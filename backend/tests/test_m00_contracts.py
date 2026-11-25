"""Unit & I/O Contract Tests for Module M00 (`m00_core_contracts`)."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from app.m00_core_contracts import (
    AssetType,
    ClipSpecDTO,
    CutConfigDTO,
    CutPlanDTO,
    GPUResourceManager,
    JobState,
    LayoutAndAntiCopyConfigDTO,
    MasterAudioAndSubDTO,
    NarrationLineDTO,
    NormalizedRectDTO,
    ProjectMode,
    RenderJobSpecDTO,
    SceneVisualItemDTO,
    SEOPackageDTO,
    SQLiteRepository,
    VisualAssetListDTO,
)


def test_normalized_rect_validation() -> None:
    """Ensure coordinates stay strictly inside [0.0, 1.0] and x+w, y+h <= 1.0."""
    valid_rect = NormalizedRectDTO(x=0.0, y=0.78, w=1.0, h=0.12)
    assert valid_rect.y == 0.78

    with pytest.raises(ValidationError):
        NormalizedRectDTO(x=0.2, y=0.85, w=0.9, h=0.10)  # x + w = 1.1 > 1.0


def test_cut_config_window_validation() -> None:
    """Verify min_clip_sec < max_clip_sec constraint."""
    cfg = CutConfigDTO(min_clip_sec=65, max_clip_sec=120)
    assert cfg.min_clip_sec == 65

    with pytest.raises(ValidationError):
        CutConfigDTO(min_clip_sec=120, max_clip_sec=90)


def test_end_to_end_dto_contract_chain(tmp_path: Path) -> None:
    """Prove Output of M03 + M04 + M05 matches 100% with Input of M06 RenderJobSpecDTO."""
    clip = ClipSpecDTO(
        clip_id="clip_001",
        project_id="proj_001",
        part_number=1,
        source_start_ms=0,
        source_end_ms=75000,
        hook_banner_title="Tổng Tài Báo Thù | Phần 1",
        lines=[
            NarrationLineDTO(
                seq_index=0,
                rel_start_ms=0,
                rel_end_ms=4500,
                vi_text="Không ai ngờ người đàn ông mặc đồ cũ kỹ này lại là chủ tịch tập đoàn.",
                image_prompt="cinematic dramatic ceo in humble clothes vertical 9:16",
            )
        ],
    )
    assert clip.duration_ms == 75000

    visuals = VisualAssetListDTO(
        clip_id="clip_001",
        items=[
            SceneVisualItemDTO(
                seq_index=0,
                asset_path=tmp_path / "scene_0.png",
                asset_type=AssetType.IMAGE,
                duration_ms=4500,
            )
        ],
    )
    audio_sub = MasterAudioAndSubDTO(
        clip_id="clip_001",
        master_audio_wav_path=tmp_path / "master.wav",
        ass_subtitle_path=tmp_path / "subs.ass",
        total_audio_duration_ms=75000,
    )

    job_spec = RenderJobSpecDTO(
        clip=clip,
        visual_assets=visuals,
        audio_sub=audio_sub,
        layout_config=LayoutAndAntiCopyConfigDTO(),
        output_dir=tmp_path / "out",
    )
    assert job_spec.clip.clip_id == "clip_001"

    # Mismatched clip_id must be rejected at contract boundary
    bad_audio = MasterAudioAndSubDTO(
        clip_id="clip_WRONG",
        master_audio_wav_path=tmp_path / "master.wav",
        total_audio_duration_ms=75000,
    )
    with pytest.raises(ValidationError):
        RenderJobSpecDTO(
            clip=clip,
            visual_assets=visuals,
            audio_sub=bad_audio,
            output_dir=tmp_path / "out",
        )


def test_gpu_resource_manager_lock_and_cleanup() -> None:
    """Ensure VRAM lock releases cleanly even when an exception occurs inside context."""
    mgr = GPUResourceManager()
    cleaned = {"called": False}

    def _cleanup() -> None:
        cleaned["called"] = True

    with pytest.raises(RuntimeError):
        with mgr.acquire_vram("test-model", cleanup_fn=_cleanup):
            assert mgr.active_owner == "test-model"
            raise RuntimeError("Simulated inference crash")

    assert cleaned["called"] is True
    assert mgr.active_owner is None


def test_sqlite_repository_crud_and_seeded_voices(tmp_path: Path) -> None:
    """Verify ERD SQLite persistence, seeded voices, CutPlan, and SEO saving."""
    repo = SQLiteRepository(tmp_path / "test_studio.db")
    voices = repo.list_voice_profiles()
    assert len(voices) >= 3

    proj = repo.create_project("p1", "Phim Ngắn Test", ProjectMode.MOVIE_CLIPPER)
    assert proj["state"] == JobState.DRAFT.value

    plan = CutPlanDTO(
        project_id="p1",
        mode=ProjectMode.MOVIE_CLIPPER,
        clips=[
            ClipSpecDTO(
                clip_id="p1_part_1",
                project_id="p1",
                part_number=1,
                source_start_ms=0,
                source_end_ms=70000,
                hook_banner_title="Phim Ngắn Test | Phần 1",
                lines=[
                    NarrationLineDTO(
                        seq_index=0,
                        rel_start_ms=500,
                        rel_end_ms=3500,
                        original_text="你好",
                        vi_text="Xin chào đại ca",
                    )
                ],
            )
        ],
    )
    repo.save_cut_plan(plan)
    repo.save_seo_package(
        SEOPackageDTO(
            clip_id="p1_part_1",
            part_number=1,
            yt_shorts_title="Cái kết bất ngờ #Shorts",
            yt_shorts_description="Xem tiếp Phần 2 tại kênh!",
            yt_shorts_tags=["phimngan", "shorts"],
            tiktok_caption="Không ngờ cái kết lại như vậy!",
            tiktok_hashtags=["#xuhuong", "#reviewphim"],
        )
    )
    repo.update_project_state("p1", JobState.COMPLETED)

    loaded = repo.get_project("p1")
    assert loaded is not None
    assert loaded["state"] == JobState.COMPLETED.value
    assert len(loaded["clips"]) == 1
    assert loaded["clips"][0]["lines"][0]["vi_narration_text"] == "Xin chào đại ca"
    assert loaded["clips"][0]["seo"]["yt_shorts_title"] == "Cái kết bất ngờ #Shorts"

