"""Cooperative Pause/Resume/Cancel controller, Sequential Batch Queue, ETA calculator & Temp Cleaner."""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Callable, Coroutine, Deque, Dict, Optional, Tuple

from app.m00_core_contracts import JobState, ProjectMode, SQLiteRepository, StudioSettings

from .progress_hub import WebSocketProgressHub


class JobCancelledException(Exception):
    """Raised internally when a user cancels an active or paused project."""


@dataclass
class ActiveJobRuntime:
    """Tracks pause/cancel state, monotonic overall progress, and smoothed ETA for one job."""

    project_id: str
    mode: ProjectMode
    is_render_only: bool = False
    pause_event: threading.Event = field(default_factory=threading.Event)
    cancelled: bool = False
    started_mono: float = field(default_factory=time.monotonic)
    paused_accum_sec: float = 0.0
    paused_since_mono: Optional[float] = None
    last_active_stage: str = "INGESTING"
    total_clips: int = 1
    current_clip_idx: int = 1
    overall_pct: float = 1.0
    baseline_pct: float = 0.0
    smoothed_eta_sec: Optional[int] = None
    last_message: str = "Đang khởi tạo tiến trình..."
    last_step_label: str = "Khởi động"
    last_progress_mono: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.pause_event.set()

    def active_elapsed_sec(self) -> int:
        now = time.monotonic()
        extra_pause = (now - self.paused_since_mono) if self.paused_since_mono is not None else 0.0
        return max(0, int(round(now - self.started_mono - self.paused_accum_sec - extra_pause)))

    def compute_overall_and_eta(self, stage: str, stage_pct: float) -> Tuple[float, Optional[int], str]:
        """Convert real per-stage percentage into monotonic overall 0..100% + accurate remaining seconds."""
        s_frac = min(1.0, max(0.0, float(stage_pct) / 100.0))
        n_clips = max(1, self.total_clips)
        c_idx = min(n_clips, max(1, self.current_clip_idx))

        if stage == "COMPLETED":
            self.overall_pct = 100.0
            return 100.0, 0, "Hoàn tất 100%"
        if stage in ("AWAITING_REVIEW",):
            self.overall_pct = 100.0
            return 100.0, 0, "Chờ duyệt kịch bản"
        if stage in ("FAILED", "CANCELLED"):
            return self.overall_pct, None, stage

        # Accurate non-overlapping stage weights matching real wall-clock GPU/CPU execution
        render_base = (
            0.0
            if self.is_render_only
            else (38.0 if self.mode == ProjectMode.MOVIE_CLIPPER else 16.0)
        )
        render_span = 99.2 - render_base

        if stage == "INGESTING":
            span_ing = 12.0 if self.mode == ProjectMode.MOVIE_CLIPPER else 9.0
            raw_overall = s_frac * span_ing
            step_lbl = "Bước 1 • Kiểm tra & chuẩn bị video"
        elif stage == "TRANSCRIBING_GPU":
            raw_overall = 12.0 + s_frac * 18.0
            step_lbl = "Bước 2 • Tách thoại GPU (Whisper)"
        elif stage == "AI_ANALYZING":
            if self.mode == ProjectMode.MOVIE_CLIPPER:
                raw_overall = 30.0 + s_frac * 8.0
                step_lbl = "Bước 3 • Dịch ngữ cảnh & chia tập"
            elif self.mode == ProjectMode.THREADS_TOPIC:
                raw_overall = 9.0 + s_frac * 7.0
                step_lbl = "Bước 2 • Dàn kịch bản thẻ bình luận"
            else:
                raw_overall = s_frac * 16.0
                step_lbl = "Bước 1 • AI phân tích & viết kịch bản"
        elif stage in (
            "GENERATING_AUDIO",
            "GENERATING_VISUALS",
            "GENERATING_ASSETS",
            "ASSEMBLING_FRAMES",
            "RENDERING_NVENC",
            "PACKAGING_SEO",
        ):
            clip_slice = render_span / float(n_clips)
            clip_origin = render_base + (c_idx - 1) * clip_slice
            if stage == "GENERATING_AUDIO":
                sub_frac = s_frac * 0.34
                sub_name = "Thu giọng đọc & trộn âm"
            elif stage == "GENERATING_VISUALS":
                sub_frac = 0.34 + s_frac * 0.18
                sub_name = "Thiết kế thẻ & hình ảnh"
            elif stage == "GENERATING_ASSETS":
                # Legacy fallback if called directly
                sub_frac = s_frac * 0.50
                sub_name = "Thu giọng & dựng cảnh"
            elif stage == "ASSEMBLING_FRAMES":
                sub_frac = 0.52 + s_frac * 0.32
                sub_name = "Dựng chuyển động 9:16"
            elif stage == "RENDERING_NVENC":
                sub_frac = 0.84 + s_frac * 0.12
                sub_name = "Mã hóa MP4 (FFmpeg/NVENC)"
            else:
                sub_frac = 0.96 + s_frac * 0.04
                sub_name = "Ảnh bìa & Gói SEO"
            raw_overall = clip_origin + clip_slice * sub_frac
            part_tag = f"Phần {c_idx}/{n_clips}" if n_clips > 1 else "Video chính"
            step_lbl = f"{part_tag} • {sub_name}"
        else:
            raw_overall = self.overall_pct
            step_lbl = stage

        self.overall_pct = round(min(99.5, max(self.overall_pct, raw_overall)), 1)
        self.last_step_label = step_lbl
        elapsed = self.active_elapsed_sec()
        delta_pct = self.overall_pct - self.baseline_pct

        eta_out: Optional[int] = self.smoothed_eta_sec
        if elapsed >= 2 and delta_pct >= 2.0 and self.overall_pct < 99.5:
            raw_eta = elapsed * ((100.0 - self.overall_pct) / max(delta_pct, 1.0))
            # Responsive ETA without wild multi-hour inflation if a single step paused briefly
            raw_eta_clamped = int(min(1800, max(1, round(raw_eta))))
            if self.smoothed_eta_sec is None:
                eta_out = raw_eta_clamped
            else:
                eta_out = int(round(0.55 * self.smoothed_eta_sec + 0.45 * raw_eta_clamped))
            self.smoothed_eta_sec = eta_out

        return self.overall_pct, eta_out, step_lbl


class JobExecutionManager:
    """Manages active job execution, cooperative Pause/Resume/Cancel, and FIFO Batch Queue."""

    def __init__(
        self,
        settings: StudioSettings,
        repo: SQLiteRepository,
        hub: WebSocketProgressHub,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.hub = hub
        self._runtimes: Dict[str, ActiveJobRuntime] = {}
        self._queue: Deque[Tuple[str, ProjectMode, bool, Callable[[], Coroutine[Any, Any, Any]]]] = deque()
        self._active_pid: Optional[str] = None
        self._lock = threading.Lock()
        self._storage_cache_ts: float = 0.0
        self._storage_cache_val: Optional[Dict[str, Any]] = None

    def is_in_memory_active_or_paused(self, project_id: str) -> bool:
        return project_id in self._runtimes or any(q[0] == project_id for q in self._queue)

    def set_clip_cursor(self, project_id: str, current_idx: int, total_clips: int) -> None:
        rt = self._runtimes.get(project_id)
        if rt:
            rt.current_clip_idx = max(1, current_idx)
            rt.total_clips = max(1, total_clips)

    def checkpoint_sync(self, project_id: str) -> None:
        """Called on worker threads: blocks while paused and raises if cancelled."""
        rt = self._runtimes.get(project_id)
        if rt is None:
            return
        if rt.cancelled:
            raise JobCancelledException("Dự án đã dừng theo yêu cầu người dùng.")
        if threading.current_thread() is not threading.main_thread():
            while not rt.pause_event.is_set():
                if rt.cancelled:
                    raise JobCancelledException("Dự án đã dừng theo yêu cầu người dùng.")
                rt.pause_event.wait(timeout=0.35)
            if rt.cancelled:
                raise JobCancelledException("Dự án đã dừng theo yêu cầu người dùng.")

    async def checkpoint_async(self, project_id: str) -> None:
        """Called on asyncio loop between steps/clips: awaits unpause and raises if cancelled."""
        rt = self._runtimes.get(project_id)
        if rt is None:
            return
        while not rt.pause_event.is_set():
            if rt.cancelled:
                raise JobCancelledException("Dự án đã dừng theo yêu cầu người dùng.")
            await asyncio.sleep(0.35)
        if rt.cancelled:
            raise JobCancelledException("Dự án đã dừng theo yêu cầu người dùng.")

    def report_progress(self, project_id: str, stage: str, stage_pct: float, message: str) -> None:
        """Enrich progress with real overall %, elapsed_sec, eta_sec, step_label & console log."""
        self.checkpoint_sync(project_id)
        is_transient_frame = stage in ("ASSEMBLING_FRAMES", "RENDERING_NVENC") and (
            "Khung " in message or "Ghép âm thanh &" in message or "Đang xuất Phần" in message
        )
        rt = self._runtimes.get(project_id)
        if rt is not None:
            now_m = time.monotonic()
            if stage not in ("PAUSED", "CANCELLED", "FAILED"):
                rt.last_active_stage = stage
            rt.last_message = message
            rt.last_progress_mono = now_m
            overall_pct, eta_sec, step_lbl = rt.compute_overall_and_eta(stage, stage_pct)
            self.hub.publish_sync(
                project_id=project_id,
                stage=stage,
                percent=overall_pct,
                message=message,
                elapsed_sec=rt.active_elapsed_sec(),
                eta_sec=eta_sec,
                step_label=step_lbl,
                stage_percent=stage_pct,
                replace_last_transient=is_transient_frame,
            )
        else:
            self.hub.publish_sync(
                project_id,
                stage,
                stage_pct,
                message,
                stage_percent=stage_pct,
                replace_last_transient=is_transient_frame,
            )

    def enqueue_job(
        self,
        project_id: str,
        mode: ProjectMode,
        is_render_only: bool,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> str:
        """Start job immediately if slot is free; otherwise place in FIFO Batch Queue."""
        with self._lock:
            if self._active_pid is not None and self._active_pid != project_id:
                self._queue.append((project_id, mode, is_render_only, coro_factory))
                q_pos = len(self._queue)
                self.repo.update_project_state(project_id, JobState.QUEUED)
                self.hub.publish_sync(
                    project_id=project_id,
                    stage=JobState.QUEUED.value,
                    percent=0.0,
                    message=f"Đang xếp hàng đợi tự động (Vị trí #{q_pos}) — sẽ chạy ngay khi video trước xong!",
                    queue_position=q_pos,
                )
                return JobState.QUEUED.value

            self._active_pid = project_id
            self._runtimes[project_id] = ActiveJobRuntime(
                project_id=project_id,
                mode=mode,
                is_render_only=is_render_only,
            )

        asyncio.create_task(self._execute_and_advance(project_id, coro_factory))
        return JobState.INGESTING.value if mode == ProjectMode.MOVIE_CLIPPER and not is_render_only else JobState.AI_ANALYZING.value

    async def _heartbeat_loop(self, project_id: str, stop_ev: asyncio.Event) -> None:
        """Emit live 1.5s elapsed-time telemetry & active watchdog heartbeat during heavy GPU/API calls."""
        while not stop_ev.is_set():
            try:
                await asyncio.wait_for(stop_ev.wait(), timeout=1.5)
                break
            except asyncio.TimeoutError:
                pass
            rt = self._runtimes.get(project_id)
            if rt is None or not rt.pause_event.is_set() or rt.cancelled:
                continue
            idle_sec = time.monotonic() - rt.last_progress_mono
            if idle_sec >= 4.5:
                hb_msg = (
                    f"{rt.last_message} (đang xử lý bước hiện tại: {int(round(idle_sec))}s)"
                )
                self.hub.publish_sync(
                    project_id=project_id,
                    stage=rt.last_active_stage,
                    percent=rt.overall_pct,
                    message=hb_msg,
                    elapsed_sec=rt.active_elapsed_sec(),
                    eta_sec=rt.smoothed_eta_sec,
                    step_label=rt.last_step_label,
                    replace_last_transient=True,
                )

    async def _execute_and_advance(
        self,
        project_id: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> None:
        stop_hb = asyncio.Event()
        hb_task = asyncio.create_task(self._heartbeat_loop(project_id, stop_hb))
        try:
            self.hub.publish_sync(
                project_id=project_id,
                stage="INGESTING",
                percent=1.0,
                message="🚀 Đã khởi chạy tiến trình xử lý tự động...",
                elapsed_sec=0,
                step_label="Khởi động pipeline",
            )
            await coro_factory()
        except JobCancelledException as cancel_exc:
            self.repo.update_project_state(project_id, JobState.CANCELLED, error_message=str(cancel_exc))
            self.hub.publish_sync(
                project_id,
                JobState.CANCELLED.value,
                self._runtimes[project_id].overall_pct if project_id in self._runtimes else 0.0,
                "⏹️ Đã hủy tiến trình theo yêu cầu (các phần đã xuất trước đó vẫn được giữ nguyên).",
            )
        except Exception:
            # PipelineOrchestrator already sets FAILED state & broadcasts error
            pass
        finally:
            stop_hb.set()
            hb_task.cancel()
            next_item: Optional[Tuple[str, ProjectMode, bool, Callable[[], Coroutine[Any, Any, Any]]]] = None
            with self._lock:
                self._runtimes.pop(project_id, None)
                if self._active_pid == project_id:
                    self._active_pid = None
                if self._queue:
                    next_item = self._queue.popleft()
                    self._active_pid = next_item[0]
                    self._runtimes[next_item[0]] = ActiveJobRuntime(
                        project_id=next_item[0],
                        mode=next_item[1],
                        is_render_only=next_item[2],
                    )
                    # Update remaining queue positions
                    for idx_q, (q_pid, _, _, _) in enumerate(self._queue, start=1):
                        self.hub.publish_sync(
                            q_pid,
                            JobState.QUEUED.value,
                            0.0,
                            f"Đang xếp hàng đợi tự động (Vị trí #{idx_q})...",
                            queue_position=idx_q,
                        )

            if next_item is not None:
                n_pid, _, _, n_factory = next_item
                asyncio.create_task(self._execute_and_advance(n_pid, n_factory))

    def pause_job(self, project_id: str) -> bool:
        """Pause an actively running job at the nearest safe boundary."""
        rt = self._runtimes.get(project_id)
        if rt is None:
            return False
        if rt.pause_event.is_set():
            rt.pause_event.clear()
            rt.paused_since_mono = time.monotonic()
        self.repo.update_project_state(project_id, JobState.PAUSED)
        self.hub.publish_sync(
            project_id=project_id,
            stage=JobState.PAUSED.value,
            percent=rt.overall_pct,
            message="⏸️ Đã tạm dừng an toàn — bấm 'Tiếp tục' bất cứ lúc nào để chạy tiếp!",
            elapsed_sec=rt.active_elapsed_sec(),
            eta_sec=rt.smoothed_eta_sec,
            step_label="Đang tạm dừng",
        )
        return True

    def resume_in_memory_job(self, project_id: str) -> bool:
        """Unpause an in-memory paused job immediately. Returns False if job is from older session."""
        rt = self._runtimes.get(project_id)
        if rt is None:
            return False
        if not rt.pause_event.is_set():
            if rt.paused_since_mono is not None:
                rt.paused_accum_sec += max(0.0, time.monotonic() - rt.paused_since_mono)
                rt.paused_since_mono = None
            rt.pause_event.set()
        restored_stage = (
            JobState(rt.last_active_stage)
            if rt.last_active_stage in JobState._value2member_map_
            else JobState.GENERATING_ASSETS
        )
        self.repo.update_project_state(project_id, restored_stage)
        self.hub.publish_sync(
            project_id=project_id,
            stage=restored_stage.value,
            percent=rt.overall_pct,
            message="▶️ Đã tiếp tục tiến trình xử lý...",
            elapsed_sec=rt.active_elapsed_sec(),
            eta_sec=rt.smoothed_eta_sec,
        )
        return True

    def cancel_job(self, project_id: str) -> bool:
        """Cancel either a queued job or an active/paused job."""
        with self._lock:
            for item in list(self._queue):
                if item[0] == project_id:
                    self._queue.remove(item)
                    self.repo.update_project_state(project_id, JobState.CANCELLED)
                    self.hub.publish_sync(
                        project_id, JobState.CANCELLED.value, 0.0, "⏹️ Đã hủy khỏi hàng đợi."
                    )
                    return True

        rt = self._runtimes.get(project_id)
        if rt is not None:
            rt.cancelled = True
            rt.pause_event.set()
            self.repo.update_project_state(project_id, JobState.CANCELLED)
            self.hub.publish_sync(
                project_id,
                JobState.CANCELLED.value,
                rt.overall_pct,
                "⏹️ Đang dừng tác vụ hiện tại...",
            )
            return True

        # Stale DB job from previous session
        self.repo.update_project_state(project_id, JobState.CANCELLED)
        self.hub.publish_sync(project_id, JobState.CANCELLED.value, 0.0, "⏹️ Đã hủy dự án.")
        return True

    def inspect_storage(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Compute disk free space and workspace folder sizes in MB/GB (cached for 20s to avoid rglob thrashing)."""
        now_m = time.monotonic()
        if (
            not force_refresh
            and self._storage_cache_val is not None
            and (now_m - self._storage_cache_ts) < 20.0
        ):
            return dict(self._storage_cache_val)
        usage = shutil.disk_usage(str(self.settings.workspace_root))
        work_bytes = self._folder_size_bytes(
            self.settings.work_dir, exclude_files={"studio.db", "studio.db-wal", "studio.db-shm"}
        )
        out_bytes = self._folder_size_bytes(self.settings.outputs_dir)
        val = {
            "disk_free_gb": round(usage.free / (1024**3), 1),
            "disk_total_gb": round(usage.total / (1024**3), 1),
            "work_temp_mb": round(work_bytes / (1024**2), 1),
            "outputs_mb": round(out_bytes / (1024**2), 1),
        }
        self._storage_cache_val = val
        self._storage_cache_ts = now_m
        return dict(val)

    def cleanup_temp_files(self) -> Dict[str, Any]:
        """Safely purge temporary folders of finished/failed/cancelled projects while keeping all MP4 outputs."""
        before_bytes = self._folder_size_bytes(
            self.settings.work_dir, exclude_files={"studio.db", "studio.db-wal", "studio.db-shm"}
        )
        protected_pids: set[str] = set(self._runtimes.keys()) | {q[0] for q in self._queue}
        protected_upload_files: set[Path] = set()
        for p in self.repo.list_projects(include_payload=True):
            if p["state"] in (
                JobState.QUEUED.value,
                JobState.INGESTING.value,
                JobState.TRANSCRIBING_GPU.value,
                JobState.AI_ANALYZING.value,
                JobState.AWAITING_REVIEW.value,
                JobState.GENERATING_ASSETS.value,
                JobState.RENDERING_NVENC.value,
                JobState.PACKAGING_SEO.value,
                JobState.PAUSED.value,
            ):
                protected_pids.add(p["id"])
            # Preserve any uploaded product photos, demo clips, or custom BGM referenced by existing projects
            try:
                import json

                req_obj = json.loads(p.get("request_payload_json") or "{}")
                for key in ("image_paths", "feedback_image_paths"):
                    for fp in req_obj.get(key) or []:
                        if fp:
                            protected_upload_files.add(Path(fp).resolve())
                for single_key in (
                    "demo_clip_path",
                    "custom_bgm_path",
                    "external_srt_path",
                    "bg_path_or_url",
                ):
                    val_s = req_obj.get(single_key)
                    if val_s and not str(val_s).startswith(("http://", "https://")):
                        protected_upload_files.add(Path(val_s).resolve())
            except Exception:
                pass
        for bg_item in self.repo.list_bg_videos():
            try:
                protected_upload_files.add(bg_item.local_path.resolve())
            except OSError:
                pass

        removed_folders = 0
        if self.settings.work_dir.exists():
            for child in self.settings.work_dir.iterdir():
                if not child.is_dir():
                    continue
                if child.name in ("_voice_previews", "_frame_previews"):
                    shutil.rmtree(child, ignore_errors=True)
                    removed_folders += 1
                    continue
                if child.name == "_uploads":
                    # Only remove orphaned files in _uploads that are NOT referenced by any saved project
                    if not protected_pids:
                        for up_item in list(child.rglob("*")):
                            if up_item.is_file():
                                try:
                                    if up_item.resolve() not in protected_upload_files:
                                        up_item.unlink(missing_ok=True)
                                except OSError:
                                    pass
                    continue
                if child.name == "_tts_cache":
                    continue
                if child.name not in protected_pids:
                    shutil.rmtree(child, ignore_errors=True)
                    removed_folders += 1

        after_bytes = self._folder_size_bytes(
            self.settings.work_dir, exclude_files={"studio.db", "studio.db-wal", "studio.db-shm"}
        )
        freed_mb = max(0.0, round((before_bytes - after_bytes) / (1024**2), 1))
        return {
            "freed_mb": freed_mb,
            "removed_folders": removed_folders,
            "storage": self.inspect_storage(force_refresh=True),
        }

    @staticmethod
    def _folder_size_bytes(folder: Path, exclude_files: Optional[set[str]] = None) -> int:
        if not folder.exists():
            return 0
        excl = exclude_files or set()
        total = 0
        for p in folder.rglob("*"):
            if p.is_file() and p.name not in excl:
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return total

