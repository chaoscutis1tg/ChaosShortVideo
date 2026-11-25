"""SQLite persistence layer implementing the 7 ERD tables and emotional voice profiles."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from .dtos import (
    BrandKitDTO,
    ClipSpecDTO,
    CutPlanDTO,
    MediaAssetDTO,
    RenderOutputDTO,
    SavedProductTemplateDTO,
    SEOPackageDTO,
    VoiceProfileDTO,
)
from .enums import (
    JobState,
    ProductCategory,
    ProductFramingStyle,
    ProjectMode,
    TransitionStyle,
    VoiceTier,
)

DEFAULT_VOICE_PROFILES: List[VoiceProfileDTO] = [
    VoiceProfileDTO(
        profile_id="edge_nam_nghe_nhan",
        display_name="Đức Trung — Nam Trầm Ấm Chia Sẻ Nhạc Cụ / Đồ Gỗ Thủ Công (Truyền cảm)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="en-US-AndrewMultilingualNeural",
        speed_rate=1.01,
        pitch_hz=-1.6,
        emotion_prompt="Giọng nam trầm ấm, điềm đạm như nghệ nhân chia sẻ mộc mạc về tiếng đàn và chất gỗ",
        dsp_preset="artisan_warm_studio",
    ),
    VoiceProfileDTO(
        profile_id="edge_nu_boutique_silk",
        display_name="Khánh Linh — Nữ Sang Trọng Tư Vấn Nhạc Cụ & Thời Trang Thiết Kế (Mềm mại)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="de-DE-SeraphinaMultilingualNeural",
        speed_rate=1.03,
        pitch_hz=0.2,
        emotion_prompt="Giọng nữ sang trọng, thanh lịch, tròn vành rõ chữ cho showroom đàn và boutique thời trang",
        dsp_preset="luxury_silk_female",
    ),
    VoiceProfileDTO(
        profile_id="edge_nam_minh_movie",
        display_name="Minh Quân — Nam Trầm Thuyết Minh Phim Bộ / Tổng Tài (Đĩnh đạc)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="en-US-BrianMultilingualNeural",
        speed_rate=1.08,
        pitch_hz=-1.2,
        emotion_prompt="Giọng nam trầm ấm, đĩnh đạc, nhấn nhá kịch tính chuẩn thuyết minh phim bộ",
        dsp_preset="movie_male_deep",
    ),
    VoiceProfileDTO(
        profile_id="edge_hoai_my_drama",
        display_name="Thanh Thảo — Nữ Ngôn Tình Sâu Lắng / Kể Chuyện Nghệ Thuật (Ngọt ngào)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="en-US-AvaMultilingualNeural",
        speed_rate=1.04,
        pitch_hz=0.0,
        emotion_prompt="Giọng nữ truyền cảm, mềm mại, giàu cảm xúc nội tâm",
        dsp_preset="drama_female_emotional",
    ),
    VoiceProfileDTO(
        profile_id="edge_lan_anh_story",
        display_name="Lan Anh — Nữ Trầm Dịu Đêm Khuya / Review Tinh Tế (Chữa lành)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="fr-FR-VivienneMultilingualNeural",
        speed_rate=1.00,
        pitch_hz=-0.6,
        emotion_prompt="Giọng nữ nhẹ nhàng, sâu lắng, ngắt nghỉ giàu chiều sâu cảm xúc",
        dsp_preset="luxury_silk_female",
    ),
    VoiceProfileDTO(
        profile_id="edge_gia_bao_consult",
        display_name="Gia Bảo — Nam Trẻ Trung Tư Vấn Thực Tế & So Sánh Phiên Bản (Rõ ràng)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="it-IT-GiuseppeMultilingualNeural",
        speed_rate=1.07,
        pitch_hz=-0.4,
        emotion_prompt="Giọng nam thân thiện, mạch lạc, giải thích thông số dễ hiểu cho người mới mua",
        dsp_preset="artisan_warm_studio",
    ),
    VoiceProfileDTO(
        profile_id="edge_phuong_anh_fashion",
        display_name="Phương Anh — Nữ Hiện Đại Lookbook Quần Áo & Phụ Kiện (Tươi sáng)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="pt-BR-ThalitaMultilingualNeural",
        speed_rate=1.06,
        pitch_hz=0.5,
        emotion_prompt="Giọng nữ tươi tắn, tự nhiên, tôn vẻ thanh lịch cho sản phẩm thời trang",
        dsp_preset="drama_female_emotional",
    ),
    VoiceProfileDTO(
        profile_id="edge_hoang_vu_action",
        display_name="Hoàng Vũ — Nam Kịch Tính Phim Hành Động / Trinh Thám (Gay cấn)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="fr-FR-RemyMultilingualNeural",
        speed_rate=1.12,
        pitch_hz=-0.8,
        emotion_prompt="Giọng nam hồi hộp, dồn dập, nhấn mạnh các tình tiết gay cấn bất ngờ",
        dsp_preset="thriller_suspense",
    ),
    VoiceProfileDTO(
        profile_id="edge_hoai_my_fast",
        display_name="Mai Phương — Nữ Review Nhịp Nhanh TikTok / Shorts (Bắt tai)",
        tier=VoiceTier.EDGE_TTS,
        voice_id_or_sample_path="en-US-EmmaMultilingualNeural",
        speed_rate=1.13,
        pitch_hz=0.3,
        emotion_prompt="Giọng nữ trẻ trung, bắt tai, mở đầu cuốn hút giữ chân người xem TikTok",
        dsp_preset="thriller_suspense",
    ),
    VoiceProfileDTO(
        profile_id="local_vais_studio",
        display_name="Ngọc Huyền (Offline Phòng Thu) — Nữ Bắc Chuẩn Đài 0.1s (Không cần mạng)",
        tier=VoiceTier.LOCAL_ONNX_VITS,
        voice_id_or_sample_path="vi_VN-vais1000-medium.onnx",
        speed_rate=1.05,
        pitch_hz=0.0,
        emotion_prompt="Giọng phát thanh viên miền Bắc rõ nét, chạy 100% trên máy không phụ thuộc mạng",
        dsp_preset="drama_female_emotional",
    ),
    VoiceProfileDTO(
        profile_id="gemini_actor_aoede",
        display_name="Nghệ Sĩ AI Aoede (Gemini Studio) — Nữ Ấm Áp Kể Chuyện Thủ Công & Nhạc Cụ",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        voice_id_or_sample_path="Aoede",
        speed_rate=1.02,
        pitch_hz=0.0,
        emotion_prompt="Đọc tự nhiên như người chơi violin lâu năm đang tâm sự nhẹ nhàng, truyền cảm và sang trọng",
        dsp_preset="luxury_silk_female",
    ),
    VoiceProfileDTO(
        profile_id="gemini_actor_puck",
        display_name="Chuyên Gia AI Puck (Gemini Studio) — Nam Thân Thiện Tư Vấn Trải Nghiệm",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        voice_id_or_sample_path="Puck",
        speed_rate=1.04,
        pitch_hz=-0.5,
        emotion_prompt="Giọng nam gần gũi, chân thành, nhấn nhá tự nhiên như đang trò chuyện trực tiếp tại cửa hàng",
        dsp_preset="artisan_warm_studio",
    ),
    VoiceProfileDTO(
        profile_id="gemini_actor_charon",
        display_name="Diễn Viên AI Charon (Gemini Studio) — Nam Trầm Sâu Điện Ảnh & Luxury",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        voice_id_or_sample_path="Charon",
        speed_rate=1.03,
        pitch_hz=-1.0,
        emotion_prompt="Giọng nam trầm sâu, sang trọng, nhịp chậm có chiều sâu điện ảnh",
        dsp_preset="movie_male_deep",
    ),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteRepository:
    """Thread-safe local SQLite repository matching ERD schema in Chapter 5.2."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._seed_default_voices()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        schema_sql = """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            mode TEXT NOT NULL,
            state TEXT NOT NULL,
            target_min_sec INTEGER NOT NULL DEFAULT 65,
            target_max_sec INTEGER NOT NULL DEFAULT 120,
            request_payload_json TEXT DEFAULT '{}',
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_media (
            media_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,
            local_video_path TEXT NOT NULL,
            audio_16k_wav_path TEXT NOT NULL,
            original_stereo_wav_path TEXT DEFAULT '',
            duration_ms INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            fps REAL NOT NULL,
            preview_frames_json TEXT NOT NULL DEFAULT '[]',
            detected_lang TEXT DEFAULT 'auto',
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS voice_profiles (
            profile_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            tier TEXT NOT NULL,
            voice_id_or_sample_path TEXT NOT NULL,
            sample_ref_text TEXT DEFAULT '',
            speed_rate REAL NOT NULL DEFAULT 1.08,
            pitch_hz REAL NOT NULL DEFAULT 0.0,
            emotion_prompt TEXT DEFAULT '',
            dsp_preset TEXT DEFAULT 'movie_male_deep',
            cloud_vendor TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS render_configs (
            config_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL UNIQUE,
            voice_profile_id TEXT NOT NULL,
            layout_config_json TEXT NOT NULL,
            audio_config_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (voice_profile_id) REFERENCES voice_profiles(profile_id)
        );

        CREATE TABLE IF NOT EXISTS video_clips (
            clip_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            part_number INTEGER NOT NULL,
            start_ms INTEGER NOT NULL,
            end_ms INTEGER NOT NULL,
            hook_banner_title TEXT NOT NULL,
            highlight_score REAL NOT NULL DEFAULT 80.0,
            append_cta_outro INTEGER NOT NULL DEFAULT 1,
            master_audio_path TEXT DEFAULT '',
            ass_subtitle_path TEXT DEFAULT '',
            output_mp4_path TEXT DEFAULT '',
            cover_jpg_path TEXT DEFAULT '',
            render_status TEXT NOT NULL DEFAULT 'PENDING',
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS subtitle_segments (
            segment_id TEXT PRIMARY KEY,
            clip_id TEXT NOT NULL,
            seq_index INTEGER NOT NULL,
            rel_start_ms INTEGER NOT NULL,
            rel_end_ms INTEGER NOT NULL,
            original_text TEXT DEFAULT '',
            vi_narration_text TEXT NOT NULL,
            image_prompt TEXT DEFAULT '',
            stock_keywords_json TEXT DEFAULT '[]',
            visual_asset_path TEXT DEFAULT '',
            matched_image_index INTEGER DEFAULT NULL,
            is_real_demo_slot INTEGER DEFAULT 0,
            callout_label TEXT DEFAULT '',
            FOREIGN KEY (clip_id) REFERENCES video_clips(clip_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS seo_metadata (
            seo_id TEXT PRIMARY KEY,
            clip_id TEXT NOT NULL UNIQUE,
            yt_shorts_title TEXT NOT NULL,
            yt_shorts_desc TEXT NOT NULL,
            yt_shorts_tags_json TEXT NOT NULL DEFAULT '[]',
            tiktok_caption TEXT NOT NULL,
            tiktok_hashtags_json TEXT NOT NULL DEFAULT '[]',
            pinned_comment TEXT DEFAULT '',
            FOREIGN KEY (clip_id) REFERENCES video_clips(clip_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS product_templates (
            template_id TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            product_category TEXT NOT NULL,
            raw_description TEXT DEFAULT '',
            call_to_action TEXT DEFAULT '',
            offer_badge TEXT DEFAULT '',
            contact_badge TEXT DEFAULT '',
            qr_code_content TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS brand_kits (
            kit_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        with self._connect() as conn:
            conn.executescript(schema_sql)
            proj_cols = [r["name"] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
            if "request_payload_json" not in proj_cols:
                conn.execute(
                    "ALTER TABLE projects ADD COLUMN request_payload_json TEXT DEFAULT '{}'"
                )
            vp_cols = [
                r["name"] for r in conn.execute("PRAGMA table_info(voice_profiles)").fetchall()
            ]
            if "emotion_prompt" not in vp_cols:
                conn.execute(
                    "ALTER TABLE voice_profiles ADD COLUMN emotion_prompt TEXT DEFAULT ''"
                )
            if "dsp_preset" not in vp_cols:
                conn.execute(
                    "ALTER TABLE voice_profiles ADD COLUMN dsp_preset TEXT DEFAULT 'movie_male_deep'"
                )
            seg_cols = [
                r["name"] for r in conn.execute("PRAGMA table_info(subtitle_segments)").fetchall()
            ]
            if "matched_image_index" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN matched_image_index INTEGER DEFAULT NULL"
                )
            if "is_real_demo_slot" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN is_real_demo_slot INTEGER DEFAULT 0"
                )
            if "callout_label" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN callout_label TEXT DEFAULT ''"
                )
            if "voice_speed_override" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN voice_speed_override REAL DEFAULT NULL"
                )
            if "voice_pitch_override" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN voice_pitch_override REAL DEFAULT NULL"
                )
            seo_cols = [
                r["name"] for r in conn.execute("PRAGMA table_info(seo_metadata)").fetchall()
            ]
            if "pinned_comment" not in seo_cols:
                conn.execute(
                    "ALTER TABLE seo_metadata ADD COLUMN pinned_comment TEXT DEFAULT ''"
                )
        self._seed_default_product_templates()

    def _seed_default_voices(self) -> None:
        """Upsert built-in default presets so upgrades immediately take effect while preserving user clones."""
        for vp in DEFAULT_VOICE_PROFILES:
            self.upsert_voice_profile(vp)

    def upsert_voice_profile(self, profile: VoiceProfileDTO) -> None:
        """Create or update a VoiceProfileDTO in SQLite."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO voice_profiles
                (profile_id, display_name, tier, voice_id_or_sample_path, sample_ref_text,
                 speed_rate, pitch_hz, emotion_prompt, dsp_preset, cloud_vendor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    tier=excluded.tier,
                    voice_id_or_sample_path=excluded.voice_id_or_sample_path,
                    sample_ref_text=excluded.sample_ref_text,
                    speed_rate=excluded.speed_rate,
                    pitch_hz=excluded.pitch_hz,
                    emotion_prompt=excluded.emotion_prompt,
                    dsp_preset=excluded.dsp_preset,
                    cloud_vendor=excluded.cloud_vendor
                """,
                (
                    profile.profile_id,
                    profile.display_name,
                    profile.tier.value,
                    profile.voice_id_or_sample_path,
                    profile.sample_ref_text,
                    profile.speed_rate,
                    profile.pitch_hz,
                    profile.emotion_prompt,
                    profile.dsp_preset,
                    profile.cloud_vendor,
                ),
            )

    def list_voice_profiles(self) -> List[VoiceProfileDTO]:
        """Return all registered voice profiles."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM voice_profiles ORDER BY rowid ASC").fetchall()
        return [
            VoiceProfileDTO(
                profile_id=r["profile_id"],
                display_name=r["display_name"],
                tier=VoiceTier(r["tier"]),
                voice_id_or_sample_path=r["voice_id_or_sample_path"],
                sample_ref_text=r["sample_ref_text"] or "",
                speed_rate=float(r["speed_rate"]),
                pitch_hz=float(r["pitch_hz"]),
                emotion_prompt=r["emotion_prompt"] or "",
                dsp_preset=r["dsp_preset"] or "movie_male_deep",
                cloud_vendor=r["cloud_vendor"],
            )
            for r in rows
        ]

    def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfileDTO]:
        """Fetch a single VoiceProfileDTO by ID."""
        for vp in self.list_voice_profiles():
            if vp.profile_id == profile_id:
                return vp
        return None

    def create_project(
        self,
        project_id: str,
        name: str,
        mode: ProjectMode,
        target_min_sec: int = 65,
        target_max_sec: int = 120,
        request_payload_json: str = "{}",
    ) -> Dict[str, Any]:
        """Insert a new project record in DRAFT state."""
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects
                (id, name, mode, state, target_min_sec, target_max_sec, request_payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    name,
                    mode.value,
                    JobState.DRAFT.value,
                    target_min_sec,
                    target_max_sec,
                    request_payload_json,
                    now,
                    now,
                ),
            )
        return self.get_project(project_id) or {}

    def update_project_state(
        self, project_id: str, state: JobState, error_message: str = ""
    ) -> None:
        """Transition project job state and persist optional error details."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE projects SET state = ?, error_message = ?, updated_at = ? WHERE id = ?",
                (state.value, error_message, _utc_now_iso(), project_id),
            )

    def save_source_media(self, media: MediaAssetDTO, source_type: str = "LOCAL_FILE") -> None:
        """Persist MediaAssetDTO output from Module M01."""
        frames_json = json.dumps([str(p) for p in media.preview_frames], ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_media
                (media_id, project_id, source_type, local_video_path, audio_16k_wav_path,
                 original_stereo_wav_path, duration_ms, width, height, fps, preview_frames_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    media.media_id,
                    media.project_id,
                    source_type,
                    str(media.video_path),
                    str(media.audio_16k_wav_path),
                    str(media.original_stereo_wav_path) if media.original_stereo_wav_path else "",
                    media.duration_ms,
                    media.width,
                    media.height,
                    media.fps,
                    frames_json,
                ),
            )

    def save_cut_plan(self, cut_plan: CutPlanDTO) -> None:
        """Persist CutPlanDTO clips and subtitle/narration lines from Module M03."""
        with self._connect() as conn:
            conn.execute("DELETE FROM video_clips WHERE project_id = ?", (cut_plan.project_id,))
            for clip in cut_plan.clips:
                conn.execute(
                    """
                    INSERT INTO video_clips
                    (clip_id, project_id, part_number, start_ms, end_ms, hook_banner_title, highlight_score, append_cta_outro)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clip.clip_id,
                        clip.project_id,
                        clip.part_number,
                        clip.source_start_ms,
                        clip.source_end_ms,
                        clip.hook_banner_title,
                        clip.highlight_score,
                        1 if clip.append_cta_outro else 0,
                    ),
                )
                for line in clip.lines:
                    seg_id = f"{clip.clip_id}_seg_{line.seq_index:04d}"
                    conn.execute(
                        """
                        INSERT INTO subtitle_segments
                        (segment_id, clip_id, seq_index, rel_start_ms, rel_end_ms, original_text,
                         vi_narration_text, image_prompt, stock_keywords_json, matched_image_index,
                         is_real_demo_slot, callout_label, voice_speed_override, voice_pitch_override)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            seg_id,
                            clip.clip_id,
                            line.seq_index,
                            line.rel_start_ms,
                            line.rel_end_ms,
                            line.original_text,
                            line.vi_text,
                            line.image_prompt,
                            json.dumps(line.stock_keywords, ensure_ascii=False),
                            line.matched_image_index,
                            1 if line.is_real_demo_slot else 0,
                            line.callout_label,
                            line.voice_speed_override,
                            line.voice_pitch_override,
                        ),
                    )

    def save_render_output(self, render_out: RenderOutputDTO) -> None:
        """Record completed MP4 output path from Module M06."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE video_clips
                SET output_mp4_path = ?, cover_jpg_path = ?, render_status = 'COMPLETED'
                WHERE clip_id = ?
                """,
                (
                    str(render_out.output_mp4_path),
                    str(render_out.cover_jpg_path) if render_out.cover_jpg_path else "",
                    render_out.clip_id,
                ),
            )

    def save_seo_package(self, seo: SEOPackageDTO) -> None:
        """Persist generated YouTube Shorts & TikTok SEO package for a clip."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO seo_metadata
                (seo_id, clip_id, yt_shorts_title, yt_shorts_desc, yt_shorts_tags_json,
                 tiktok_caption, tiktok_hashtags_json, pinned_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"seo_{seo.clip_id}",
                    seo.clip_id,
                    seo.yt_shorts_title,
                    seo.yt_shorts_description,
                    json.dumps(seo.yt_shorts_tags, ensure_ascii=False),
                    seo.tiktok_caption,
                    json.dumps(seo.tiktok_hashtags, ensure_ascii=False),
                    seo.pinned_comment,
                ),
            )

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve project details along with its clips and SEO packages."""
        with self._connect() as conn:
            proj = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not proj:
                return None
            media = conn.execute(
                "SELECT * FROM source_media WHERE project_id = ?", (project_id,)
            ).fetchone()
            clips_rows = conn.execute(
                "SELECT * FROM video_clips WHERE project_id = ? ORDER BY part_number ASC",
                (project_id,),
            ).fetchall()

            clips_data: List[Dict[str, Any]] = []
            for cr in clips_rows:
                cid = cr["clip_id"]
                segs = conn.execute(
                    "SELECT * FROM subtitle_segments WHERE clip_id = ? ORDER BY seq_index ASC",
                    (cid,),
                ).fetchall()
                seo = conn.execute(
                    "SELECT * FROM seo_metadata WHERE clip_id = ?", (cid,)
                ).fetchone()
                clip_dict = dict(cr)
                clip_dict["lines"] = [dict(s) for s in segs]
                clip_dict["seo"] = dict(seo) if seo else None
                clips_data.append(clip_dict)

            result = dict(proj)
            result["source_media"] = dict(media) if media else None
            result["clips"] = clips_data
            return result

    def list_projects(self) -> List[Dict[str, Any]]:
        """Return summary list of all projects ordered newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Delete a project and all cascaded clips/subtitles/SEO records from SQLite."""
        existing = self.get_project(project_id)
        if not existing:
            return None
        with self._connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return existing

    def _seed_default_product_templates(self) -> None:
        with self._connect() as conn:
            cnt = conn.execute("SELECT COUNT(*) AS c FROM product_templates").fetchone()["c"]
        if cnt > 0:
            return
        defaults = [
            SavedProductTemplateDTO(
                template_id="tpl_violin_avaro_s2",
                product_name="Đàn Violin Avaro S2 & S2S Gỗ Thịt Cao Cấp",
                product_category=ProductCategory.MUSICAL_INSTRUMENT,
                raw_description=(
                    "• Mặt top: Gỗ thịt (Solid Wood) cho âm vang dày và ấm.\n"
                    "• Lưng và hông: Gỗ Maple cao cấp vân đẹp sắc nét.\n"
                    "• Mặt phím: Gỗ mun (Ebony) bền bỉ, bấm êm tay.\n"
                    "• Bộ khóa Peg: Gỗ cao cấp giữ dây chuẩn xác.\n"
                    "• Giữ dây: Kim loại bản S2; bản S2S dùng chất liệu gỗ.\n"
                    "• Tặng trọn bộ phụ kiện: Vĩ kéo, Nhựa thông, Kê vai KPE, Sách học violin.\n"
                    "• Hỗ trợ test đàn trực tiếp tại Hà Nội hoặc quay clip âm mộc gửi riêng."
                ),
                call_to_action="Nhắn trực tiếp cho shop hoặc để lại bình luận để nhận video test chất âm mộc và ưu đãi trọn bộ phụ kiện hôm nay!",
                offer_badge="🎁 Tặng Trọn Bộ Phụ Kiện Sẵn Chơi",
                contact_badge="📍 Test Đàn Hà Nội • Nhận Clip Âm Mộc",
                qr_code_content="https://www.sonmusic.vn",
            ),
            SavedProductTemplateDTO(
                template_id="tpl_fashion_office_set",
                product_name="Set Áo Sơ Mi & Quần Âu Thiết Kế Tôn Dáng Cao Cấp",
                product_category=ProductCategory.FASHION_APPAREL,
                raw_description=(
                    "• Chất liệu: Vải tuyết mưa mềm mát, đứng form, hạn chế nhăn tối đa.\n"
                    "• Thiết kế: Chiết eo tinh tế che khuyết điểm vòng 2, tôn dáng chân dài.\n"
                    "• Đường may: Tỉ mỉ từng đường kim mũi chỉ, đủ size từ S đến XL.\n"
                    "• Quyền lợi: Kiểm tra mặc thử ưng ý trước khi nhận hàng."
                ),
                call_to_action="Để lại chiều cao cân nặng dưới bình luận để shop tư vấn chuẩn size ngay hôm nay nhé!",
                offer_badge="🔥 Ưu Đãi Hôm Nay • Đủ Size S - XL",
                contact_badge="🚚 Kiểm Hàng Trước Khi Nhận • Hỗ Trợ Đổi Size",
                qr_code_content="",
            ),
        ]
        for tpl in defaults:
            self.upsert_product_template(tpl)

    def list_product_templates(self) -> List[SavedProductTemplateDTO]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM product_templates ORDER BY updated_at DESC"
            ).fetchall()
        return [
            SavedProductTemplateDTO(
                template_id=r["template_id"],
                product_name=r["product_name"],
                product_category=ProductCategory(r["product_category"]),
                raw_description=r["raw_description"] or "",
                call_to_action=r["call_to_action"] or "",
                offer_badge=r["offer_badge"] or "",
                contact_badge=r["contact_badge"] or "",
                qr_code_content=r["qr_code_content"] or "",
            )
            for r in rows
        ]

    def upsert_product_template(self, tpl: SavedProductTemplateDTO) -> SavedProductTemplateDTO:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO product_templates
                (template_id, product_name, product_category, raw_description,
                 call_to_action, offer_badge, contact_badge, qr_code_content, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(template_id) DO UPDATE SET
                    product_name=excluded.product_name,
                    product_category=excluded.product_category,
                    raw_description=excluded.raw_description,
                    call_to_action=excluded.call_to_action,
                    offer_badge=excluded.offer_badge,
                    contact_badge=excluded.contact_badge,
                    qr_code_content=excluded.qr_code_content,
                    updated_at=excluded.updated_at
                """,
                (
                    tpl.template_id,
                    tpl.product_name,
                    tpl.product_category.value,
                    tpl.raw_description,
                    tpl.call_to_action,
                    tpl.offer_badge,
                    tpl.contact_badge,
                    tpl.qr_code_content,
                    _utc_now_iso(),
                ),
            )
        return tpl

    def delete_product_template(self, template_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM product_templates WHERE template_id = ?", (template_id,)
            )
            return cur.rowcount > 0

    def get_brand_kit(self, kit_id: str = "default_brand_kit") -> BrandKitDTO:
        """Load persistent store BrandKitDTO (or return clean default if none saved yet)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM brand_kits WHERE kit_id = ?", (kit_id,)
            ).fetchone()
        if not row:
            return BrandKitDTO(
                kit_id=kit_id,
                brand_name="",
                showroom_address="",
                hotline_or_web="",
                preferred_framing=ProductFramingStyle.BLURRED_STUDIO_CARD,
                preferred_transition=TransitionStyle.CAPCUT_DISSOLVE,
            )
        try:
            data = json.loads(row["payload_json"] or "{}")
            return BrandKitDTO(**data)
        except Exception:
            return BrandKitDTO(kit_id=kit_id)

    def save_brand_kit(self, kit: BrandKitDTO) -> BrandKitDTO:
        """Persist store BrandKitDTO in SQLite."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO brand_kits (kit_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(kit_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (kit.kit_id, kit.model_dump_json(), _utc_now_iso()),
            )
        return kit

    def export_store_catalog_bundle(self) -> Dict[str, Any]:
        """Export Brand Kit, saved Product Templates, and custom cloned Voices as JSON-serializable dict."""
        bk = self.get_brand_kit()
        bk_dict = json.loads(bk.model_dump_json())
        if bk.logo_path:
            bk_dict["logo_filename"] = bk.logo_path.name

        custom_voices: List[Dict[str, Any]] = []
        for vp in self.list_voice_profiles():
            if vp.tier == VoiceTier.LOCAL_F5_CLONE:
                vd = vp.model_dump()
                sp = Path(vp.voice_id_or_sample_path)
                vd["sample_filename"] = sp.name
                custom_voices.append(vd)

        return {
            "app": "ChaosShortVideo",
            "schema_version": "3.1",
            "exported_at": _utc_now_iso(),
            "brand_kit": bk_dict,
            "product_templates": [t.model_dump() for t in self.list_product_templates()],
            "custom_voices": custom_voices,
        }

    def import_store_catalog_bundle(
        self, bundle: Dict[str, Any], assets_dir: Path
    ) -> Dict[str, int]:
        """Restore Brand Kit, Product Templates, and custom cloned Voices with remapped local asset paths."""
        tpl_count = 0
        for raw_t in bundle.get("product_templates") or []:
            if not isinstance(raw_t, dict) or not raw_t.get("product_name"):
                continue
            try:
                dto_t = SavedProductTemplateDTO(
                    template_id=str(raw_t.get("template_id") or f"tpl_{tpl_count + 1}"),
                    product_name=str(raw_t["product_name"]),
                    product_category=ProductCategory(
                        raw_t.get("product_category") or ProductCategory.MUSICAL_INSTRUMENT.value
                    ),
                    raw_description=str(raw_t.get("raw_description") or ""),
                    call_to_action=str(raw_t.get("call_to_action") or ""),
                    offer_badge=str(raw_t.get("offer_badge") or ""),
                    contact_badge=str(raw_t.get("contact_badge") or ""),
                    qr_code_content=str(raw_t.get("qr_code_content") or ""),
                )
                self.upsert_product_template(dto_t)
                tpl_count += 1
            except Exception:
                continue

        voice_count = 0
        for raw_v in bundle.get("custom_voices") or []:
            if not isinstance(raw_v, dict) or not raw_v.get("profile_id"):
                continue
            try:
                sample_fname = str(raw_v.get("sample_filename") or "")
                remapped_sample = str(raw_v.get("voice_id_or_sample_path") or "")
                if sample_fname:
                    candidate_wav = assets_dir / "voice_samples" / Path(sample_fname).name
                    if candidate_wav.exists():
                        remapped_sample = str(candidate_wav)
                vp_dto = VoiceProfileDTO(
                    profile_id=str(raw_v["profile_id"]),
                    display_name=str(raw_v.get("display_name") or "Giọng Nhân Bản"),
                    tier=VoiceTier.LOCAL_F5_CLONE,
                    voice_id_or_sample_path=remapped_sample,
                    sample_ref_text=str(raw_v.get("sample_ref_text") or ""),
                    speed_rate=float(raw_v.get("speed_rate") or 1.04),
                    pitch_hz=float(raw_v.get("pitch_hz") or 0.0),
                    emotion_prompt=str(raw_v.get("emotion_prompt") or ""),
                    dsp_preset=str(raw_v.get("dsp_preset") or "artisan_warm_studio"),
                )
                self.upsert_voice_profile(vp_dto)
                voice_count += 1
            except Exception:
                continue

        bk_restored = 0
        raw_bk = bundle.get("brand_kit")
        if isinstance(raw_bk, dict):
            try:
                bk_copy = dict(raw_bk)
                logo_fname = str(bk_copy.pop("logo_filename", "") or "")
                if logo_fname:
                    candidate_logo = assets_dir / "logos" / Path(logo_fname).name
                    bk_copy["logo_path"] = str(candidate_logo) if candidate_logo.exists() else None
                elif bk_copy.get("logo_path") and not Path(str(bk_copy["logo_path"])).exists():
                    bk_copy["logo_path"] = None
                self.save_brand_kit(BrandKitDTO(**bk_copy))
                bk_restored = 1
            except Exception:
                pass

        return {
            "templates_restored": tpl_count,
            "voices_restored": voice_count,
            "brand_kit_restored": bk_restored,
        }

