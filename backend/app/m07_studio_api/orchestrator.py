"""Pipeline Orchestrator wiring M01..M06 strictly through M00 Interfaces & DTOs."""

import asyncio
import json
from pathlib import Path
import re
import subprocess
from typing import Dict, List, Optional
import wave

from app.m00_core_contracts import (
    AudioSubConfigDTO,
    ClipSpecDTO,
    CutConfigDTO,
    CutPlanDTO,
    DEFAULT_VOICE_PROFILES,
    ILLMService,
    IMediaIngestor,
    IngestRequestDTO,
    ITranscriber,
    IVideoCompositor,
    IVisualProducer,
    IVoiceAudioMixer,
    JobState,
    LayoutAndAntiCopyConfigDTO,
    MASTER_AUDIO_SAMPLE_RATE,
    MediaAssetDTO,
    ProductReviewPromptDTO,
    ProjectMode,
    RenderJobSpecDTO,
    RenderOutputDTO,
    ScrapedThreadBundleDTO,
    SEOPackageDTO,
    SQLiteRepository,
    StudioBaseError,
    StudioSettings,
    TopicPromptDTO,
    VisualMode,
    VoiceProfileDTO,
    resolve_aspect_dimensions,
)

from .job_manager import JobCancelledException, JobExecutionManager
from .progress_hub import WebSocketProgressHub


def _slugify_folder(name: str, fallback: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", name).strip(" ._")
    return cleaned[:80] if cleaned else fallback


def _extract_demo_audio_44k(demo_path: Path, dst_wav: Path, max_sec: float = 22.0) -> tuple[Optional[Path], int]:
    """Extract 44.1kHz stereo WAV from a real product/instrument demo video or audio file."""
    if not demo_path.exists():
        return None, 0
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-t",
        f"{max_sec:.2f}",
        "-i",
        str(demo_path),
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(MASTER_AUDIO_SAMPLE_RATE),
        "-ac",
        "2",
        str(dst_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0 and dst_wav.exists() and dst_wav.stat().st_size > 200:
        with wave.open(str(dst_wav), "rb") as wf:
            dur_ms = max(1000, int(round(wf.getnframes() / float(wf.getframerate()) * 1000.0)))
        return dst_wav, min(dur_ms, int(max_sec * 1000))

    # Video without audio stream (e.g. silent outfit try-on clip): probe video duration via ffprobe
    probe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(demo_path),
    ]
    p_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
    try:
        v_dur_ms = int(round(float((p_res.stdout or "0").strip()) * 1000.0))
        return None, min(max(v_dur_ms, 3000), int(max_sec * 1000)) if v_dur_ms > 0 else 0
    except ValueError:
        return None, 0


class PipelineOrchestrator:
    """Coordinates Topic-to-Video, Movie Clipper, and Product Showcase pipelines."""

    def __init__(
        self,
        settings: StudioSettings,
        repo: SQLiteRepository,
        progress_hub: WebSocketProgressHub,
        ingestor: IMediaIngestor,
        transcriber: ITranscriber,
        brain: ILLMService,
        visual_producer: IVisualProducer,
        audio_mixer: IVoiceAudioMixer,
        compositor: IVideoCompositor,
        job_manager: Optional[JobExecutionManager] = None,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.hub = progress_hub
        self.ingestor = ingestor
        self.transcriber = transcriber
        self.brain = brain
        self.visual_producer = visual_producer
        self.audio_mixer = audio_mixer
        self.compositor = compositor
        self.job_mgr = job_manager

        # Runtime context cache for seamless resume after Studio Review
        self._pending_plans: Dict[str, CutPlanDTO] = {}
        self._pending_media: Dict[str, MediaAssetDTO] = {}
        self._pending_visual_modes: Dict[str, VisualMode] = {}
        self._pending_products: Dict[str, ProductReviewPromptDTO] = {}

    def _cb(self, project_id: str):
        def _notify(stage: str, pct: float, msg: str) -> None:
            if self.job_mgr is not None:
                self.job_mgr.report_progress(project_id, stage, pct, msg)
            else:
                self.hub.publish_sync(project_id, stage, pct, msg)

        return _notify

    async def _checkpoint(self, project_id: str) -> None:
        if self.job_mgr is not None:
            await self.job_mgr.checkpoint_async(project_id)

    def _resolve_voice(self, profile_id: str) -> VoiceProfileDTO:
        found = self.repo.get_voice_profile(profile_id)
        return found if found is not None else DEFAULT_VOICE_PROFILES[0]

    def _build_voice_registry(self) -> Dict[str, VoiceProfileDTO]:
        return {vp.profile_id: vp for vp in self.repo.list_voice_profiles()}

    async def execute_threads_pipeline(
        self,
        ingest_req: IngestRequestDTO,
        bundle: ScrapedThreadBundleDTO,
        append_cta_comment: str,
        voice_profile_id: str,
        audio_config: AudioSubConfigDTO,
        layout_config: LayoutAndAntiCopyConfigDTO,
        auto_one_click: bool = True,
    ) -> CutPlanDTO:
        """Run Mode 4 (Threads & Comments): Ingest BG video -> Build CutPlan -> Render Floating Cards."""
        pid = ingest_req.project_id
        cb = self._cb(pid)
        try:
            self.repo.update_project_state(pid, JobState.INGESTING)
            cb("INGESTING", 25.0, "Đang chuẩn bị video nền lặp vòng 9:16...")
            media = await self.ingestor.ingest(
                ingest_req, work_dir=self.settings.work_dir, on_progress=cb
            )
            self.repo.save_source_media(media, source_type=ingest_req.source_type.value)
            self._pending_media[pid] = media

            self.repo.update_project_state(pid, JobState.AI_ANALYZING)
            cb("AI_ANALYZING", 60.0, "Đang dàn trang kịch bản bài đăng gốc & các bình luận tiêu biểu...")
            cut_plan = await self.brain.build_threads_clips(
                bundle=bundle,
                project_id=pid,
                append_cta_comment=append_cta_comment,
                anonymize_handles=layout_config.threads_anonymize_handles,
            )
            self.repo.save_cut_plan(cut_plan)
            self._pending_plans[pid] = cut_plan

            if not auto_one_click:
                self.repo.update_project_state(pid, JobState.AWAITING_REVIEW)
                cb(
                    "AWAITING_REVIEW",
                    100.0,
                    "Đã sẵn sàng kịch bản Threads & bình luận! Mời bạn kiểm tra trước khi xuất video.",
                )
                return cut_plan

            await self.render_approved_plan(
                project_id=pid,
                cut_plan=cut_plan,
                voice_profile_id=voice_profile_id,
                audio_config=audio_config,
                layout_config=layout_config,
                media_override=media,
            )
            return cut_plan
        except JobCancelledException:
            raise
        except Exception as exc:
            err_txt = exc.message if isinstance(exc, StudioBaseError) else str(exc)
            self.repo.update_project_state(pid, JobState.FAILED, error_message=err_txt)
            cb("FAILED", 0.0, f"Lỗi xử lý video Threads: {err_txt}")
            raise

    async def execute_topic_pipeline(
        self,
        prompt_req: TopicPromptDTO,
        voice_profile_id: str,
        audio_config: AudioSubConfigDTO,
        layout_config: LayoutAndAntiCopyConfigDTO,
        auto_one_click: bool = True,
    ) -> CutPlanDTO:
        """Run Mode 1: Generate script -> optionally pause for review -> render MP4 + SEO."""
        pid = prompt_req.project_id
        cb = self._cb(pid)
        try:
            self.repo.update_project_state(pid, JobState.AI_ANALYZING)
            cb("AI_ANALYZING", 20.0, "Đang viết kịch bản phân cảnh cuốn hút từ chủ đề...")

            cut_plan = await self.brain.build_topic_clips(prompt_req)
            self.repo.save_cut_plan(cut_plan)
            self._pending_plans[pid] = cut_plan
            self._pending_visual_modes[pid] = prompt_req.visual_mode

            if not auto_one_click:
                self.repo.update_project_state(pid, JobState.AWAITING_REVIEW)
                cb("AWAITING_REVIEW", 100.0, "Đã sinh kịch bản! Mời bạn xem/chỉnh sửa trước khi dựng.")
                return cut_plan

            await self.render_approved_plan(
                project_id=pid,
                cut_plan=cut_plan,
                voice_profile_id=voice_profile_id,
                audio_config=audio_config,
                layout_config=layout_config,
                visual_mode=prompt_req.visual_mode,
            )
            return cut_plan
        except JobCancelledException:
            raise
        except Exception as exc:
            err_txt = exc.message if isinstance(exc, StudioBaseError) else str(exc)
            self.repo.update_project_state(pid, JobState.FAILED, error_message=err_txt)
            cb("FAILED", 0.0, f"Lỗi xử lý: {err_txt}")
            raise

    async def execute_product_pipeline(
        self,
        prompt_req: ProductReviewPromptDTO,
        voice_profile_id: str,
        audio_config: AudioSubConfigDTO,
        layout_config: LayoutAndAntiCopyConfigDTO,
        auto_one_click: bool = True,
    ) -> CutPlanDTO:
        """Run Mode 3: Analyze product photos + specs -> sales script -> uncropped 9:16 showcase MP4."""
        pid = prompt_req.project_id
        cb = self._cb(pid)
        try:
            self.repo.update_project_state(pid, JobState.AI_ANALYZING)
            cb(
                "AI_ANALYZING",
                18.0,
                f"AI đang xem {len(prompt_req.image_paths)} ảnh sản phẩm & viết kịch bản chốt đơn...",
            )

            proj_work_dir = self.settings.work_dir / pid
            demo_dur_ms = 0
            if prompt_req.demo_clip_path and prompt_req.demo_clip_path.exists():
                _, demo_dur_ms = await asyncio.to_thread(
                    _extract_demo_audio_44k,
                    prompt_req.demo_clip_path,
                    proj_work_dir / "demo_44k.wav",
                )

            cut_plan = await self.brain.build_product_review_clips(
                prompt_req, demo_duration_ms=demo_dur_ms
            )
            self.repo.save_cut_plan(cut_plan)
            self._pending_plans[pid] = cut_plan
            self._pending_products[pid] = prompt_req

            if not auto_one_click:
                self.repo.update_project_state(pid, JobState.AWAITING_REVIEW)
                cb(
                    "AWAITING_REVIEW",
                    100.0,
                    "Đã lên kịch bản bán hàng & ghép ảnh! Mời bạn kiểm tra trước khi xuất video.",
                )
                return cut_plan

            await self.render_approved_plan(
                project_id=pid,
                cut_plan=cut_plan,
                voice_profile_id=voice_profile_id,
                audio_config=audio_config,
                layout_config=layout_config,
            )
            return cut_plan
        except JobCancelledException:
            raise
        except Exception as exc:
            err_txt = exc.message if isinstance(exc, StudioBaseError) else str(exc)
            self.repo.update_project_state(pid, JobState.FAILED, error_message=err_txt)
            cb("FAILED", 0.0, f"Lỗi xử lý sản phẩm: {err_txt}")
            raise

    async def execute_movie_pipeline(
        self,
        ingest_req: IngestRequestDTO,
        cut_config: CutConfigDTO,
        voice_profile_id: str,
        audio_config: AudioSubConfigDTO,
        layout_config: LayoutAndAntiCopyConfigDTO,
        lang_hint: str = "auto",
        auto_one_click: bool = True,
    ) -> CutPlanDTO:
        """Run Mode 2: Ingest -> GPU Whisper ASR -> Translate & Smart Split -> Render NVENC + SEO."""
        pid = ingest_req.project_id
        cb = self._cb(pid)
        try:
            self.repo.update_project_state(pid, JobState.INGESTING)
            media = await self.ingestor.ingest(
                ingest_req, work_dir=self.settings.work_dir, on_progress=cb
            )
            self.repo.save_source_media(media, source_type=ingest_req.source_type.value)
            self._pending_media[pid] = media

            self.repo.update_project_state(pid, JobState.TRANSCRIBING_GPU)
            transcript = await self.transcriber.transcribe(
                media, lang_hint=lang_hint, on_progress=cb
            )

            self.repo.update_project_state(pid, JobState.AI_ANALYZING)
            cb("AI_ANALYZING", 45.0, "Đang dịch ngữ cảnh phim & chia tập thông minh (65-120s)...")
            cut_plan = await self.brain.translate_and_split_movie(
                transcript=transcript,
                config=cut_config,
                project_id=pid,
                total_duration_ms=media.duration_ms,
            )
            self.repo.save_cut_plan(cut_plan)
            self._pending_plans[pid] = cut_plan

            if not auto_one_click:
                self.repo.update_project_state(pid, JobState.AWAITING_REVIEW)
                cb(
                    "AWAITING_REVIEW",
                    100.0,
                    f"Đã chia thành {len(cut_plan.clips)} phần! Mời kiểm tra bản dịch & mốc cắt.",
                )
                return cut_plan

            await self.render_approved_plan(
                project_id=pid,
                cut_plan=cut_plan,
                voice_profile_id=voice_profile_id,
                audio_config=audio_config,
                layout_config=layout_config,
                media_override=media,
            )
            return cut_plan
        except JobCancelledException:
            raise
        except Exception as exc:
            err_txt = exc.message if isinstance(exc, StudioBaseError) else str(exc)
            self.repo.update_project_state(pid, JobState.FAILED, error_message=err_txt)
            cb("FAILED", 0.0, f"Lỗi xử lý: {err_txt}")
            raise

    async def render_approved_plan(
        self,
        project_id: str,
        cut_plan: CutPlanDTO,
        voice_profile_id: str,
        audio_config: AudioSubConfigDTO,
        layout_config: LayoutAndAntiCopyConfigDTO,
        visual_mode: VisualMode = VisualMode.AI_IMAGE,
        media_override: Optional[MediaAssetDTO] = None,
        image_paths_override: Optional[List[Path]] = None,
    ) -> List[RenderOutputDTO]:
        """Generate TTS/Visual assets, render MP4s via NVENC, and write SEO files."""
        cb = self._cb(project_id)
        proj_info = self.repo.get_project(project_id) or {"name": project_id}
        folder_slug = _slugify_folder(f"{proj_info.get('name', project_id)}_{project_id[:6]}", project_id)
        project_out_dir = self.settings.outputs_dir / folder_slug
        project_out_dir.mkdir(parents=True, exist_ok=True)
        project_work_dir = self.settings.work_dir / project_id

        voice_profile = self._resolve_voice(voice_profile_id)
        voice_registry = self._build_voice_registry()
        media = media_override or self._pending_media.get(project_id)
        if media is None and proj_info.get("source_media"):
            sm = proj_info["source_media"]
            media = MediaAssetDTO(
                media_id=sm["media_id"],
                project_id=project_id,
                video_path=Path(sm["local_video_path"]),
                audio_16k_wav_path=Path(sm["audio_16k_wav_path"]),
                original_stereo_wav_path=(
                    Path(sm["original_stereo_wav_path"]) if sm.get("original_stereo_wav_path") else None
                ),
                duration_ms=int(sm["duration_ms"]),
                width=int(sm["width"]),
                height=int(sm["height"]),
                fps=float(sm["fps"]),
            )

        outputs: List[RenderOutputDTO] = []
        seo_packages: List[SEOPackageDTO] = []
        total_clips = max(len(cut_plan.clips), 1)

        for idx, clip in enumerate(cut_plan.clips, start=1):
            await self._checkpoint(project_id)
            if self.job_mgr is not None:
                self.job_mgr.set_clip_cursor(project_id, idx, total_clips)
            self.repo.update_project_state(project_id, JobState.GENERATING_ASSETS)
            cb(
                "GENERATING_ASSETS",
                2.0,
                f"Đang chuẩn bị âm thanh & tài nguyên cho Phần {clip.part_number}/{total_clips}...",
            )

            visual_assets = None
            src_video: Optional[Path] = None
            orig_stereo: Optional[Path] = None
            effective_clip = clip
            effective_layout = layout_config
            canvas_w, canvas_h = resolve_aspect_dimensions(layout_config.aspect_ratio)
            has_outro = bool(
                layout_config.outro_card_enabled
                and (
                    layout_config.outro_brand_title.strip()
                    or layout_config.outro_subtitle.strip()
                    or layout_config.outro_contact_line.strip()
                    or layout_config.logo_path
                )
            )
            outro_ms = int(layout_config.outro_duration_ms) if has_outro else 0
            synced_audio_cfg = audio_config.model_copy(
                update={
                    "subtitle_pos_y": layout_config.subtitle_pos_y,
                    "subtitle_font_size": layout_config.subtitle_font_size,
                    "outro_tail_ms": outro_ms,
                }
            )

            if cut_plan.mode == ProjectMode.PRODUCT_SHOWCASE:
                prod_ctx = self._pending_products.get(project_id)
                prod_imgs: List[Path] = (
                    list(image_paths_override)
                    if image_paths_override
                    else (list(prod_ctx.image_paths) if prod_ctx else [])
                )
                prod_demo_clip: Optional[Path] = prod_ctx.demo_clip_path if prod_ctx else None

                if not prod_imgs or prod_demo_clip is None:
                    saved_payload = json.loads(proj_info.get("request_payload_json") or "{}")
                    if not prod_imgs:
                        prod_imgs = [Path(p) for p in (saved_payload.get("image_paths") or [])]
                    if prod_demo_clip is None and saved_payload.get("demo_clip_path"):
                        prod_demo_clip = Path(saved_payload["demo_clip_path"])

                if image_paths_override and prod_ctx is not None:
                    self._pending_products[project_id] = prod_ctx.model_copy(
                        update={"image_paths": list(image_paths_override)}
                    )

                demo_wav: Optional[Path] = None
                if prod_demo_clip and prod_demo_clip.exists():
                    cached_demo_wav = project_work_dir / "demo_44k.wav"
                    if cached_demo_wav.exists():
                        demo_wav = cached_demo_wav
                    else:
                        demo_wav, _ = await asyncio.to_thread(
                            _extract_demo_audio_44k, prod_demo_clip, cached_demo_wav
                        )

                # 1. Synthesize sales voiceover + real demo sound FIRST for millisecond accuracy
                prod_audio_cfg = synced_audio_cfg.model_copy(update={"keep_original_audio": False})
                audio_sub = await self.audio_mixer.process(
                    clip=clip,
                    profile=voice_profile,
                    audio_config=prod_audio_cfg,
                    out_dir=project_work_dir,
                    orig_stereo_wav=None,
                    on_progress=cb,
                    demo_audio_wav=demo_wav,
                    canvas_w=canvas_w,
                    canvas_h=canvas_h,
                    voice_registry=voice_registry,
                )

                # 2. Align every product photo & demo video scene to exact spoken timestamps
                speech_dur_ms = max(1000, audio_sub.total_audio_duration_ms - outro_ms)
                if len(audio_sub.line_spans_ms) == len(clip.lines):
                    synced_lines = [
                        ln.model_copy(update={"rel_start_ms": s_ms, "rel_end_ms": e_ms})
                        for ln, (s_ms, e_ms) in zip(clip.lines, audio_sub.line_spans_ms)
                    ]
                    effective_clip = clip.model_copy(
                        update={
                            "lines": synced_lines,
                            "source_end_ms": max(clip.duration_ms, speech_dur_ms),
                        }
                    )

                # 3. Compose uncropped multi-aspect product plates (100% media coverage, cutout, A/B, feedback & wave)
                fb_imgs = list(layout_config.feedback_image_paths or [])
                if not fb_imgs and prod_ctx and prod_ctx.feedback_image_paths:
                    fb_imgs = list(prod_ctx.feedback_image_paths)
                visual_assets = await self.visual_producer.produce_product_showcase(
                    clip=effective_clip,
                    image_paths=prod_imgs,
                    out_dir=project_work_dir,
                    demo_clip_path=prod_demo_clip,
                    on_progress=cb,
                    framing_style=layout_config.product_framing,
                    aspect_ratio=layout_config.aspect_ratio,
                    show_photo_callouts=layout_config.show_photo_callouts,
                    studio_cutout_enabled=layout_config.studio_cutout_enabled,
                    comparison_split_enabled=layout_config.comparison_split_enabled,
                    comparison_label_a=layout_config.comparison_label_a,
                    comparison_label_b=layout_config.comparison_label_b,
                    feedback_image_paths=fb_imgs,
                    demo_audio_wav=demo_wav,
                    soundwave_enabled=layout_config.soundwave_enabled,
                )
                # Preserve 1.0x authentic instrument pitch & brand orientation for shop's own photos/demo
                effective_layout = layout_config.model_copy(
                    update={"hardsub_mask_enabled": False, "anti_copyright_enabled": False}
                )
            elif cut_plan.mode == ProjectMode.THREADS_TOPIC:
                if media is None:
                    raise RuntimeError("Không tìm thấy tệp video nền cho dự án Threads.")
                src_video = media.video_path
                orig_stereo = (
                    media.original_stereo_wav_path if synced_audio_cfg.keep_original_audio else None
                )
                audio_sub = await self.audio_mixer.process(
                    clip=clip,
                    profile=voice_profile,
                    audio_config=synced_audio_cfg,
                    out_dir=project_work_dir,
                    orig_stereo_wav=orig_stereo,
                    on_progress=cb,
                    canvas_w=canvas_w,
                    canvas_h=canvas_h,
                    voice_registry=voice_registry,
                )
                speech_dur_ms = max(1000, audio_sub.total_audio_duration_ms - outro_ms)
                if len(audio_sub.line_spans_ms) == len(clip.lines):
                    synced_lines = [
                        ln.model_copy(update={"rel_start_ms": s_ms, "rel_end_ms": e_ms})
                        for ln, (s_ms, e_ms) in zip(clip.lines, audio_sub.line_spans_ms)
                    ]
                    effective_clip = clip.model_copy(
                        update={
                            "lines": synced_lines,
                            "source_end_ms": max(clip.duration_ms, speech_dur_ms),
                        }
                    )
                visual_assets = await self.visual_producer.produce_threads_cards(
                    clip=effective_clip,
                    out_dir=project_work_dir,
                    card_theme=layout_config.threads_card_theme,
                    anonymize_handles=layout_config.threads_anonymize_handles,
                    aspect_ratio=layout_config.aspect_ratio,
                    on_progress=cb,
                )
                effective_layout = layout_config.model_copy(
                    update={"hardsub_mask_enabled": False, "anti_copyright_enabled": False}
                )
            elif cut_plan.mode == ProjectMode.TOPIC_VIDEO:
                eff_vis_mode = self._pending_visual_modes.get(project_id, visual_mode)
                audio_sub = await self.audio_mixer.process(
                    clip=clip,
                    profile=voice_profile,
                    audio_config=synced_audio_cfg,
                    out_dir=project_work_dir,
                    orig_stereo_wav=None,
                    on_progress=cb,
                    canvas_w=canvas_w,
                    canvas_h=canvas_h,
                    voice_registry=voice_registry,
                )
                if len(audio_sub.line_spans_ms) == len(clip.lines):
                    synced_lines = [
                        ln.model_copy(update={"rel_start_ms": s_ms, "rel_end_ms": e_ms})
                        for ln, (s_ms, e_ms) in zip(clip.lines, audio_sub.line_spans_ms)
                    ]
                    effective_clip = clip.model_copy(
                        update={
                            "lines": synced_lines,
                            "source_end_ms": max(
                                clip.duration_ms, audio_sub.total_audio_duration_ms
                            ),
                        }
                    )
                visual_assets = await self.visual_producer.produce(
                    clip=effective_clip,
                    visual_mode=eff_vis_mode,
                    out_dir=project_work_dir,
                    on_progress=cb,
                )
            else:
                if media is None:
                    raise RuntimeError("Không tìm thấy dữ liệu phim nguồn cho dự án.")
                src_video = media.video_path
                orig_stereo = media.original_stereo_wav_path
                audio_sub = await self.audio_mixer.process(
                    clip=clip,
                    profile=voice_profile,
                    audio_config=synced_audio_cfg,
                    out_dir=project_work_dir,
                    orig_stereo_wav=orig_stereo,
                    on_progress=cb,
                    canvas_w=canvas_w,
                    canvas_h=canvas_h,
                    voice_registry=voice_registry,
                )

            self.repo.update_project_state(project_id, JobState.RENDERING_NVENC)
            spec = RenderJobSpecDTO(
                clip=effective_clip,
                source_video_path=src_video,
                visual_assets=visual_assets,
                audio_sub=audio_sub,
                layout_config=effective_layout,
                output_dir=project_out_dir,
                prefer_nvenc=self.settings.prefer_nvenc_gpu,
            )
            rendered = await self.compositor.render(spec, on_progress=cb)
            self.repo.save_render_output(rendered)
            outputs.append(rendered)

            self.repo.update_project_state(project_id, JobState.PACKAGING_SEO)
            seo = await self.brain.build_seo(effective_clip, mode_label=cut_plan.mode.value)
            self.repo.save_seo_package(seo)
            seo_packages.append(seo)

        self._write_seo_text_bundle(project_out_dir, seo_packages)
        self.repo.update_project_state(project_id, JobState.COMPLETED)
        cb(
            "COMPLETED",
            100.0,
            f"Hoàn tất xuất {len(outputs)} video kèm gói SEO tại {project_out_dir.name}!",
        )
        return outputs

    @staticmethod
    def _write_seo_text_bundle(out_dir: Path, packages: List[SEOPackageDTO]) -> None:
        lines: List[str] = ["=== GÓI TIÊU ĐỀ, MÔ TẢ & HASHTAG CHUẨN SEO (SHORTS & TIKTOK) ===\n"]
        for pkg in packages:
            lines.append(f"--- PHẦN {pkg.part_number:02d} (Part_{pkg.part_number:02d}.mp4) ---")
            lines.append(f"[YouTube Shorts - Tiêu đề]: {pkg.yt_shorts_title}")
            lines.append(f"[YouTube Shorts - Mô tả]:\n{pkg.yt_shorts_description}")
            lines.append(f"[YouTube Shorts - Từ khóa]: {', '.join(pkg.yt_shorts_tags)}")
            lines.append(
                f"[TikTok - Caption & Hashtag]:\n{pkg.tiktok_caption}\n{' '.join(pkg.tiktok_hashtags)}\n"
            )
            if pkg.pinned_comment:
                lines.append(f"[Bình luận ghim chốt đơn gợi ý]:\n{pkg.pinned_comment}\n")
        (out_dir / "SEO_TikTok_YouTubeShorts.txt").write_text(
            "\n".join(lines), encoding="utf-8"
        )

