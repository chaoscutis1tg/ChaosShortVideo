"""FastAPI REST & WebSocket Server for ShortVideo Studio AI (Module M07)."""

import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional
import uuid
import zipfile

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFilter
from pydantic import BaseModel, Field

from app.m00_core_contracts import (
    AudioSubConfigDTO,
    BrandKitDTO,
    BriefExpandRequestDTO,
    ClipSpecDTO,
    CopywritingTone,
    CoverTemplateStyle,
    CutConfigDTO,
    CutPlanDTO,
    GPUResourceManager,
    HardsubMaskMode,
    IngestRequestDTO,
    JobState,
    LayoutAndAntiCopyConfigDTO,
    NarrationLineDTO,
    ProductCategory,
    ProductFramingStyle,
    ProductReviewPromptDTO,
    ProjectMode,
    SalesScriptAngle,
    SavedProductTemplateDTO,
    SourceType,
    SQLiteRepository,
    SUPPORTED_VIDEO_EXTENSIONS,
    StudioSettings,
    SubtitleStyle,
    TopicPromptDTO,
    TransitionStyle,
    VisualMode,
    VoiceProfileDTO,
    VoiceTier,
    VoiceUseCaseCategory,
    get_settings,
    resolve_aspect_dimensions,
)
from app.m01_media_ingest import (
    FFmpegMediaIngestor,
    FFmpegMediaTrimmer,
    ProductWebScraper,
    YtDlpDownloader,
    normalize_video_url,
)
from app.m02_asr_transcription import FasterWhisperTranscriber
from app.m03_ai_content_brain import (
    FreeVietnameseTranslator,
    GeminiContentBrainService,
    TikTokShopComplianceChecker,
)
from app.m04_visual_producer import ProductPhotoShowcaseProvider, VisualProducerFacade
from app.m05_voice_audio_mixer import (
    F5VoiceCloneGPUProvider,
    MovieAudioAndSubMixer,
    StudioBGMLibrary,
    TTSProviderFactory,
)
from app.m06_nvenc_compositor import FFmpegNVENCCompositor, StudioOverlayArtist

from .job_manager import JobExecutionManager
from .orchestrator import PipelineOrchestrator
from .progress_hub import WebSocketProgressHub


# ============================================================================
# API Request Schemas
# ============================================================================


class TopicStartRequest(BaseModel):
    topic_title: str = Field(min_length=3, max_length=200)
    key_points: str = ""
    visual_mode: VisualMode = VisualMode.AI_IMAGE
    target_duration_sec: int = Field(default=90, ge=15, le=180)
    part_count: int = Field(default=1, ge=1, le=20)
    narrative_tone: str = "cuốn hút, kịch tính kiểu kể chuyện Shorts/TikTok"
    voice_profile_id: str = "edge_nam_minh_movie"
    subtitle_style: SubtitleStyle = SubtitleStyle.KARAOKE_CAPCUT
    bgm_preset_id: Optional[str] = "bgm_lofi_story"
    custom_bgm_path: Optional[str] = None
    bgm_volume: float = 0.08
    layout_config: LayoutAndAntiCopyConfigDTO = Field(
        default_factory=LayoutAndAntiCopyConfigDTO
    )
    parent_group_id: Optional[str] = None
    auto_one_click: bool = True


class MovieStartRequest(BaseModel):
    project_name: str = Field(min_length=2, max_length=150)
    source_type: SourceType = SourceType.LOCAL_FILE
    path_or_url: str = Field(min_length=1)
    external_srt_path: Optional[str] = None
    source_language: str = "auto"
    cut_config: CutConfigDTO = Field(default_factory=CutConfigDTO)
    voice_profile_id: str = "edge_nam_minh_movie"
    bgm_preset_id: Optional[str] = None
    custom_bgm_path: Optional[str] = None
    audio_config: AudioSubConfigDTO = Field(default_factory=AudioSubConfigDTO)
    layout_config: LayoutAndAntiCopyConfigDTO = Field(
        default_factory=LayoutAndAntiCopyConfigDTO
    )
    parent_group_id: Optional[str] = None
    auto_one_click: bool = True


class ProductStartRequest(BaseModel):
    product_name: str = Field(min_length=2, max_length=200)
    product_category: ProductCategory = ProductCategory.MUSICAL_INSTRUMENT
    sales_angle: SalesScriptAngle = SalesScriptAngle.EXPERT_SPEC_REVIEW
    copywriting_tone: CopywritingTone = CopywritingTone.ARTISAN_STORYTELLER
    variant_count: int = Field(default=1, ge=1, le=4)
    raw_description: str = Field(default="", max_length=6000)
    image_paths: List[str] = Field(min_length=1)
    photo_notes: List[str] = Field(default_factory=list)
    feedback_image_paths: List[str] = Field(default_factory=list)
    comparison_enabled: bool = False
    comparison_left_label: str = "Phiên bản A"
    comparison_right_label: str = "Phiên bản B"
    demo_clip_path: Optional[str] = None
    target_duration_sec: int = Field(default=55, ge=15, le=180)
    call_to_action: str = (
        "Nhắn trực tiếp cho cửa hàng hoặc để lại bình luận để nhận video test thực tế và ưu đãi hôm nay."
    )
    voice_profile_id: str = "edge_nam_nghe_nhan"
    voice_speed_global: Optional[float] = None
    voice_pitch_global: Optional[float] = None
    subtitle_style: SubtitleStyle = SubtitleStyle.CINEMA
    bgm_preset_id: Optional[str] = "bgm_luxury_acoustic"
    custom_bgm_path: Optional[str] = None
    bgm_volume: float = 0.06
    layout_config: LayoutAndAntiCopyConfigDTO = Field(
        default_factory=LayoutAndAntiCopyConfigDTO
    )
    parent_group_id: Optional[str] = None
    auto_one_click: bool = True


class ComplianceCheckRequest(BaseModel):
    text: str = Field(default="", max_length=8000)


class ProjectGroupSaveRequest(BaseModel):
    group_id: Optional[str] = None
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=600)
    color_tag: str = Field(default="#0ea5e9", max_length=24)


class ProjectGroupAssignRequest(BaseModel):
    group_id: Optional[str] = None


class BriefExpandAPIRequest(BaseModel):
    mode: ProjectMode = ProjectMode.TOPIC_VIDEO
    raw_title: str = Field(default="", max_length=250)
    short_brief: str = Field(default="", max_length=4000)
    product_category: ProductCategory = ProductCategory.MUSICAL_INSTRUMENT
    target_duration_sec: int = Field(default=75, ge=15, le=180)
    part_count: int = Field(default=1, ge=1, le=20)


class ProductTemplateSaveRequest(BaseModel):
    template_id: Optional[str] = None
    product_name: str = Field(min_length=2, max_length=200)
    product_category: ProductCategory = ProductCategory.MUSICAL_INSTRUMENT
    raw_description: str = Field(default="", max_length=6000)
    call_to_action: str = ""
    offer_badge: str = ""
    contact_badge: str = ""
    qr_code_content: str = ""


class ApprovedClipLinePatch(BaseModel):
    seq_index: int
    rel_start_ms: int
    rel_end_ms: int
    original_text: str = ""
    vi_text: str
    image_prompt: str = ""
    stock_keywords: List[str] = Field(default_factory=list)
    matched_image_index: Optional[int] = None
    is_real_demo_slot: bool = False
    callout_label: str = ""
    voice_speed_override: Optional[float] = None
    voice_pitch_override: Optional[float] = None


class ApprovedClipPatch(BaseModel):
    clip_id: str
    part_number: int
    source_start_ms: int
    source_end_ms: int
    hook_banner_title: str
    append_cta_outro: bool = True
    lines: List[ApprovedClipLinePatch]


class RenderApprovedRequest(BaseModel):
    voice_profile_id: str = "edge_nam_minh_movie"
    visual_mode: VisualMode = VisualMode.AI_IMAGE
    bgm_preset_id: Optional[str] = None
    custom_bgm_path: Optional[str] = None
    audio_config: AudioSubConfigDTO = Field(default_factory=AudioSubConfigDTO)
    layout_config: LayoutAndAntiCopyConfigDTO = Field(
        default_factory=LayoutAndAntiCopyConfigDTO
    )
    clips: Optional[List[ApprovedClipPatch]] = None
    selected_part_numbers: Optional[List[int]] = None
    image_paths_override: Optional[List[str]] = None


class APIKeysUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    fpt_ai_api_key: Optional[str] = None


class GPUSelectRequest(BaseModel):
    device_id: str = Field(default="auto")


class VoicePreviewRequest(BaseModel):
    profile_id: str
    sample_text: str = "Không ai ngờ người đàn ông trầm lặng này lại chính là chủ tịch tập đoàn!"
    speed_rate: Optional[float] = None
    pitch_hz: Optional[float] = None


class YouTubeVoiceCloneRequest(BaseModel):
    youtube_url: str = Field(min_length=8)
    display_name: str = Field(min_length=2, max_length=120)
    start_sec: float = Field(default=5.0, ge=0.0, le=14400.0)
    duration_sec: float = Field(default=15.0, ge=6.0, le=24.0)
    category: VoiceUseCaseCategory = VoiceUseCaseCategory.MOVIE_DUB
    dialect_hint: str = Field(default="auto")
    speed_rate: float = Field(default=1.02, ge=0.80, le=1.40)
    sample_ref_text: str = Field(default="")


class URLProbeRequest(BaseModel):
    url: str = Field(min_length=4)


class CutoutPreviewRequest(BaseModel):
    local_path: str = Field(min_length=2)


class BrandKitSaveRequest(BaseModel):
    brand_name: str = ""
    logo_path: Optional[str] = None
    logo_pos_x: float = 0.04
    logo_pos_y: float = 0.04
    showroom_address: str = ""
    hotline_or_web: str = ""
    qr_code_content: str = ""
    qr_code_label: str = "Quét xem chi tiết"
    subtitle_pos_y: float = 0.84
    subtitle_font_size: int = 52
    outro_card_enabled: bool = False
    preferred_framing: ProductFramingStyle = ProductFramingStyle.BLURRED_STUDIO_CARD
    preferred_transition: TransitionStyle = TransitionStyle.CAPCUT_DISSOLVE
    preferred_voice_id: str = "edge_nam_nghe_nhan"
    preferred_bgm_id: Optional[str] = "bgm_luxury_acoustic"


class MediaTrimRequest(BaseModel):
    local_path: str = Field(min_length=2)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class TrueFrameSnapshotRequest(BaseModel):
    active_tab: str = "product"
    sample_media_path: Optional[str] = None
    sample_media_url: Optional[str] = None
    banner_title: str = "Đàn Violin Gỗ Thịt Tự Nhiên"
    sample_subtitle: str = "Mặt đàn gỗ thịt tự nhiên nguyên tấm cho âm vang dày và ấm."
    preview_as_cover: bool = False
    layout_config: LayoutAndAntiCopyConfigDTO = Field(
        default_factory=LayoutAndAntiCopyConfigDTO
    )


class ProductBatchUrlsRequest(BaseModel):
    urls: List[str] = Field(min_length=1, max_length=20)
    product_category: ProductCategory = ProductCategory.MUSICAL_INSTRUMENT
    copywriting_tone: CopywritingTone = CopywritingTone.ARTISAN_STORYTELLER
    diversify_angles: bool = True
    target_duration_sec: int = Field(default=55, ge=15, le=180)
    call_to_action: str = (
        "Nhắn trực tiếp cho cửa hàng hoặc để lại bình luận để nhận video test thực tế và ưu đãi hôm nay."
    )
    voice_profile_id: str = "edge_nam_nghe_nhan"
    voice_speed_global: Optional[float] = None
    voice_pitch_global: Optional[float] = None
    subtitle_style: SubtitleStyle = SubtitleStyle.CINEMA
    bgm_preset_id: Optional[str] = "bgm_luxury_acoustic"
    custom_bgm_path: Optional[str] = None
    bgm_volume: float = 0.06
    layout_config: LayoutAndAntiCopyConfigDTO = Field(
        default_factory=LayoutAndAntiCopyConfigDTO
    )
    auto_one_click: bool = True


# ============================================================================
# Application Factory (Dependency Injection Ready for Testing & Production)
# ============================================================================


def create_studio_app(custom_settings: Optional[StudioSettings] = None) -> FastAPI:
    """Instantiate FastAPI application wired with all modular services."""
    settings = custom_settings or get_settings()
    settings.ensure_directories()
    bgm_dir = settings.assets_dir / "bgm"
    StudioBGMLibrary.ensure_builtin_tracks(bgm_dir)

    repo = SQLiteRepository(settings.sqlite_db_path)
    hub = WebSocketProgressHub()
    gpu_mgr = GPUResourceManager()
    job_mgr = JobExecutionManager(settings=settings, repo=repo, hub=hub)

    def _build_orchestrator() -> PipelineOrchestrator:
        return PipelineOrchestrator(
            settings=settings,
            repo=repo,
            progress_hub=hub,
            ingestor=FFmpegMediaIngestor(),
            transcriber=FasterWhisperTranscriber(
                model_size=settings.whisper_model_size,
                compute_type=settings.whisper_compute_type,
                gpu_manager=gpu_mgr,
            ),
            brain=GeminiContentBrainService(
                api_key=settings.gemini_api_key,
                model_name=settings.gemini_model,
                allow_offline_fallback=True,
            ),
            visual_producer=VisualProducerFacade(
                pexels_api_key=settings.pexels_api_key,
                pixabay_api_key=settings.pixabay_api_key,
            ),
            audio_mixer=MovieAudioAndSubMixer(tts_factory=TTSProviderFactory()),
            compositor=FFmpegNVENCCompositor(gpu_manager=gpu_mgr),
            job_manager=job_mgr,
        )

    orchestrator = _build_orchestrator()

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        hub.bind_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(
        title="ChaosShortVideo API",
        version="3.0.0",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/media/outputs", StaticFiles(directory=str(settings.outputs_dir)), name="outputs")
    app.mount("/media/work", StaticFiles(directory=str(settings.work_dir)), name="work")
    app.mount("/media/assets", StaticFiles(directory=str(settings.assets_dir)), name="assets")

    def _to_media_url(path_str: str) -> str:
        if not path_str:
            return ""
        p = Path(path_str).resolve()
        for prefix, root in (
            ("/media/outputs", settings.outputs_dir.resolve()),
            ("/media/work", settings.work_dir.resolve()),
            ("/media/assets", settings.assets_dir.resolve()),
        ):
            try:
                rel = p.relative_to(root)
                return f"{prefix}/{rel.as_posix()}"
            except ValueError:
                continue
        return ""

    def _resolve_bgm_into_audio_cfg(
        audio_cfg: AudioSubConfigDTO,
        bgm_preset_id: Optional[str],
        custom_bgm_path: Optional[str] = None,
    ) -> AudioSubConfigDTO:
        if custom_bgm_path and Path(custom_bgm_path).exists():
            return audio_cfg.model_copy(update={"bgm_path": Path(custom_bgm_path)})
        if audio_cfg.bgm_path and audio_cfg.bgm_path.exists():
            return audio_cfg
        resolved = StudioBGMLibrary.resolve_bgm_path(bgm_dir, bgm_preset_id)
        if resolved is not None:
            return audio_cfg.model_copy(update={"bgm_path": resolved})
        return audio_cfg

    def _discover_lan_urls(port: int = 8000) -> List[str]:
        """Return reachable LAN URLs (e.g. http://192.168.1.200:8000) excluding WSL/loopback."""
        candidates: List[str] = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                primary_ip = s.getsockname()[0]
                if primary_ip and not primary_ip.startswith("127."):
                    candidates.append(primary_ip)
        except OSError:
            pass
        try:
            _, _, ips = socket.gethostbyname_ex(socket.gethostname())
            for ip in ips:
                if ip.startswith(("192.168.", "10.")) and ip not in candidates:
                    candidates.append(ip)
        except OSError:
            pass
        return [f"http://{ip}:{port}" for ip in candidates]

    @app.get("/api/system/status")
    async def get_system_status() -> Dict[str, Any]:
        gpus = [g.model_dump() for g in gpu_mgr.list_gpu_adapters()]
        nvenc_ok = gpu_mgr.is_nvenc_available()
        return {
            "cuda_available": gpu_mgr.is_cuda_available(),
            "nvenc_available": nvenc_ok,
            "encoder_note": gpu_mgr.encoder_diagnostic_note,
            "preferred_device": gpu_mgr.preferred_device,
            "gpus": gpus,
            "lan_urls": _discover_lan_urls(8000),
            "active_gpu_owner": gpu_mgr.active_owner,
            "whisper_model": settings.whisper_model_size,
            "outputs_dir": str(settings.outputs_dir),
            "storage": job_mgr.inspect_storage(),
            "keys_configured": {
                "gemini": bool(settings.gemini_api_key),
                "pexels": bool(settings.pexels_api_key),
                "pixabay": bool(settings.pixabay_api_key),
                "elevenlabs": bool(settings.elevenlabs_api_key),
                "fpt_ai": bool(settings.fpt_ai_api_key),
            },
        }

    @app.post("/api/system/gpu-select")
    async def select_gpu_device(req: GPUSelectRequest) -> Dict[str, Any]:
        """Switch target compute device ('auto', 'cuda:0', 'cuda:1', 'cpu')."""
        chosen = gpu_mgr.set_preferred_device(req.device_id)
        settings.prefer_nvenc_gpu = chosen != "cpu"
        return await get_system_status()

    @app.post("/api/system/cleanup-temp")
    async def cleanup_temp_workspace() -> Dict[str, Any]:
        """Free disk space by cleaning temporary scratch files of finished/cancelled projects."""
        return job_mgr.cleanup_temp_files()

    @app.post("/api/system/settings")
    async def update_api_keys(req: APIKeysUpdateRequest) -> Dict[str, Any]:
        nonlocal orchestrator
        env_path = settings.workspace_root / ".env"
        existing: Dict[str, str] = {}
        if env_path.exists():
            for ln in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in ln and not ln.strip().startswith("#"):
                    k, v = ln.split("=", 1)
                    existing[k.strip()] = v.strip()

        updates = {
            "GEMINI_API_KEY": req.gemini_api_key,
            "PEXELS_API_KEY": req.pexels_api_key,
            "PIXABAY_API_KEY": req.pixabay_api_key,
            "ELEVENLABS_API_KEY": req.elevenlabs_api_key,
            "FPT_AI_API_KEY": req.fpt_ai_api_key,
        }
        for env_key, val in updates.items():
            if val is not None:
                clean_v = val.strip()
                existing[env_key] = clean_v
                os.environ[env_key] = clean_v

        settings.gemini_api_key = existing.get("GEMINI_API_KEY", settings.gemini_api_key)
        settings.pexels_api_key = existing.get("PEXELS_API_KEY", settings.pexels_api_key)
        settings.pixabay_api_key = existing.get("PIXABAY_API_KEY", settings.pixabay_api_key)
        settings.elevenlabs_api_key = existing.get("ELEVENLABS_API_KEY", settings.elevenlabs_api_key)
        settings.fpt_ai_api_key = existing.get("FPT_AI_API_KEY", settings.fpt_ai_api_key)

        env_lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        orchestrator = _build_orchestrator()
        return await get_system_status()

    @app.get("/api/bgm")
    async def list_bgm_presets() -> List[Dict[str, Any]]:
        """List built-in copyright-free studio BGM tracks with preview URLs."""
        presets = StudioBGMLibrary.ensure_builtin_tracks(bgm_dir)
        out: List[Dict[str, Any]] = []
        for p in presets:
            d = p.model_dump()
            d["wav_path"] = str(p.wav_path)
            d["audio_url"] = _to_media_url(str(p.wav_path))
            out.append(d)
        return out

    def _serialize_voice_profile(v: VoiceProfileDTO) -> Dict[str, Any]:
        d = v.model_dump()
        if v.tier == VoiceTier.LOCAL_F5_CLONE and v.voice_id_or_sample_path:
            sp = Path(v.voice_id_or_sample_path)
            if sp.exists():
                d["sample_audio_url"] = _to_media_url(str(sp))
        return d

    async def _auto_transcribe_reference_wav(norm_wav: Path, vid: str) -> str:
        """Convert 24kHz sample WAV to 16kHz mono and run M02 GPU/CPU Whisper to extract exact Vietnamese text."""
        wav_16k = norm_wav.with_name(f"{vid}_16k_tmp.wav")
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(norm_wav),
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(wav_16k),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0 or not wav_16k.exists():
                return ""
            from app.m00_core_contracts import MediaAssetDTO

            dummy_media = MediaAssetDTO(
                media_id=f"vc_{vid}",
                project_id=f"vc_{vid}",
                video_path=norm_wav,
                audio_16k_wav_path=wav_16k,
                duration_ms=15000,
                width=1080,
                height=1920,
                fps=30.0,
            )
            tr = await orchestrator.transcriber.transcribe(dummy_media, lang_hint="vi")
            joined = " ".join(s.text.strip() for s in tr.segments if s.text.strip()).strip()
            return joined
        except Exception:
            return ""
        finally:
            wav_16k.unlink(missing_ok=True)

    @app.get("/api/voices")
    async def list_voices() -> List[Dict[str, Any]]:
        return [_serialize_voice_profile(v) for v in repo.list_voice_profiles()]

    @app.post("/api/voices/preview")
    async def preview_voice(req: VoicePreviewRequest) -> Dict[str, str]:
        prof = repo.get_voice_profile(req.profile_id)
        if prof is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ giọng đọc.")
        updates: Dict[str, Any] = {}
        if req.speed_rate is not None:
            updates["speed_rate"] = float(req.speed_rate)
        if req.pitch_hz is not None:
            updates["pitch_hz"] = float(req.pitch_hz)
        eff_prof = prof.model_copy(update=updates) if updates else prof
        preview_dir = settings.work_dir / "_voice_previews"
        tag = f"{eff_prof.speed_rate:.2f}_{eff_prof.pitch_hz:.1f}".replace("-", "m").replace(".", "d")
        out_wav = preview_dir / f"preview_{eff_prof.profile_id}_{tag}.wav"
        provider = TTSProviderFactory().get_provider(eff_prof.tier)
        await provider.synthesize(req.sample_text, eff_prof, out_wav)
        return {"audio_url": _to_media_url(str(out_wav))}

    @app.post("/api/voices/clone-sample")
    async def register_cloned_voice(
        display_name: str = Form(...),
        sample_ref_text: str = Form(default=""),
        speed_rate: float = Form(default=1.04),
        category: str = Form(default="MOVIE_DUB"),
        dialect_hint: str = Form(default="auto"),
        sample_file: UploadFile = File(...),
    ) -> Dict[str, Any]:
        vid = f"clone_{uuid.uuid4().hex[:8]}"
        safe_ext = Path(sample_file.filename or "sample.wav").suffix or ".wav"
        raw_path = settings.assets_dir / "voice_samples" / f"{vid}_raw{safe_ext}"
        norm_wav = settings.assets_dir / "voice_samples" / f"{vid}_24k.wav"
        raw_path.parent.mkdir(parents=True, exist_ok=True)

        with open(raw_path, "wb") as f_out:
            shutil.copyfileobj(sample_file.file, f_out)

        try:
            await asyncio.to_thread(
                F5VoiceCloneGPUProvider.prepare_reference_sample, raw_path, norm_wav, 0.0, 16.0
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            raw_path.unlink(missing_ok=True)

        ref_txt = sample_ref_text.strip()
        if not ref_txt:
            ref_txt = await _auto_transcribe_reference_wav(norm_wav, vid)

        analysis = await asyncio.to_thread(
            F5VoiceCloneGPUProvider.analyze_voice_sample, norm_wav, ref_txt, dialect_hint
        )
        try:
            cat_enum = VoiceUseCaseCategory(category)
        except ValueError:
            cat_enum = VoiceUseCaseCategory.MOVIE_DUB

        profile = VoiceProfileDTO(
            profile_id=vid,
            display_name=f"{display_name.strip()} (Giọng Thu Mẫu)",
            tier=VoiceTier.LOCAL_F5_CLONE,
            category=cat_enum,
            tags=list(analysis.get("tags") or ["Giọng thu mẫu"]),  # type: ignore[arg-type]
            voice_id_or_sample_path=str(norm_wav),
            sample_ref_text=ref_txt,
            speed_rate=speed_rate,
            pitch_hz=0.0,
            emotion_prompt=str(analysis.get("emotion_prompt") or ""),
            dsp_preset=str(analysis.get("dsp_preset") or "cinema_uslt_female"),
        )
        repo.upsert_voice_profile(profile)
        return _serialize_voice_profile(profile)

    @app.post("/api/voices/clone-youtube")
    async def register_cloned_voice_from_youtube(req: YouTubeVoiceCloneRequest) -> Dict[str, Any]:
        """Download a clean 10–20s narrator segment directly from YouTube, auto-transcribe & build GPU Clone profile."""
        import sys

        clean_url = normalize_video_url(req.youtube_url.strip())
        vid = f"ytclone_{uuid.uuid4().hex[:8]}"
        samples_dir = settings.assets_dir / "voice_samples"
        samples_dir.mkdir(parents=True, exist_ok=True)
        out_tpl = str(samples_dir / f"{vid}_raw.%(ext)s")
        norm_wav = samples_dir / f"{vid}_24k.wav"

        s_sec = max(0.0, float(req.start_sec))
        e_sec = s_sec + max(6.0, min(24.0, float(req.duration_sec)))

        def _download_yt_slice() -> Path:
            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--no-playlist",
                "-f",
                "bestaudio/best",
                "--download-sections",
                f"*{s_sec:.1f}-{e_sec:.1f}",
                "--force-keyframes-at-cuts",
                "-x",
                "--audio-format",
                "wav",
                "-o",
                out_tpl,
                clean_url,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
            matches = list(samples_dir.glob(f"{vid}_raw.*"))
            if proc.returncode != 0 or not matches:
                err_msg = (proc.stderr or proc.stdout or "").strip()[-320:]
                raise RuntimeError(f"Không thể tải đoạn giọng mẫu từ YouTube: {err_msg}")
            return matches[0]

        raw_dl: Optional[Path] = None
        try:
            raw_dl = await asyncio.to_thread(_download_yt_slice)
            await asyncio.to_thread(
                F5VoiceCloneGPUProvider.prepare_reference_sample,
                raw_dl,
                norm_wav,
                0.0,
                req.duration_sec,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            for leftover in samples_dir.glob(f"{vid}_raw.*"):
                leftover.unlink(missing_ok=True)

        ref_txt = req.sample_ref_text.strip()
        if not ref_txt:
            ref_txt = await _auto_transcribe_reference_wav(norm_wav, vid)

        analysis = await asyncio.to_thread(
            F5VoiceCloneGPUProvider.analyze_voice_sample, norm_wav, ref_txt, req.dialect_hint
        )
        profile = VoiceProfileDTO(
            profile_id=vid,
            display_name=f"{req.display_name.strip()} (Trích Mẫu YouTube)",
            tier=VoiceTier.LOCAL_F5_CLONE,
            category=req.category,
            tags=["Mẫu YouTube", *list(analysis.get("tags") or [])[1:]],  # type: ignore[misc]
            voice_id_or_sample_path=str(norm_wav),
            sample_ref_text=ref_txt,
            speed_rate=req.speed_rate,
            pitch_hz=0.0,
            emotion_prompt=str(analysis.get("emotion_prompt") or ""),
            dsp_preset=str(analysis.get("dsp_preset") or "cinema_uslt_female"),
        )
        repo.upsert_voice_profile(profile)
        return _serialize_voice_profile(profile)

    @app.post("/api/media/probe-url")
    async def probe_remote_video_url(req: URLProbeRequest) -> Dict[str, Any]:
        """Normalize pasted video URL and return title, duration, and thumbnail preview."""
        try:
            downloader = YtDlpDownloader()
            return await downloader.probe_url_info(req.url)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/uploads/file")
    async def upload_studio_file(
        category: str = Form(default="video"),
        file: UploadFile = File(...),
    ) -> Dict[str, Any]:
        """Upload local video, .srt subtitle, BGM, or channel watermark PNG."""
        target_folder = (
            settings.assets_dir / "logos"
            if category == "logo"
            else settings.work_dir / "_uploads"
        )
        target_folder.mkdir(parents=True, exist_ok=True)
        orig_name = Path(file.filename or "upload.mp4").name
        ext = Path(orig_name).suffix.lower() or ".mp4"
        safe_name = f"up_{uuid.uuid4().hex[:10]}{ext}"
        dest = target_folder / safe_name
        with open(dest, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)
        return {
            "local_path": str(dest),
            "original_name": orig_name,
            "media_url": _to_media_url(str(dest)),
            "duration_ms": await asyncio.to_thread(FFmpegMediaTrimmer.probe_duration_ms, dest),
        }

    @app.post("/api/uploads/batch")
    async def upload_batch_studio_files(
        category: str = Form(default="product_photo"),
        files: List[UploadFile] = File(...),
    ) -> List[Dict[str, Any]]:
        """Upload multiple product photos or close-up clips at once."""
        target_folder = settings.work_dir / "_uploads" / category
        target_folder.mkdir(parents=True, exist_ok=True)
        uploaded: List[Dict[str, Any]] = []
        for idx, up_f in enumerate(files):
            orig_name = Path(up_f.filename or f"photo_{idx + 1}.jpg").name
            ext = Path(orig_name).suffix.lower() or ".jpg"
            safe_name = f"prod_{uuid.uuid4().hex[:10]}{ext}"
            dest = target_folder / safe_name
            with open(dest, "wb") as f_out:
                shutil.copyfileobj(up_f.file, f_out)
            dur_ms = await asyncio.to_thread(FFmpegMediaTrimmer.probe_duration_ms, dest)
            uploaded.append(
                {
                    "local_path": str(dest),
                    "original_name": orig_name,
                    "media_url": _to_media_url(str(dest)),
                    "duration_ms": dur_ms,
                }
            )
        return uploaded

    def _resolve_media_ref(url_or_path: Optional[str]) -> Optional[Path]:
        if not url_or_path:
            return None
        clean = url_or_path.split("?", 1)[0].strip()
        if not clean:
            return None
        for prefix, root in (
            ("/media/outputs/", settings.outputs_dir.resolve()),
            ("/media/work/", settings.work_dir.resolve()),
            ("/media/assets/", settings.assets_dir.resolve()),
        ):
            if clean.startswith(prefix):
                rel = clean[len(prefix) :].lstrip("/")
                cand = (root / rel).resolve()
                if cand.exists() and cand.is_file():
                    return cand
        direct = Path(clean)
        if direct.exists() and direct.is_file():
            return direct
        return None

    @app.post("/api/media/trim")
    async def trim_uploaded_media_highlight(req: MediaTrimRequest) -> Dict[str, Any]:
        """Trim `[start_ms, end_ms]` highlight segment from an uploaded demo audio or video clip."""
        src_p = _resolve_media_ref(req.local_path)
        if src_p is None or not src_p.exists():
            raise HTTPException(status_code=404, detail="Không tìm thấy tệp gốc để cắt đoạn.")
        trim_dir = settings.work_dir / "_uploads" / "trimmed"
        try:
            use_nvenc = settings.prefer_nvenc_gpu and gpu_mgr.is_nvenc_available()
            res = await asyncio.to_thread(
                FFmpegMediaTrimmer.trim_segment,
                src_p,
                trim_dir,
                req.start_ms,
                req.end_ms,
                use_nvenc,
            )
            return {
                "local_path": str(res.output_path),
                "original_name": res.output_path.name,
                "media_url": _to_media_url(str(res.output_path)),
                "duration_ms": res.duration_ms,
                "start_ms": res.start_ms,
                "end_ms": res.end_ms,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/system/lan-qr")
    async def get_lan_mobile_qr_png(url: Optional[str] = None) -> Response:
        """Generate a high-contrast PNG QR code so phones on Wi-Fi open ChaosShortVideo instantly."""
        import qrcode  # type: ignore

        lan_list = _discover_lan_urls(8000)
        target_url = (url or "").strip() or (
            lan_list[0] if lan_list else "http://127.0.0.1:8000"
        )
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(target_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#0f172a", back_color="#ffffff").convert("RGB")
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")

    @app.get("/api/system/backup-export")
    async def export_store_backup_zip() -> FileResponse:
        """Package Brand Kit, Logo, Product Templates & Cloned Voices into a portable .zip backup."""
        backup_dir = settings.work_dir / "_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        zip_path = backup_dir / "ChaosShortVideo_StoreBackup.zip"
        manifest = repo.export_store_catalog_bundle()

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            logos_dir = settings.assets_dir / "logos"
            if logos_dir.exists():
                for lg in logos_dir.iterdir():
                    if lg.is_file():
                        zf.write(lg, arcname=f"logos/{lg.name}")
            samples_dir = settings.assets_dir / "voice_samples"
            if samples_dir.exists():
                for vs in samples_dir.iterdir():
                    if vs.is_file():
                        zf.write(vs, arcname=f"voice_samples/{vs.name}")

        return FileResponse(
            path=str(zip_path),
            media_type="application/zip",
            filename="ChaosShortVideo_StoreBackup.zip",
        )

    @app.post("/api/system/backup-import")
    async def import_store_backup_zip(file: UploadFile = File(...)) -> Dict[str, Any]:
        """Restore Brand Kit, Logo, Product Templates & Cloned Voices from a .zip backup."""
        raw_bytes = await file.read()
        try:
            with zipfile.ZipFile(BytesIO(raw_bytes), "r") as zf:
                if "manifest.json" not in zf.namelist():
                    raise HTTPException(
                        status_code=400,
                        detail="Tệp sao lưu không hợp lệ (thiếu manifest.json).",
                    )
                for member in zf.namelist():
                    if member.startswith("logos/") and not member.endswith("/"):
                        safe_name = Path(member).name
                        if safe_name:
                            dst = settings.assets_dir / "logos" / safe_name
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            dst.write_bytes(zf.read(member))
                    elif member.startswith("voice_samples/") and not member.endswith("/"):
                        safe_name = Path(member).name
                        if safe_name:
                            dst = settings.assets_dir / "voice_samples" / safe_name
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            dst.write_bytes(zf.read(member))
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Lỗi đọc tệp sao lưu: {exc}") from exc

        counts = repo.import_store_catalog_bundle(manifest, settings.assets_dir)
        return {"status": "ok", **counts}

    @app.post("/api/preview/render-frame")
    async def render_true_compositor_frame_snapshot(req: TrueFrameSnapshotRequest) -> Dict[str, Any]:
        """Render a true 1080p still snapshot through M04 + M06 (cutout, blur, overlays, ASS subtitle or Cover)."""
        t0 = time.perf_counter()
        cfg = req.layout_config
        canvas_w, canvas_h = resolve_aspect_dimensions(cfg.aspect_ratio)
        snap_dir = settings.work_dir / "_frame_previews"
        snap_dir.mkdir(parents=True, exist_ok=True)
        uid = uuid.uuid4().hex[:10]
        plate_png = snap_dir / f"plate_{uid}.png"
        ovr_png = snap_dir / f"ovr_{uid}.png"
        out_jpg = snap_dir / f"true_frame_{uid}.jpg"

        src_media = _resolve_media_ref(req.sample_media_path or req.sample_media_url)

        def _build_snapshot_sync() -> None:
            # 1. Build base visual plate
            if (
                src_media is not None
                and src_media.exists()
                and src_media.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS
            ):
                if req.active_tab == "movie":
                    with Image.open(src_media) as im_raw:
                        rgb_m = im_raw.convert("RGB")
                        if cfg.hardsub_mask_enabled:
                            r = cfg.hardsub_rect
                            mx0 = int(rgb_m.width * r.x)
                            my0 = int(rgb_m.height * r.y)
                            mx1 = min(rgb_m.width, int(rgb_m.width * (r.x + r.w)))
                            my1 = min(rgb_m.height, int(rgb_m.height * (r.y + r.h)))
                            if mx1 > mx0 + 4 and my1 > my0 + 4:
                                if r.mode == HardsubMaskMode.DARK_BOX:
                                    md = ImageDraw.Draw(rgb_m)
                                    md.rectangle([(mx0, my0), (mx1, my1)], fill=(8, 10, 14))
                                else:
                                    crop = rgb_m.crop((mx0, my0, mx1, my1)).filter(
                                        ImageFilter.GaussianBlur(radius=14)
                                    )
                                    rgb_m.paste(crop, (mx0, my0))
                        bg = rgb_m.resize((canvas_w, canvas_h)).filter(
                            ImageFilter.GaussianBlur(radius=24)
                        )
                        dark = Image.new("RGBA", (canvas_w, canvas_h), (6, 9, 15, 115))
                        base_c = Image.alpha_composite(bg.convert("RGBA"), dark)
                        sc = min(canvas_w / max(rgb_m.width, 1), (canvas_h * 0.62) / max(rgb_m.height, 1))
                        fw = max(1, int(rgb_m.width * sc))
                        fh = max(1, int(rgb_m.height * sc))
                        fg_m = rgb_m.resize((fw, fh), Image.Resampling.LANCZOS).convert("RGBA")
                        base_c.alpha_composite(fg_m, ((canvas_w - fw) // 2, (canvas_h - fh) // 2))
                        base_c.save(plate_png, format="PNG")
                else:
                    ProductPhotoShowcaseProvider.compose_uncropped_plate(
                        src_img=src_media,
                        dst_png=plate_png,
                        callout_label="Gỗ thịt tự nhiên" if cfg.show_photo_callouts else "",
                        framing_style=cfg.product_framing,
                        canvas_w=canvas_w,
                        canvas_h=canvas_h,
                        studio_cutout_enabled=cfg.studio_cutout_enabled,
                    )
            else:
                # Sample studio card when no photo is uploaded yet
                sample = Image.new("RGBA", (canvas_w, canvas_h), (14, 18, 26, 255))
                glow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                gd = ImageDraw.Draw(glow)
                r_g = int(min(canvas_w, canvas_h) * 0.42)
                gd.ellipse(
                    [
                        (canvas_w // 2 - r_g, canvas_h // 2 - r_g),
                        (canvas_w // 2 + r_g, canvas_h // 2 + r_g),
                    ],
                    fill=(146, 92, 38, 110),
                )
                sample = Image.alpha_composite(sample, glow.filter(ImageFilter.GaussianBlur(radius=85)))
                sd = ImageDraw.Draw(sample)
                cw_card = int(canvas_w * 0.72)
                ch_card = int(canvas_h * 0.50)
                cx0 = (canvas_w - cw_card) // 2
                cy0 = (canvas_h - ch_card) // 2 - 20
                sd.rounded_rectangle(
                    [(cx0, cy0), (cx0 + cw_card, cy0 + ch_card)],
                    radius=32,
                    fill=(30, 41, 59, 235),
                    outline=(212, 175, 55, 180),
                    width=3,
                )
                sample.save(plate_png, format="PNG")

            # 2. Render true static overlay
            StudioOverlayArtist.create_static_overlay(
                out_png=ovr_png,
                banner_text=req.banner_title,
                show_top_banner=cfg.show_top_banner,
                logo_path=cfg.logo_path,
                logo_pos_x=cfg.logo_pos_x,
                logo_pos_y=cfg.logo_pos_y,
                sales_badge_enabled=cfg.sales_badge_enabled,
                sales_price_or_offer=cfg.sales_price_or_offer,
                sales_contact_info=cfg.sales_contact_info,
                qr_code_content=cfg.qr_code_content,
                qr_code_label=cfg.qr_code_label,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
            )

            with Image.open(plate_png) as bp, Image.open(ovr_png) as ov:
                composed = Image.alpha_composite(bp.convert("RGBA"), ov.convert("RGBA"))

            if req.preview_as_cover:
                eff_head = cfg.cover_headline.strip() or req.banner_title
                composed = StudioOverlayArtist.apply_cover_studio_typography(
                    composed,
                    cover_style=(
                        CoverTemplateStyle.BOLD_HOOK
                        if cfg.cover_style == CoverTemplateStyle.CLEAN_POSTER
                        and not cfg.cover_headline.strip()
                        else cfg.cover_style
                    ),
                    headline=eff_head,
                    badge_text=cfg.cover_badge_text,
                )
            else:
                composed = StudioOverlayArtist.render_sample_subtitle_line(
                    composed,
                    subtitle_text=req.sample_subtitle,
                    pos_y=cfg.subtitle_pos_y,
                    font_size=cfg.subtitle_font_size,
                )

            composed.convert("RGB").save(out_jpg, format="JPEG", quality=93)
            plate_png.unlink(missing_ok=True)
            ovr_png.unlink(missing_ok=True)

        await asyncio.to_thread(_build_snapshot_sync)
        elapsed_ms = int(round((time.perf_counter() - t0) * 1000.0))
        return {
            "image_url": _to_media_url(str(out_jpg)),
            "width": canvas_w,
            "height": canvas_h,
            "elapsed_ms": elapsed_ms,
            "nvenc_active": gpu_mgr.is_nvenc_available(),
        }

    @app.post("/api/product/batch-urls")
    async def start_batch_product_projects_from_urls(
        req: ProductBatchUrlsRequest,
    ) -> Dict[str, Any]:
        """Auto-scrape multiple store product URLs, diversify angles, and enqueue batch rendering."""
        clean_urls: List[str] = []
        seen_u: set[str] = set()
        for raw_u in req.urls:
            u = raw_u.strip()
            if u.startswith(("http://", "https://")) and u not in seen_u:
                seen_u.add(u)
                clean_urls.append(u)

        if not clean_urls:
            raise HTTPException(
                status_code=400,
                detail="Vui lòng dán ít nhất 1 đường dẫn sản phẩm hợp lệ (bắt đầu bằng https://).",
            )

        angle_cycle = [
            SalesScriptAngle.EXPERT_SPEC_REVIEW,
            SalesScriptAngle.BEGINNER_CONSULT,
            SalesScriptAngle.UNBOXING_AND_GIFT,
            SalesScriptAngle.PRICE_COMPARISON_DEAL,
        ]
        created_projects: List[Dict[str, str]] = []
        failed_urls: List[Dict[str, str]] = []

        for idx, url in enumerate(clean_urls):
            batch_sub = settings.work_dir / "_uploads" / f"batch_{uuid.uuid4().hex[:8]}"
            try:
                scraped = await ProductWebScraper.scrape_url(url, batch_sub, max_images=10)
                valid_imgs = [p for p in scraped.downloaded_image_paths if p.exists()]
                if not valid_imgs:
                    failed_urls.append({"url": url, "reason": "Không tìm thấy ảnh sản phẩm trên trang."})
                    continue

                p_name = (scraped.product_name or f"Sản phẩm #{idx + 1}").strip()[:180]
                chosen_angle = (
                    angle_cycle[idx % len(angle_cycle)]
                    if req.diversify_angles
                    else SalesScriptAngle.EXPERT_SPEC_REVIEW
                )
                project_id = f"prd_{uuid.uuid4().hex[:8]}"

                single_req = ProductStartRequest(
                    product_name=p_name,
                    product_category=req.product_category,
                    sales_angle=chosen_angle,
                    copywriting_tone=req.copywriting_tone,
                    variant_count=1,
                    raw_description=scraped.raw_description or p_name,
                    image_paths=[str(p) for p in valid_imgs],
                    target_duration_sec=req.target_duration_sec,
                    call_to_action=req.call_to_action,
                    voice_profile_id=req.voice_profile_id,
                    voice_speed_global=req.voice_speed_global,
                    voice_pitch_global=req.voice_pitch_global,
                    subtitle_style=req.subtitle_style,
                    bgm_preset_id=req.bgm_preset_id,
                    custom_bgm_path=req.custom_bgm_path,
                    bgm_volume=req.bgm_volume,
                    layout_config=req.layout_config,
                    auto_one_click=req.auto_one_click,
                )
                repo.create_project(
                    project_id=project_id,
                    name=p_name,
                    mode=ProjectMode.PRODUCT_SHOWCASE,
                    target_min_sec=max(15, req.target_duration_sec - 15),
                    target_max_sec=min(180, req.target_duration_sec + 20),
                    request_payload_json=single_req.model_dump_json(),
                )
                prompt_dto = ProductReviewPromptDTO(
                    project_id=project_id,
                    product_name=p_name,
                    product_category=req.product_category,
                    sales_angle=chosen_angle,
                    copywriting_tone=req.copywriting_tone,
                    variant_count=1,
                    raw_description=scraped.raw_description or p_name,
                    image_paths=valid_imgs,
                    target_duration_sec=req.target_duration_sec,
                    call_to_action=req.call_to_action,
                )
                audio_cfg = _resolve_bgm_into_audio_cfg(
                    AudioSubConfigDTO(
                        enable_narration=True,
                        keep_original_audio=False,
                        bgm_volume=req.bgm_volume,
                        subtitle_style=req.subtitle_style,
                        subtitle_pos_y=req.layout_config.subtitle_pos_y,
                        subtitle_font_size=req.layout_config.subtitle_font_size,
                        voice_speed_global=req.voice_speed_global,
                        voice_pitch_global=req.voice_pitch_global,
                    ),
                    req.bgm_preset_id,
                    req.custom_bgm_path,
                )
                st = job_mgr.enqueue_job(
                    project_id=project_id,
                    mode=ProjectMode.PRODUCT_SHOWCASE,
                    is_render_only=False,
                    coro_factory=lambda p_dto=prompt_dto, a_cfg=audio_cfg: orchestrator.execute_product_pipeline(
                        p_dto,
                        req.voice_profile_id,
                        a_cfg,
                        req.layout_config,
                        req.auto_one_click,
                    ),
                )
                created_projects.append(
                    {"project_id": project_id, "product_name": p_name, "state": st}
                )
            except Exception as exc:
                failed_urls.append({"url": url, "reason": str(exc)})

        if not created_projects:
            first_err = failed_urls[0]["reason"] if failed_urls else "Lỗi không xác định"
            raise HTTPException(
                status_code=400,
                detail=f"Không tạo được dự án nào từ danh sách link ({first_err}).",
            )

        return {
            "created_count": len(created_projects),
            "created_projects": created_projects,
            "failed_urls": failed_urls,
        }

    @app.post("/api/brain/expand-brief")
    async def expand_short_brief_endpoint(req: BriefExpandAPIRequest) -> Dict[str, Any]:
        """Analyze a short title + rough idea via API Key and expand into full script brief & optimal settings."""
        try:
            dto = BriefExpandRequestDTO(
                mode=req.mode,
                raw_title=req.raw_title,
                short_brief=req.short_brief,
                product_category=req.product_category,
                target_duration_sec=req.target_duration_sec,
                part_count=req.part_count,
            )
            expanded = await orchestrator.brain.expand_short_brief(dto)
            return expanded.model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Lỗi phân tích nội dung AI: {exc}") from exc

    @app.post("/api/product/compliance-check")
    async def check_product_script_compliance(req: ComplianceCheckRequest) -> Dict[str, Any]:
        """Audit product description/script against TikTok Shop & Ad Law rules."""
        return TikTokShopComplianceChecker.check_and_sanitize(req.text).model_dump()

    @app.post("/api/product/scrape-url")
    async def scrape_product_webpage(req: URLProbeRequest) -> Dict[str, Any]:
        """Auto-extract product title, specs, and gallery photos from an e-commerce/shop URL."""
        try:
            dest_folder = settings.work_dir / "_uploads" / "scraped_product"
            scraped = await ProductWebScraper.scrape_url(req.url, dest_folder, max_images=10)
            media_items = [
                {
                    "local_path": str(p),
                    "original_name": p.name,
                    "media_url": _to_media_url(str(p)),
                    "isVideo": False,
                }
                for p in scraped.downloaded_image_paths
            ]
            return {
                "source_url": scraped.source_url,
                "product_name": scraped.product_name,
                "raw_description": scraped.raw_description,
                "price_hint": scraped.price_hint,
                "media_items": media_items,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/product/preview-cutout")
    async def preview_single_photo_studio_cutout(req: CutoutPreviewRequest) -> Dict[str, str]:
        """Isolate product subject from background on a single uploaded photo and return transparent PNG."""
        src = Path(req.local_path)
        if not src.exists():
            raise HTTPException(status_code=404, detail="Không tìm thấy tệp ảnh gốc.")
        cutout_dir = settings.work_dir / "_uploads" / "cutouts"
        dst = cutout_dir / f"cutout_{uuid.uuid4().hex[:10]}.png"
        await asyncio.to_thread(ProductPhotoShowcaseProvider.create_studio_cutout_file, src, dst)
        return {
            "local_path": str(dst),
            "original_name": dst.name,
            "media_url": _to_media_url(str(dst)),
        }

    @app.get("/api/brand-kit")
    async def get_store_brand_kit() -> Dict[str, Any]:
        kit = repo.get_brand_kit()
        out = json.loads(kit.model_dump_json())
        out["logo_url"] = _to_media_url(str(kit.logo_path)) if kit.logo_path else ""
        return out

    @app.post("/api/brand-kit")
    async def save_store_brand_kit(req: BrandKitSaveRequest) -> Dict[str, Any]:
        logo_p = Path(req.logo_path) if req.logo_path and Path(req.logo_path).exists() else None
        saved = repo.save_brand_kit(
            BrandKitDTO(
                brand_name=req.brand_name.strip(),
                logo_path=logo_p,
                logo_pos_x=req.logo_pos_x,
                logo_pos_y=req.logo_pos_y,
                showroom_address=req.showroom_address.strip(),
                hotline_or_web=req.hotline_or_web.strip(),
                qr_code_content=req.qr_code_content.strip(),
                qr_code_label=req.qr_code_label.strip() or "Quét xem chi tiết",
                subtitle_pos_y=req.subtitle_pos_y,
                subtitle_font_size=req.subtitle_font_size,
                outro_card_enabled=req.outro_card_enabled,
                preferred_framing=req.preferred_framing,
                preferred_transition=req.preferred_transition,
                preferred_voice_id=req.preferred_voice_id,
                preferred_bgm_id=req.preferred_bgm_id,
            )
        )
        out = json.loads(saved.model_dump_json())
        out["logo_url"] = _to_media_url(str(saved.logo_path)) if saved.logo_path else ""
        return out

    @app.get("/api/product/templates")
    async def list_saved_product_templates() -> List[Dict[str, Any]]:
        """List reusable shop catalog product presets."""
        return [t.model_dump() for t in repo.list_product_templates()]

    @app.post("/api/product/templates")
    async def save_product_template(req: ProductTemplateSaveRequest) -> Dict[str, Any]:
        """Create or update a reusable shop catalog product preset."""
        tid = (req.template_id or "").strip() or f"tpl_{uuid.uuid4().hex[:8]}"
        saved = repo.upsert_product_template(
            SavedProductTemplateDTO(
                template_id=tid,
                product_name=req.product_name.strip(),
                product_category=req.product_category,
                raw_description=req.raw_description,
                call_to_action=req.call_to_action,
                offer_badge=req.offer_badge,
                contact_badge=req.contact_badge,
                qr_code_content=req.qr_code_content,
            )
        )
        return saved.model_dump()

    @app.delete("/api/product/templates/{template_id}")
    async def remove_product_template(template_id: str) -> Dict[str, Any]:
        repo.delete_product_template(template_id)
        return {"deleted_id": template_id}

    @app.post("/api/product/start")
    async def start_product_project(req: ProductStartRequest) -> Dict[str, Any]:
        """Start or enqueue Mode 3 E-Commerce Product Showcase workflow."""
        valid_imgs = [Path(p) for p in req.image_paths if p and Path(p).exists()]
        if not valid_imgs:
            raise HTTPException(
                status_code=400,
                detail="Vui lòng tải lên ít nhất 1 ảnh sản phẩm hợp lệ trước khi tạo video.",
            )

        project_id = f"prd_{uuid.uuid4().hex[:8]}"
        repo.create_project(
            project_id=project_id,
            name=req.product_name,
            mode=ProjectMode.PRODUCT_SHOWCASE,
            target_min_sec=max(15, req.target_duration_sec - 15),
            target_max_sec=min(180, req.target_duration_sec + 20),
            request_payload_json=req.model_dump_json(),
            parent_group_id=req.parent_group_id,
        )
        demo_p = (
            Path(req.demo_clip_path)
            if req.demo_clip_path and Path(req.demo_clip_path).exists()
            else None
        )
        valid_fb_imgs = [
            Path(p) for p in req.feedback_image_paths if p and Path(p).exists()
        ]
        eff_layout = req.layout_config.model_copy(
            update={
                "comparison_split_enabled": bool(
                    req.comparison_enabled or req.layout_config.comparison_split_enabled
                ),
                "comparison_label_a": req.layout_config.comparison_label_a
                or req.comparison_left_label,
                "comparison_label_b": req.layout_config.comparison_label_b
                or req.comparison_right_label,
                "feedback_image_paths": valid_fb_imgs or list(req.layout_config.feedback_image_paths),
            }
        )
        prompt_dto = ProductReviewPromptDTO(
            project_id=project_id,
            product_name=req.product_name,
            product_category=req.product_category,
            sales_angle=req.sales_angle,
            copywriting_tone=req.copywriting_tone,
            variant_count=req.variant_count,
            raw_description=req.raw_description,
            image_paths=valid_imgs,
            photo_notes=req.photo_notes,
            feedback_image_paths=valid_fb_imgs,
            comparison_enabled=eff_layout.comparison_split_enabled,
            comparison_left_label=eff_layout.comparison_label_a or "Phiên bản A",
            comparison_right_label=eff_layout.comparison_label_b or "Phiên bản B",
            demo_clip_path=demo_p,
            target_duration_sec=req.target_duration_sec,
            call_to_action=req.call_to_action,
        )
        audio_cfg = _resolve_bgm_into_audio_cfg(
            AudioSubConfigDTO(
                enable_narration=True,
                keep_original_audio=False,
                bgm_volume=req.bgm_volume,
                subtitle_style=req.subtitle_style,
                subtitle_pos_y=eff_layout.subtitle_pos_y,
                subtitle_font_size=eff_layout.subtitle_font_size,
                voice_speed_global=req.voice_speed_global,
                voice_pitch_global=req.voice_pitch_global,
            ),
            req.bgm_preset_id,
            req.custom_bgm_path,
        )
        initial_state = job_mgr.enqueue_job(
            project_id=project_id,
            mode=ProjectMode.PRODUCT_SHOWCASE,
            is_render_only=False,
            coro_factory=lambda: orchestrator.execute_product_pipeline(
                prompt_dto,
                req.voice_profile_id,
                audio_cfg,
                eff_layout,
                req.auto_one_click,
            ),
        )
        return {"project_id": project_id, "state": initial_state}

    @app.post("/api/topic/start")
    async def start_topic_project(req: TopicStartRequest) -> Dict[str, Any]:
        project_id = f"top_{uuid.uuid4().hex[:8]}"
        repo.create_project(
            project_id=project_id,
            name=req.topic_title,
            mode=ProjectMode.TOPIC_VIDEO,
            target_min_sec=max(15, req.target_duration_sec - 15),
            target_max_sec=min(180, req.target_duration_sec + 15),
            request_payload_json=req.model_dump_json(),
            parent_group_id=req.parent_group_id,
        )
        prompt_dto = TopicPromptDTO(
            project_id=project_id,
            topic_title=req.topic_title,
            key_points=req.key_points,
            visual_mode=req.visual_mode,
            target_duration_sec=req.target_duration_sec,
            part_count=req.part_count,
            narrative_tone=req.narrative_tone,
        )
        audio_cfg = _resolve_bgm_into_audio_cfg(
            AudioSubConfigDTO(
                enable_narration=True,
                keep_original_audio=False,
                bgm_volume=req.bgm_volume,
                subtitle_style=req.subtitle_style,
            ),
            req.bgm_preset_id,
            req.custom_bgm_path,
        )
        initial_state = job_mgr.enqueue_job(
            project_id=project_id,
            mode=ProjectMode.TOPIC_VIDEO,
            is_render_only=False,
            coro_factory=lambda: orchestrator.execute_topic_pipeline(
                prompt_dto,
                req.voice_profile_id,
                audio_cfg,
                req.layout_config,
                req.auto_one_click,
            ),
        )
        return {"project_id": project_id, "state": initial_state}

    @app.post("/api/movie/start")
    async def start_movie_project(req: MovieStartRequest) -> Dict[str, Any]:
        project_id = f"mov_{uuid.uuid4().hex[:8]}"
        raw_target = req.path_or_url.strip()
        eff_source_type = (
            SourceType.VIDEO_URL
            if ("http://" in raw_target.lower() or "https://" in raw_target.lower())
            else req.source_type
        )
        eff_target = (
            normalize_video_url(raw_target)
            if eff_source_type == SourceType.VIDEO_URL
            else raw_target
        )
        normalized_req = req.model_copy(
            update={"source_type": eff_source_type, "path_or_url": eff_target}
        )
        repo.create_project(
            project_id=project_id,
            name=normalized_req.project_name,
            mode=ProjectMode.MOVIE_CLIPPER,
            target_min_sec=normalized_req.cut_config.min_clip_sec,
            target_max_sec=normalized_req.cut_config.max_clip_sec,
            request_payload_json=normalized_req.model_dump_json(),
            parent_group_id=normalized_req.parent_group_id,
        )
        ingest_dto = IngestRequestDTO(
            project_id=project_id,
            source_type=eff_source_type,
            path_or_url=eff_target,
            external_srt_path=(
                Path(normalized_req.external_srt_path)
                if normalized_req.external_srt_path
                else None
            ),
        )
        cut_cfg = normalized_req.cut_config.model_copy(
            update={"series_title": normalized_req.project_name}
        )
        audio_cfg = _resolve_bgm_into_audio_cfg(
            normalized_req.audio_config,
            normalized_req.bgm_preset_id,
            normalized_req.custom_bgm_path,
        )
        initial_state = job_mgr.enqueue_job(
            project_id=project_id,
            mode=ProjectMode.MOVIE_CLIPPER,
            is_render_only=False,
            coro_factory=lambda: orchestrator.execute_movie_pipeline(
                ingest_dto,
                cut_cfg,
                normalized_req.voice_profile_id,
                audio_cfg,
                normalized_req.layout_config,
                normalized_req.source_language,
                normalized_req.auto_one_click,
            ),
        )
        return {"project_id": project_id, "state": initial_state}

    @app.get("/api/project-groups")
    async def list_parent_project_groups() -> List[Dict[str, Any]]:
        """List all parent project containers with child project counts."""
        return [g.model_dump() for g in repo.list_project_groups()]

    @app.post("/api/project-groups")
    async def save_parent_project_group(req: ProjectGroupSaveRequest) -> Dict[str, Any]:
        """Create or update a parent project container."""
        gid = (req.group_id or "").strip() or f"grp_{uuid.uuid4().hex[:8]}"
        saved = repo.upsert_project_group(
            group_id=gid,
            name=req.name,
            description=req.description,
            color_tag=req.color_tag,
        )
        return saved.model_dump()

    @app.delete("/api/project-groups/{group_id}")
    async def remove_parent_project_group(group_id: str) -> Dict[str, Any]:
        """Delete a parent project group while preserving all child projects."""
        repo.delete_project_group(group_id)
        return {"deleted_group_id": group_id}

    @app.post("/api/projects/{project_id}/assign-group")
    async def assign_project_group_endpoint(
        project_id: str, req: ProjectGroupAssignRequest
    ) -> Dict[str, Any]:
        """Assign or detach a child project to/from a parent project group."""
        proj = repo.get_project(project_id)
        if proj is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
        repo.assign_project_to_group(project_id, req.group_id)
        return await get_project_detail(project_id)

    @app.get("/api/projects")
    async def get_all_projects() -> List[Dict[str, Any]]:
        projs = repo.list_projects()
        for p in projs:
            p["live_progress"] = hub.get_latest(p["id"])
        return projs

    @app.get("/api/projects/{project_id}")
    async def get_project_detail(project_id: str) -> Dict[str, Any]:
        proj = repo.get_project(project_id)
        if proj is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
        proj["live_progress"] = hub.get_latest(project_id)
        proj["is_active_in_memory"] = job_mgr.is_in_memory_active_or_paused(project_id)
        if proj.get("source_media"):
            frames = json.loads(proj["source_media"].get("preview_frames_json") or "[]")
            proj["source_media"]["preview_urls"] = [_to_media_url(fp) for fp in frames]
        try:
            saved_req_dict = json.loads(proj.get("request_payload_json") or "{}")
        except Exception:
            saved_req_dict = {}
        proj["saved_request"] = saved_req_dict

        if proj.get("mode") == ProjectMode.PRODUCT_SHOWCASE.value:
            raw_img_paths = saved_req_dict.get("image_paths") or []
            proj["product_image_paths"] = raw_img_paths
            proj["product_image_urls"] = [_to_media_url(fp) for fp in raw_img_paths]
        for clip in proj.get("clips", []):
            clip["video_url"] = _to_media_url(clip.get("output_mp4_path") or "")
            clip["cover_url"] = _to_media_url(clip.get("cover_jpg_path") or "")
        return proj

    @app.post("/api/projects/{project_id}/render")
    async def approve_and_render_project(
        project_id: str, req: RenderApprovedRequest
    ) -> Dict[str, Any]:
        proj = repo.get_project(project_id)
        if proj is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")

        mode = ProjectMode(proj["mode"])
        if req.clips:
            rebuilt_clips: List[ClipSpecDTO] = []
            for cp in req.clips:
                rebuilt_clips.append(
                    ClipSpecDTO(
                        clip_id=cp.clip_id,
                        project_id=project_id,
                        part_number=cp.part_number,
                        source_start_ms=cp.source_start_ms,
                        source_end_ms=cp.source_end_ms,
                        hook_banner_title=cp.hook_banner_title,
                        lines=[
                            NarrationLineDTO(
                                seq_index=ln.seq_index,
                                rel_start_ms=ln.rel_start_ms,
                                rel_end_ms=ln.rel_end_ms,
                                original_text=ln.original_text,
                                vi_text=ln.vi_text,
                                image_prompt=ln.image_prompt,
                                stock_keywords=ln.stock_keywords,
                                matched_image_index=ln.matched_image_index,
                                is_real_demo_slot=ln.is_real_demo_slot,
                                callout_label=ln.callout_label,
                                voice_speed_override=ln.voice_speed_override,
                                voice_pitch_override=ln.voice_pitch_override,
                            )
                            for ln in cp.lines
                        ],
                        append_cta_outro=cp.append_cta_outro,
                    )
                )
            cut_plan = CutPlanDTO(project_id=project_id, mode=mode, clips=rebuilt_clips)
            repo.save_cut_plan(cut_plan)
        else:
            rebuilt_clips = [
                ClipSpecDTO(
                    clip_id=c["clip_id"],
                    project_id=project_id,
                    part_number=int(c["part_number"]),
                    source_start_ms=int(c["start_ms"]),
                    source_end_ms=int(c["end_ms"]),
                    hook_banner_title=c["hook_banner_title"],
                    append_cta_outro=bool(c["append_cta_outro"]),
                    lines=[
                        NarrationLineDTO(
                            seq_index=int(s["seq_index"]),
                            rel_start_ms=int(s["rel_start_ms"]),
                            rel_end_ms=int(s["rel_end_ms"]),
                            original_text=s["original_text"] or "",
                            vi_text=s["vi_narration_text"],
                            image_prompt=s["image_prompt"] or "",
                            stock_keywords=json.loads(s.get("stock_keywords_json") or "[]"),
                            matched_image_index=(
                                int(s["matched_image_index"])
                                if s.get("matched_image_index") is not None
                                else None
                            ),
                            is_real_demo_slot=bool(s.get("is_real_demo_slot")),
                            callout_label=s.get("callout_label") or "",
                            voice_speed_override=(
                                float(s["voice_speed_override"])
                                if s.get("voice_speed_override") is not None
                                else None
                            ),
                            voice_pitch_override=(
                                float(s["voice_pitch_override"])
                                if s.get("voice_pitch_override") is not None
                                else None
                            ),
                        )
                        for s in c["lines"]
                    ],
                )
                for c in proj["clips"]
            ]
            cut_plan = CutPlanDTO(project_id=project_id, mode=mode, clips=rebuilt_clips)

        if req.selected_part_numbers:
            allowed_parts = set(req.selected_part_numbers)
            filtered = [c for c in cut_plan.clips if c.part_number in allowed_parts]
            if filtered:
                cut_plan = CutPlanDTO(project_id=project_id, mode=mode, clips=filtered)

        override_imgs: Optional[List[Path]] = None
        if req.image_paths_override:
            valid_ov = [Path(p) for p in req.image_paths_override if p and Path(p).exists()]
            if valid_ov:
                override_imgs = valid_ov

        # Persist updated layout/voice/bgm/photo order into request_payload_json for future re-edits
        try:
            saved_req_dict = json.loads(proj.get("request_payload_json") or "{}")
            saved_req_dict["voice_profile_id"] = req.voice_profile_id
            saved_req_dict["bgm_preset_id"] = req.bgm_preset_id
            saved_req_dict["custom_bgm_path"] = req.custom_bgm_path
            saved_req_dict["bgm_volume"] = req.audio_config.bgm_volume
            saved_req_dict["layout_config"] = json.loads(req.layout_config.model_dump_json())
            if override_imgs:
                saved_req_dict["image_paths"] = [str(p) for p in override_imgs]
            with repo._connect() as conn:
                conn.execute(
                    "UPDATE projects SET request_payload_json = ? WHERE id = ?",
                    (json.dumps(saved_req_dict, ensure_ascii=False), project_id),
                )
        except Exception:
            pass

        audio_cfg = _resolve_bgm_into_audio_cfg(
            req.audio_config, req.bgm_preset_id, req.custom_bgm_path
        )
        initial_state = job_mgr.enqueue_job(
            project_id=project_id,
            mode=mode,
            is_render_only=True,
            coro_factory=lambda: orchestrator.render_approved_plan(
                project_id,
                cut_plan,
                req.voice_profile_id,
                audio_cfg,
                req.layout_config,
                req.visual_mode,
                image_paths_override=override_imgs,
            ),
        )
        return {"project_id": project_id, "state": initial_state}

    @app.post("/api/projects/{project_id}/pause")
    async def pause_project(project_id: str) -> Dict[str, Any]:
        """Pause an active project safely."""
        if not job_mgr.pause_job(project_id):
            repo.update_project_state(project_id, JobState.PAUSED)
        return await get_project_detail(project_id)

    @app.post("/api/projects/{project_id}/resume")
    async def resume_project(project_id: str) -> Dict[str, Any]:
        """Resume an in-memory paused project OR resume unfinished parts from disk."""
        if job_mgr.resume_in_memory_job(project_id):
            return await get_project_detail(project_id)

        proj = repo.get_project(project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")

        # If clips already exist on disk, render ONLY the unfinished parts!
        clips = proj.get("clips") or []
        unfinished = [
            int(c["part_number"])
            for c in clips
            if not (c.get("output_mp4_path") and Path(c["output_mp4_path"]).exists())
        ]
        if clips and unfinished:
            saved_dict = json.loads(proj.get("request_payload_json") or "{}")
            voice_id = saved_dict.get("voice_profile_id") or "edge_nam_minh_movie"
            mode = ProjectMode(proj["mode"])
            audio_dict = saved_dict.get("audio_config") or {}
            audio_cfg = (
                AudioSubConfigDTO(**audio_dict)
                if audio_dict
                else AudioSubConfigDTO(
                    enable_narration=True,
                    keep_original_audio=(mode == ProjectMode.MOVIE_CLIPPER),
                    subtitle_style=(
                        SubtitleStyle.CINEMA
                        if mode == ProjectMode.MOVIE_CLIPPER
                        else SubtitleStyle.KARAOKE_CAPCUT
                    ),
                )
            )
            layout_dict = saved_dict.get("layout_config") or {}
            layout_cfg = (
                LayoutAndAntiCopyConfigDTO(**layout_dict)
                if layout_dict
                else LayoutAndAntiCopyConfigDTO()
            )
            await approve_and_render_project(
                project_id,
                RenderApprovedRequest(
                    voice_profile_id=voice_id,
                    bgm_preset_id=saved_dict.get("bgm_preset_id"),
                    audio_config=audio_cfg,
                    layout_config=layout_cfg,
                    selected_part_numbers=unfinished,
                ),
            )
            return await get_project_detail(project_id)

        await retry_failed_project(project_id)
        return await get_project_detail(project_id)

    @app.post("/api/projects/{project_id}/cancel")
    async def cancel_project(project_id: str) -> Dict[str, Any]:
        """Cancel a running, paused, or queued project."""
        job_mgr.cancel_job(project_id)
        return await get_project_detail(project_id)

    @app.delete("/api/projects/{project_id}")
    async def delete_project_endpoint(project_id: str) -> Dict[str, Any]:
        """Cancel if active, delete DB record & temp files, while keeping exported .mp4 files safe."""
        job_mgr.cancel_job(project_id)
        deleted = repo.delete_project(project_id)
        if deleted is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
        hub.clear_project(project_id)
        work_sub = settings.work_dir / project_id
        if work_sub.exists():
            shutil.rmtree(work_sub, ignore_errors=True)
        return {"deleted_id": project_id, "storage": job_mgr.inspect_storage()}

    @app.post("/api/projects/{project_id}/translate-vi")
    async def translate_project_segments_to_vietnamese(project_id: str) -> Dict[str, Any]:
        """Translate all non-Vietnamese lines of an existing project into Vietnamese in-place."""
        proj = repo.get_project(project_id)
        if proj is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")

        all_seg_ids: List[str] = []
        all_sources: List[str] = []
        for clip in proj.get("clips", []):
            for ln in clip.get("lines", []):
                all_seg_ids.append(ln["segment_id"])
                src_txt = (ln.get("original_text") or ln.get("vi_narration_text") or "").strip()
                all_sources.append(src_txt)

        if not all_sources:
            return await get_project_detail(project_id)

        vi_results = await FreeVietnameseTranslator.translate_lines(all_sources, source_lang="auto")
        with repo._connect() as conn:
            for seg_id, orig, vi_txt in zip(all_seg_ids, all_sources, vi_results):
                conn.execute(
                    """
                    UPDATE subtitle_segments
                    SET original_text = CASE WHEN original_text = '' THEN ? ELSE original_text END,
                        vi_narration_text = ?
                    WHERE segment_id = ?
                    """,
                    (orig, vi_txt, seg_id),
                )
        return await get_project_detail(project_id)

    @app.post("/api/projects/{project_id}/retry")
    async def retry_failed_project(project_id: str) -> Dict[str, Any]:
        """Retry an existing Movie, Topic, or Product project via JobExecutionManager."""
        proj = repo.get_project(project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")

        saved_json = proj.get("request_payload_json") or "{}"
        mode = ProjectMode(proj["mode"])

        if mode == ProjectMode.MOVIE_CLIPPER:
            parsed_req: Optional[MovieStartRequest] = None
            try:
                raw_dict = json.loads(saved_json)
                if raw_dict.get("path_or_url"):
                    parsed_req = MovieStartRequest(**raw_dict)
            except Exception:
                parsed_req = None

            sm = proj.get("source_media")
            if sm and sm.get("local_video_path") and Path(sm["local_video_path"]).exists():
                ingest_dto = IngestRequestDTO(
                    project_id=project_id,
                    source_type=SourceType.LOCAL_FILE,
                    path_or_url=sm["local_video_path"],
                )
            elif parsed_req is not None:
                eff_type = (
                    SourceType.VIDEO_URL
                    if ("http://" in parsed_req.path_or_url or "https://" in parsed_req.path_or_url)
                    else parsed_req.source_type
                )
                eff_url = (
                    normalize_video_url(parsed_req.path_or_url)
                    if eff_type == SourceType.VIDEO_URL
                    else parsed_req.path_or_url
                )
                ingest_dto = IngestRequestDTO(
                    project_id=project_id,
                    source_type=eff_type,
                    path_or_url=eff_url,
                    external_srt_path=(
                        Path(parsed_req.external_srt_path)
                        if parsed_req.external_srt_path
                        else None
                    ),
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Dự án cũ chưa lưu đường dẫn gốc, vui lòng dán lại link ở tab Cắt Phim.",
                )

            cut_cfg = (
                parsed_req.cut_config.model_copy(update={"series_title": proj["name"]})
                if parsed_req
                else CutConfigDTO(
                    min_clip_sec=int(proj.get("target_min_sec") or 65),
                    max_clip_sec=int(proj.get("target_max_sec") or 120),
                    series_title=proj["name"],
                )
            )
            repo.update_project_state(project_id, JobState.INGESTING, error_message="")
            audio_cfg = _resolve_bgm_into_audio_cfg(
                parsed_req.audio_config if parsed_req else AudioSubConfigDTO(),
                parsed_req.bgm_preset_id if parsed_req else None,
            )
            st = job_mgr.enqueue_job(
                project_id=project_id,
                mode=ProjectMode.MOVIE_CLIPPER,
                is_render_only=False,
                coro_factory=lambda: orchestrator.execute_movie_pipeline(
                    ingest_dto,
                    cut_cfg,
                    parsed_req.voice_profile_id if parsed_req else "edge_nam_minh_movie",
                    audio_cfg,
                    parsed_req.layout_config if parsed_req else LayoutAndAntiCopyConfigDTO(),
                    parsed_req.source_language if parsed_req else "auto",
                    parsed_req.auto_one_click if parsed_req else True,
                ),
            )
            return {"project_id": project_id, "state": st}

        if mode == ProjectMode.PRODUCT_SHOWCASE:
            try:
                prod_req = ProductStartRequest(**json.loads(saved_json))
            except Exception as exc:
                raise HTTPException(
                    status_code=400, detail=f"Không thể khôi phục cấu hình sản phẩm: {exc}"
                ) from exc
            valid_imgs = [Path(p) for p in prod_req.image_paths if p and Path(p).exists()]
            demo_p = (
                Path(prod_req.demo_clip_path)
                if prod_req.demo_clip_path and Path(prod_req.demo_clip_path).exists()
                else None
            )
            prompt_dto = ProductReviewPromptDTO(
                project_id=project_id,
                product_name=prod_req.product_name,
                product_category=prod_req.product_category,
                sales_angle=prod_req.sales_angle,
                copywriting_tone=prod_req.copywriting_tone,
                variant_count=prod_req.variant_count,
                raw_description=prod_req.raw_description,
                image_paths=valid_imgs,
                photo_notes=prod_req.photo_notes,
                demo_clip_path=demo_p,
                target_duration_sec=prod_req.target_duration_sec,
                call_to_action=prod_req.call_to_action,
            )
            repo.update_project_state(project_id, JobState.AI_ANALYZING, error_message="")
            audio_cfg = _resolve_bgm_into_audio_cfg(
                AudioSubConfigDTO(
                    enable_narration=True,
                    keep_original_audio=False,
                    bgm_volume=prod_req.bgm_volume,
                    subtitle_style=prod_req.subtitle_style,
                ),
                prod_req.bgm_preset_id,
                prod_req.custom_bgm_path,
            )
            st = job_mgr.enqueue_job(
                project_id=project_id,
                mode=ProjectMode.PRODUCT_SHOWCASE,
                is_render_only=False,
                coro_factory=lambda: orchestrator.execute_product_pipeline(
                    prompt_dto,
                    prod_req.voice_profile_id,
                    audio_cfg,
                    prod_req.layout_config,
                    prod_req.auto_one_click,
                ),
            )
            return {"project_id": project_id, "state": st}

        prompt_dto = TopicPromptDTO(
            project_id=project_id,
            topic_title=proj["name"],
            target_duration_sec=int(proj.get("target_max_sec") or 90),
        )
        repo.update_project_state(project_id, JobState.AI_ANALYZING, error_message="")
        st = job_mgr.enqueue_job(
            project_id=project_id,
            mode=ProjectMode.TOPIC_VIDEO,
            is_render_only=False,
            coro_factory=lambda: orchestrator.execute_topic_pipeline(
                prompt_dto,
                "edge_nam_minh_movie",
                AudioSubConfigDTO(
                    keep_original_audio=False, subtitle_style=SubtitleStyle.KARAOKE_CAPCUT
                ),
                LayoutAndAntiCopyConfigDTO(),
                True,
            ),
        )
        return {"project_id": project_id, "state": st}

    @app.post("/api/projects/{project_id}/open-folder")
    async def open_project_output_folder(project_id: str) -> Dict[str, str]:
        proj = repo.get_project(project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
        target_dir = settings.outputs_dir
        for clip in proj.get("clips", []):
            if clip.get("output_mp4_path"):
                p = Path(clip["output_mp4_path"]).parent
                if p.exists():
                    target_dir = p
                    break
        if os.name == "nt" and target_dir.exists():
            subprocess.Popen(["explorer", str(target_dir)])
        return {"opened_dir": str(target_dir)}

    @app.get("/api/projects/{project_id}/download-zip")
    async def download_project_bundle_zip(project_id: str) -> FileResponse:
        """Package all completed MP4 videos, Cover JPEGs, ASS subtitles & SEO text into a .zip."""
        proj = repo.get_project(project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")

        files_to_pack: List[tuple[Path, str]] = []
        out_folder: Optional[Path] = None
        for clip in proj.get("clips", []):
            p_num = int(clip.get("part_number") or 1)
            mp4_s = clip.get("output_mp4_path") or ""
            if mp4_s and Path(mp4_s).exists():
                mp4_p = Path(mp4_s)
                out_folder = mp4_p.parent
                files_to_pack.append((mp4_p, f"Video_Part_{p_num:02d}.mp4"))
            cov_s = clip.get("cover_jpg_path") or ""
            if cov_s and Path(cov_s).exists():
                files_to_pack.append((Path(cov_s), f"Anh_Bia_Part_{p_num:02d}.jpg"))

        if out_folder and (out_folder / "SEO_TikTok_YouTubeShorts.txt").exists():
            files_to_pack.append(
                (out_folder / "SEO_TikTok_YouTubeShorts.txt", "SEO_TikTok_YouTubeShorts.txt")
            )

        if not files_to_pack:
            raise HTTPException(status_code=400, detail="Dự án chưa có tệp video xuất hoàn tất.")

        zips_dir = settings.work_dir / "_zips"
        zips_dir.mkdir(parents=True, exist_ok=True)
        zip_path = zips_dir / f"{project_id}_bundle.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            for src_p, arc_name in files_to_pack:
                zf.write(src_p, arcname=arc_name)

        safe_dl = f"ChaosShortVideo_{project_id}.zip"
        return FileResponse(
            path=str(zip_path),
            media_type="application/zip",
            filename=safe_dl,
        )

    @app.websocket("/ws/progress/{project_id}")
    async def ws_project_progress(websocket: WebSocket, project_id: str) -> None:
        await hub.connect(project_id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            hub.disconnect(project_id, websocket)

    # Serve built React frontend SPA if `frontend/dist` exists
    dist_dir = settings.workspace_root / "frontend" / "dist"
    if dist_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="fe_assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            candidate = dist_dir / full_path
            if full_path and candidate.exists() and candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(dist_dir / "index.html"))

    return app


app = create_studio_app()
