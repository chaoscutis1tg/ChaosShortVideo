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

    def __post_init__(self) -> None:
        self.pause_event.set()

    def active_elapsed_sec(self) -> int:
        now = time.monotonic()
        extra_pause = (now - self.paused_since_mono) if self.paused_since_mono is not None else 0.0
        return max(0, int(round(now - self.started_mono - self.paused_accum_sec - extra_pause)))

    def compute_overall_and_eta(self, stage: str, stage_pct: float) -> Tuple[float, Optional[int], str]:
        """Convert per-stage percentage into monotonic overall 0..100% + smoothed remaining seconds."""
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

        # Render span allocation
        render_base = (
            0.0
            if self.is_render_only
            else (42.0 if self.mode == ProjectMode.MOVIE_CLIPPER else 16.0)
        )
        render_span = 99.0 - render_base

        if stage == "INGESTING":
            raw_overall = s_frac * 14.0
            step_lbl = "Bước 1/4 • Tải & kiểm tra video"
        elif stage == "TRANSCRIBING_GPU":
            raw_overall = 14.0 + s_frac * 20.0
            step_lbl = "Bước 2/4 • Tách thoại AI (Whisper)"
        elif stage == "AI_ANALYZING":
            if self.mode == ProjectMode.MOVIE_CLIPPER:
                raw_overall = 34.0 + s_frac * 8.0
                step_lbl = "Bước 3/4 • Dịch Vietsub & chia tập"
            else:
                raw_overall = s_frac * 16.0
                step_lbl = "Bước 1/3 • AI lên kịch bản"
        elif stage in ("GENERATING_ASSETS", "RENDERING_NVENC", "PACKAGING_SEO"):
            clip_slice = render_span / float(n_clips)
            clip_origin = render_base + (c_idx - 1) * clip_slice
            if stage == "GENERATING_ASSETS":
                sub_frac = s_frac * 0.45
                sub_name = "Thu giọng & dựng cảnh"
            elif stage == "RENDERING_NVENC":
                sub_frac = 0.45 + s_frac * 0.50
                sub_name = "Kết xuất MP4 9:16"
            else:
                sub_frac = 0.95 + s_frac * 0.05
                sub_name = "Đóng gói SEO"
            raw_overall = clip_origin + clip_slice * sub_frac
            part_tag = f"Phần {c_idx}/{n_clips}" if n_clips > 1 else "Video chính"
            step_lbl = f"{part_tag} • {sub_name}"
        else:
            raw_overall = self.overall_pct
            step_lbl = stage

        self.overall_pct = round(min(99.4, max(self.overall_pct, raw_overall)), 1)
        elapsed = self.active_elapsed_sec()
        delta_pct = self.overall_pct - self.baseline_pct

        eta_out: Optional[int] = self.smoothed_eta_sec
        if elapsed >= 2 and delta_pct >= 1.5 and self.overall_pct < 99.5:
            raw_eta = elapsed * ((100.0 - self.overall_pct) / max(delta_pct, 1.0))
            raw_eta_clamped = int(min(7200, max(1, round(raw_eta))))
            if self.smoothed_eta_sec is None:
                eta_out = raw_eta_clamped
            else:
                eta_out = int(round(0.68 * self.smoothed_eta_sec + 0.32 * raw_eta_clamped))
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
        """Enrich progress with overall %, elapsed_sec, eta_sec, and step_label before broadcasting."""
        self.checkpoint_sync(project_id)
        rt = self._runtimes.get(project_id)
        if rt is not None:
            if stage not in ("PAUSED", "CANCELLED", "FAILED"):
                rt.last_active_stage = stage
            overall_pct, eta_sec, step_lbl = rt.compute_overall_and_eta(stage, stage_pct)
            self.hub.publish_sync(
                project_id=project_id,
                stage=stage,
                percent=overall_pct,
                message=message,
                elapsed_sec=rt.active_elapsed_sec(),
                eta_sec=eta_sec,
                step_label=step_lbl,
            )
        else:
            self.hub.publish_sync(project_id, stage, stage_pct, message)

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

    async def _execute_and_advance(
        self,
        project_id: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> None:
        try:
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

    def inspect_storage(self) -> Dict[str, Any]:
        """Compute disk free space and workspace folder sizes in MB/GB."""
        usage = shutil.disk_usage(str(self.settings.workspace_root))
        work_bytes = self._folder_size_bytes(self.settings.work_dir, exclude_files={"studio.db", "studio.db-wal", "studio.db-shm"})
        out_bytes = self._folder_size_bytes(self.settings.outputs_dir)
        return {
            "disk_free_gb": round(usage.free / (1024**3), 1),
            "disk_total_gb": round(usage.total / (1024**3), 1),
            "work_temp_mb": round(work_bytes / (1024**2), 1),
            "outputs_mb": round(out_bytes / (1024**2), 1),
        }

    def cleanup_temp_files(self) -> Dict[str, Any]:
        """Safely purge temporary folders of finished/failed/cancelled projects while keeping all MP4 outputs."""
        before_bytes = self._folder_size_bytes(
            self.settings.work_dir, exclude_files={"studio.db", "studio.db-wal", "studio.db-shm"}
        )
        protected_pids: set[str] = set(self._runtimes.keys()) | {q[0] for q in self._queue}
        for p in self.repo.list_projects():
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

        removed_folders = 0
        if self.settings.work_dir.exists():
            for child in self.settings.work_dir.iterdir():
                if not child.is_dir():
                    continue
                if child.name == "_voice_previews":
                    shutil.rmtree(child, ignore_errors=True)
                    removed_folders += 1
                    continue
                if child.name == "_uploads":
                    # Keep _uploads if any project is awaiting review / queued / paused
                    if not protected_pids:
                        shutil.rmtree(child, ignore_errors=True)
                        removed_folders += 1
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
            "storage": self.inspect_storage(),
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

