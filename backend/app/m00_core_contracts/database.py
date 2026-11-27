"""SQLite persistence layer implementing the 7 ERD tables and emotional voice profiles."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from .config import WORKSPACE_ROOT
from .dtos import (
    BrandKitDTO,
    ClipSpecDTO,
    CutPlanDTO,
    MediaAssetDTO,
    ProjectGroupDTO,
    RenderOutputDTO,
    SavedBgVideoDTO,
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
    VoiceUseCaseCategory,
)

DEFAULT_VOICE_PROFILES: List[VoiceProfileDTO] = [
    # =========================================================================
    # NHÓM 1: LỒNG TIẾNG & THUYẾT MINH PHIM (MOVIE_DUB — 10 Giọng)
    # =========================================================================
    VoiceProfileDTO(
        profile_id="gemini_uslt_mytam",
        display_name="Mỹ Tâm USLT — Nữ Sài Gòn Thuyết Minh Phim Chiếu Rạp Mỹ (Chuẩn Tín Hiệu Vô Hình)",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Miền Nam", "Phim chiếu rạp Mỹ", "Chuẩn Tín Hiệu Vô Hình"],
        voice_id_or_sample_path="Kore",
        speed_rate=1.02,
        pitch_hz=0.0,
        emotion_prompt=(
            "Đọc bằng giọng nữ miền Nam Sài Gòn trung trầm, điềm tĩnh, nghiêm nghị, rõ từng chữ "
            "chuẩn thuyết minh phim hành động Mỹ chiếu rạp (kiểu USLT / SCTV9), phát âm phương ngữ Nam Bộ tự nhiên"
        ),
        dsp_preset="cinema_uslt_female",
    ),
    VoiceProfileDTO(
        profile_id="clone_tin_hieu_vo_hinh",
        display_name="Giọng Mẫu Tín Hiệu Vô Hình — Nữ Nam Bộ Trích Gốc Phim Mẫu (Voice Clone GPU)",
        tier=VoiceTier.LOCAL_F5_CLONE,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Mẫu gốc YouTube", "Miền Nam", "Thuyết minh USLT"],
        voice_id_or_sample_path=str(
            WORKSPACE_ROOT / "assets" / "voice_samples" / "ref_tin_hieu_vo_hinh_24k.wav"
        ),
        sample_ref_text=(
            "Nhưng khi chính phủ chịu lắng nghe khoa học thì nó đã quá muộn rồi. "
            "Đại dịch đã khiến xã hội ngưng lại đột ngột."
        ),
        speed_rate=1.02,
        pitch_hz=0.0,
        emotion_prompt=(
            "Đọc bằng giọng nữ miền Nam Sài Gòn trung trầm, điềm tĩnh, nghiêm nghị, rõ chữ "
            "chuẩn thuyết minh phim chiếu rạp Mỹ Tín Hiệu Vô Hình, phát âm phương ngữ Nam Bộ tự nhiên"
        ),
        dsp_preset="cinema_uslt_female",
    ),
    VoiceProfileDTO(
        profile_id="gemini_cinema_fenrir",
        display_name="Quốc Khánh Cinema (Gemini Studio) — Nam Trầm Thuyết Minh Bom Tấn Hollywood",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Miền Nam", "Phim hành động Mỹ", "Nam trầm dày"],
        voice_id_or_sample_path="Fenrir",
        speed_rate=1.03,
        pitch_hz=-0.6,
        emotion_prompt=(
            "Đọc bằng giọng nam miền Nam trầm dày, uy lực, đĩnh đạc chuẩn thuyết minh phim hành động "
            "chiếu rạp Hollywood, ngắt nhịp dứt khoát và cuốn hút"
        ),
        dsp_preset="cinema_uslt_male",
    ),
    VoiceProfileDTO(
        profile_id="edge_nam_minh_movie",
        display_name="Minh Quân — Nam Trầm Thuyết Minh Phim Bộ / Tổng Tài (Đĩnh đạc)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Phim bộ", "Tổng tài", "Đĩnh đạc"],
        voice_id_or_sample_path="en-US-BrianMultilingualNeural",
        speed_rate=1.08,
        pitch_hz=-1.2,
        emotion_prompt="Giọng nam trầm ấm, đĩnh đạc, nhấn nhá kịch tính chuẩn thuyết minh phim bộ",
        dsp_preset="movie_male_deep",
    ),
    VoiceProfileDTO(
        profile_id="edge_nam_uslt_saigon",
        display_name="Chí Bảo — Nam Sài Gòn Thuyết Minh Phim Lẻ & Phim Hồng Kông (TVB / USLT)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Miền Nam", "Phim lẻ & TVB", "Rõ chữ"],
        voice_id_or_sample_path="ko-KR-HyunsuMultilingualNeural",
        speed_rate=1.05,
        pitch_hz=-0.6,
        emotion_prompt="Giọng nam miền Nam ấm rõ, nhịp điệu tự nhiên chuẩn thuyết minh phim lẻ và phim bộ TVB",
        dsp_preset="cinema_uslt_male",
    ),
    VoiceProfileDTO(
        profile_id="edge_hoang_vu_action",
        display_name="Hoàng Vũ — Nam Kịch Tính Phim Hành Động / Trinh Thám (Gay cấn)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Hành động", "Sinh tồn", "Gay cấn"],
        voice_id_or_sample_path="fr-FR-RemyMultilingualNeural",
        speed_rate=1.12,
        pitch_hz=-0.8,
        emotion_prompt="Giọng nam hồi hộp, dồn dập, nhấn mạnh các tình tiết gay cấn bất ngờ",
        dsp_preset="thriller_suspense",
    ),
    VoiceProfileDTO(
        profile_id="edge_hoai_my_drama",
        display_name="Thanh Thảo — Nữ Thuyết Minh Phim Ngôn Tình / Cổ Trang Sâu Lắng",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Cổ trang", "Ngôn tình", "Truyền cảm"],
        voice_id_or_sample_path="en-US-AvaMultilingualNeural",
        speed_rate=1.04,
        pitch_hz=0.0,
        emotion_prompt="Giọng nữ truyền cảm, mềm mại, giàu cảm xúc nội tâm cho phim cổ trang và tâm lý",
        dsp_preset="drama_female_emotional",
    ),
    VoiceProfileDTO(
        profile_id="gemini_cinema_leda",
        display_name="Thúy Hạnh VTV (Gemini Studio) — Nữ Bắc Thuyết Minh Phim Điện Ảnh Đĩnh Đạc",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Miền Bắc", "Phim truyền hình", "Chuẩn VTV"],
        voice_id_or_sample_path="Leda",
        speed_rate=1.02,
        pitch_hz=-0.2,
        emotion_prompt=(
            "Đọc bằng giọng nữ Hà Nội chuẩn đài truyền hình VTV, sang trọng, điềm đạm, "
            "nhấn nhá tinh tế cho thuyết minh phim truyện điện ảnh"
        ),
        dsp_preset="cinema_uslt_female",
    ),
    VoiceProfileDTO(
        profile_id="edge_bong_dem_horror",
        display_name="Bóng Đêm — Nam Trầm Lạnh Phim Kinh Dị / Tâm Lý Tội Phạm (Ám ảnh)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Kinh dị", "Trinh thám đêm", "Trầm lạnh"],
        voice_id_or_sample_path="en-AU-WilliamMultilingualNeural",
        speed_rate=0.98,
        pitch_hz=-2.0,
        emotion_prompt="Giọng nam trầm lạnh, nhịp chậm đầy bí ẩn cho phim kinh dị và giải mã vụ án",
        dsp_preset="horror_dark_male",
    ),
    VoiceProfileDTO(
        profile_id="local_25h_saigon_movie",
        display_name="Quỳnh Mai (Offline 0.1s) — Nữ Thuyết Minh Phim & Đọc Truyện Không Cần Mạng",
        tier=VoiceTier.LOCAL_ONNX_VITS,
        category=VoiceUseCaseCategory.MOVIE_DUB,
        tags=["Offline 0.1s", "Không cần mạng", "Nữ êm dịu"],
        voice_id_or_sample_path="vi_VN-25hours_single-low.onnx",
        speed_rate=1.03,
        pitch_hz=-0.2,
        emotion_prompt="Giọng nữ đọc truyện và thuyết minh phim êm dịu, chạy trực tiếp trên máy 0.1s",
        dsp_preset="cinema_uslt_female",
    ),

    # =========================================================================
    # NHÓM 2: CHUYÊN SHORT TIKTOK NHỊP NHANH (TIKTOK_SHORT — 7 Giọng)
    # =========================================================================
    VoiceProfileDTO(
        profile_id="edge_hoai_my_fast",
        display_name="Mai Phương — Nữ Review Nhịp Nhanh Bắt Trend TikTok (Giữ chân 3s đầu)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.TIKTOK_SHORT,
        tags=["TikTok Xu hướng", "Nhịp nhanh", "Bắt tai"],
        voice_id_or_sample_path="en-US-EmmaMultilingualNeural",
        speed_rate=1.15,
        pitch_hz=0.4,
        emotion_prompt="Giọng nữ trẻ trung, bắt tai, mở đầu cuốn hút giữ chân người xem lướt TikTok",
        dsp_preset="tiktok_punchy_bright",
    ),
    VoiceProfileDTO(
        profile_id="gemini_tiktok_zephyr",
        display_name="Bảo Ngọc GenZ (Gemini Studio) — Nữ Kể Drama / Storytime Bóc Phốt Cuốn Hút",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.TIKTOK_SHORT,
        tags=["Miền Nam", "Storytime Drama", "GenZ tự nhiên"],
        voice_id_or_sample_path="Zephyr",
        speed_rate=1.12,
        pitch_hz=0.2,
        emotion_prompt=(
            "Đọc bằng giọng nữ trẻ miền Nam GenZ năng động, biểu cảm sinh động, nhấn nhá kịch tính "
            "như đang kể drama nóng hổi trên TikTok"
        ),
        dsp_preset="tiktok_punchy_bright",
    ),
    VoiceProfileDTO(
        profile_id="edge_tuan_kiet_tiktok",
        display_name="Tuấn Kiệt — Nam Review Công Nghệ / Đời Sống Tốc Độ Cao (Sắc nét)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.TIKTOK_SHORT,
        tags=["Review nhanh", "Công nghệ & Mẹo", "Năng lượng cao"],
        voice_id_or_sample_path="it-IT-GiuseppeMultilingualNeural",
        speed_rate=1.16,
        pitch_hz=0.2,
        emotion_prompt="Giọng nam trẻ khỏe khoắn, tốc độ nhanh, đi thẳng vào trọng tâm cho video TikTok 30–60s",
        dsp_preset="tiktok_punchy_bright",
    ),
    VoiceProfileDTO(
        profile_id="edge_hai_dang_topfact",
        display_name="Hải Đăng — Nam Top 5 Sự Thật Giật Gân / Tóm Tắt Nhanh 60 Giây",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.TIKTOK_SHORT,
        tags=["Top sự thật", "Giật gân", "Tốc độ cao"],
        voice_id_or_sample_path="fr-FR-RemyMultilingualNeural",
        speed_rate=1.17,
        pitch_hz=-0.4,
        emotion_prompt="Giọng nam dồn dập, nhấn mạnh con số và chi tiết bất ngờ giữ tỷ lệ xem hết video",
        dsp_preset="tiktok_punchy_bright",
    ),
    VoiceProfileDTO(
        profile_id="edge_minh_chau_lifestyle",
        display_name="Minh Châu — Nữ Mẹo Vặt / Ẩm Thực & Vlog Đời Thường Sôi Động",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.TIKTOK_SHORT,
        tags=["Ẩm thực & Vlog", "Tươi sáng", "Thân thiện"],
        voice_id_or_sample_path="pt-BR-ThalitaMultilingualNeural",
        speed_rate=1.13,
        pitch_hz=0.6,
        emotion_prompt="Giọng nữ tươi tắn, giàu năng lượng tích cực cho clip ẩm thực, du lịch và mẹo hay",
        dsp_preset="tiktok_punchy_bright",
    ),
    VoiceProfileDTO(
        profile_id="gemini_tiktok_achird",
        display_name="Khôi Nguyên (Gemini Studio) — Nam Trẻ Bắt Trend Hài Hước & Phản Biện",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.TIKTOK_SHORT,
        tags=["Hài hước", "Góc nhìn mới", "Linh hoạt"],
        voice_id_or_sample_path="Achird",
        speed_rate=1.12,
        pitch_hz=0.0,
        emotion_prompt=(
            "Đọc bằng giọng nam trẻ trung, lanh lợi, dí dỏm kiểu nhà sáng tạo nội dung TikTok triệu view"
        ),
        dsp_preset="tiktok_punchy_bright",
    ),
    VoiceProfileDTO(
        profile_id="local_vivos_tiktok_fast",
        display_name="Tuấn Anh Sài Gòn (Offline 0.1s) — Nam Miền Nam Nhịp Nhanh Không Cần Mạng",
        tier=VoiceTier.LOCAL_ONNX_VITS,
        category=VoiceUseCaseCategory.TIKTOK_SHORT,
        tags=["Offline 0.1s", "Miền Nam", "Nhịp nhanh"],
        voice_id_or_sample_path="vi_VN-vivos-x_low.onnx#2",
        speed_rate=1.13,
        pitch_hz=0.0,
        emotion_prompt="Giọng nam miền Nam trẻ trung chạy offline siêu tốc 0.1s cho xuất hàng loạt TikTok",
        dsp_preset="tiktok_punchy_bright",
    ),

    # =========================================================================
    # NHÓM 3: CHUYÊN YOUTUBE SHORTS CHIỀU SÂU & TRI THỨC (YOUTUBE_SHORT — 8 Giọng)
    # =========================================================================
    VoiceProfileDTO(
        profile_id="gemini_yt_orus",
        display_name="Giáo Sư Hoàng Nam (Gemini Studio) — Nam Trầm Khoa Học, Vũ Trụ & Lịch Sử",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.YOUTUBE_SHORT,
        tags=["Khoa học & Lịch sử", "Chiều sâu", "Chuẩn Documentary"],
        voice_id_or_sample_path="Orus",
        speed_rate=1.03,
        pitch_hz=-0.8,
        emotion_prompt=(
            "Đọc bằng giọng nam trầm uyên bác, chững chạc, truyền cảm hứng khám phá như phim tài liệu "
            "khoa học vũ trụ và lịch sử trên YouTube Shorts"
        ),
        dsp_preset="yt_documentary_warm",
    ),
    VoiceProfileDTO(
        profile_id="edge_lan_anh_story",
        display_name="Lan Anh — Nữ Trầm Dịu Podcast Đêm Khuya & Tâm Lý Học (Chữa lành)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.YOUTUBE_SHORT,
        tags=["Podcast chữa lành", "Tâm lý học", "Sâu lắng"],
        voice_id_or_sample_path="fr-FR-VivienneMultilingualNeural",
        speed_rate=1.00,
        pitch_hz=-0.6,
        emotion_prompt="Giọng nữ nhẹ nhàng, sâu lắng, ngắt nghỉ giàu chiều sâu cảm xúc cho YouTube Shorts",
        dsp_preset="luxury_silk_female",
    ),
    VoiceProfileDTO(
        profile_id="edge_van_minh_knowledge",
        display_name="Văn Minh — Nam Phân Tích Tài Chính, Kinh Doanh & Tóm Tắt Sách",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.YOUTUBE_SHORT,
        tags=["Tài chính & Sách", "Mạch lạc", "Điềm đạm"],
        voice_id_or_sample_path="en-AU-WilliamMultilingualNeural",
        speed_rate=1.05,
        pitch_hz=-0.8,
        emotion_prompt="Giọng nam điềm đạm, đáng tin cậy, trình bày kiến thức kinh tế và bài học thành công",
        dsp_preset="yt_documentary_warm",
    ),
    VoiceProfileDTO(
        profile_id="gemini_actor_charon",
        display_name="Diễn Viên AI Charon (Gemini Studio) — Nam Trầm Sâu Bí Ẩn & Triết Lý",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.YOUTUBE_SHORT,
        tags=["Giải mã bí ẩn", "Triết lý", "Trầm sâu"],
        voice_id_or_sample_path="Charon",
        speed_rate=1.03,
        pitch_hz=-1.0,
        emotion_prompt="Giọng nam trầm sâu, sang trọng, nhịp chậm có chiều sâu điện ảnh và suy ngẫm",
        dsp_preset="movie_male_deep",
    ),
    VoiceProfileDTO(
        profile_id="gemini_actor_aoede",
        display_name="Nghệ Sĩ AI Aoede (Gemini Studio) — Nữ Ấm Áp Kể Chuyện Nghệ Thuật & Văn Hóa",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.YOUTUBE_SHORT,
        tags=["Nghệ thuật & Âm nhạc", "Truyền cảm", "Tinh tế"],
        voice_id_or_sample_path="Aoede",
        speed_rate=1.02,
        pitch_hz=0.0,
        emotion_prompt="Đọc tự nhiên như người làm nghệ thuật lâu năm đang tâm sự nhẹ nhàng, truyền cảm",
        dsp_preset="luxury_silk_female",
    ),
    VoiceProfileDTO(
        profile_id="edge_thu_ha_doc",
        display_name="Thu Hà — Nữ Thuyết Minh Khám Phá Thế Giới & Kiến Thức Thường Thức",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.YOUTUBE_SHORT,
        tags=["Khám phá", "Thiên nhiên", "Dễ nghe"],
        voice_id_or_sample_path="en-US-AvaMultilingualNeural",
        speed_rate=1.04,
        pitch_hz=-0.3,
        emotion_prompt="Giọng nữ trong trẻo, mạch lạc, dẫn dắt người xem khám phá kiến thức thú vị",
        dsp_preset="yt_documentary_warm",
    ),
    VoiceProfileDTO(
        profile_id="local_vais_studio",
        display_name="Ngọc Huyền (Offline 0.1s) — Nữ Bắc Chuẩn Đài Tin Tức & Kiến Thức",
        tier=VoiceTier.LOCAL_ONNX_VITS,
        category=VoiceUseCaseCategory.YOUTUBE_SHORT,
        tags=["Offline 0.1s", "Miền Bắc", "Chuẩn đài"],
        voice_id_or_sample_path="vi_VN-vais1000-medium.onnx",
        speed_rate=1.05,
        pitch_hz=0.0,
        emotion_prompt="Giọng phát thanh viên miền Bắc rõ nét, chạy 100% trên máy không phụ thuộc mạng",
        dsp_preset="drama_female_emotional",
    ),
    VoiceProfileDTO(
        profile_id="local_vivos_saigon_male",
        display_name="Minh Triết Sài Gòn (Offline 0.1s) — Nam Trầm Miền Nam Kể Chuyện Offline",
        tier=VoiceTier.LOCAL_ONNX_VITS,
        category=VoiceUseCaseCategory.YOUTUBE_SHORT,
        tags=["Offline 0.1s", "Miền Nam", "Nam trầm"],
        voice_id_or_sample_path="vi_VN-vivos-x_low.onnx#8",
        speed_rate=1.03,
        pitch_hz=-0.4,
        emotion_prompt="Giọng nam miền Nam trầm ấm chạy offline trực tiếp trên máy tính không cần mạng",
        dsp_preset="yt_documentary_warm",
    ),

    # =========================================================================
    # NHÓM 4: TƯ VẤN BÁN HÀNG & SHOWROOM CAO CẤP (ECOMMERCE_SALES — 5 Giọng)
    # =========================================================================
    VoiceProfileDTO(
        profile_id="edge_nam_nghe_nhan",
        display_name="Đức Trung — Nam Trầm Ấm Nghệ Nhân Nhạc Cụ & Đồ Gỗ Thủ Công (Truyền cảm)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.ECOMMERCE_SALES,
        tags=["Nhạc cụ & Đồ gỗ", "Chân thành", "Ấm áp"],
        voice_id_or_sample_path="en-US-AndrewMultilingualNeural",
        speed_rate=1.01,
        pitch_hz=-0.8,
        emotion_prompt="Giọng nam trầm ấm, điềm đạm như nghệ nhân chia sẻ mộc mạc về tiếng đàn và chất gỗ",
        dsp_preset="artisan_warm_studio",
    ),
    VoiceProfileDTO(
        profile_id="edge_nu_boutique_silk",
        display_name="Khánh Linh — Nữ Sang Trọng Tư Vấn Nhạc Cụ & Thời Trang Thiết Kế (Mềm mại)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.ECOMMERCE_SALES,
        tags=["Showroom & Boutique", "Thanh lịch", "Mềm mại"],
        voice_id_or_sample_path="en-US-AvaMultilingualNeural",
        speed_rate=1.01,
        pitch_hz=-0.4,
        emotion_prompt="Giọng nữ sang trọng, thanh lịch, tròn vành rõ chữ cho showroom đàn và thời trang",
        dsp_preset="luxury_silk_female",
    ),
    VoiceProfileDTO(
        profile_id="edge_gia_bao_consult",
        display_name="Gia Bảo — Nam Trẻ Trung Tư Vấn Thực Tế & So Sánh Phiên Bản (Rõ ràng)",
        tier=VoiceTier.EDGE_TTS,
        category=VoiceUseCaseCategory.ECOMMERCE_SALES,
        tags=["Tư vấn mua hàng", "So sánh A/B", "Rõ ràng"],
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
        category=VoiceUseCaseCategory.ECOMMERCE_SALES,
        tags=["Thời trang & Mỹ phẩm", "Tươi sáng", "Hiện đại"],
        voice_id_or_sample_path="pt-BR-ThalitaMultilingualNeural",
        speed_rate=1.06,
        pitch_hz=0.5,
        emotion_prompt="Giọng nữ tươi tắn, tự nhiên, tôn vẻ thanh lịch cho sản phẩm thời trang",
        dsp_preset="drama_female_emotional",
    ),
    VoiceProfileDTO(
        profile_id="gemini_actor_puck",
        display_name="Chuyên Gia AI Puck (Gemini Studio) — Nam Thân Thiện Tư Vấn Trải Nghiệm",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        category=VoiceUseCaseCategory.ECOMMERCE_SALES,
        tags=["Tư vấn 1-1", "Gần gũi", "Chân thực"],
        voice_id_or_sample_path="Puck",
        speed_rate=1.04,
        pitch_hz=-0.5,
        emotion_prompt="Giọng nam gần gũi, chân thành, nhấn nhá tự nhiên như đang trò chuyện trực tiếp tại cửa hàng",
        dsp_preset="artisan_warm_studio",
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
            category TEXT NOT NULL DEFAULT 'MOVIE_DUB',
            tags_json TEXT NOT NULL DEFAULT '[]',
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

        CREATE TABLE IF NOT EXISTS project_groups (
            group_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            color_tag TEXT DEFAULT '#0ea5e9',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bg_videos (
            bg_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category_tag TEXT DEFAULT 'Chill / Đời sống',
            local_path TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            width INTEGER NOT NULL DEFAULT 1080,
            height INTEGER NOT NULL DEFAULT 1920,
            created_at TEXT NOT NULL
        );
        """
        with self._connect() as conn:
            conn.executescript(schema_sql)
            proj_cols = [r["name"] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
            if "request_payload_json" not in proj_cols:
                conn.execute(
                    "ALTER TABLE projects ADD COLUMN request_payload_json TEXT DEFAULT '{}'"
                )
            if "parent_group_id" not in proj_cols:
                conn.execute(
                    "ALTER TABLE projects ADD COLUMN parent_group_id TEXT DEFAULT NULL"
                )
            # Recover any stale in-flight projects from an abruptly closed previous server session
            conn.execute(
                """
                UPDATE projects
                SET state = 'PAUSED',
                    error_message = CASE
                        WHEN error_message = '' THEN 'Phiên trước đã tạm đóng — bấm Tiếp tục để chạy tiếp dự án.'
                        ELSE error_message
                    END
                WHERE state IN (
                    'QUEUED', 'INGESTING', 'TRANSCRIBING_GPU', 'AI_ANALYZING',
                    'GENERATING_ASSETS', 'RENDERING_NVENC', 'PACKAGING_SEO'
                )
                """
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
            if "category" not in vp_cols:
                conn.execute(
                    "ALTER TABLE voice_profiles ADD COLUMN category TEXT DEFAULT 'MOVIE_DUB'"
                )
            if "tags_json" not in vp_cols:
                conn.execute(
                    "ALTER TABLE voice_profiles ADD COLUMN tags_json TEXT DEFAULT '[]'"
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
            if "voice_profile_override" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN voice_profile_override TEXT DEFAULT NULL"
                )
            if "speaker_handle" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN speaker_handle TEXT DEFAULT ''"
                )
            if "display_card_text" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN display_card_text TEXT DEFAULT ''"
                )
            if "likes_display" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN likes_display TEXT DEFAULT ''"
                )
            if "is_op_post" not in seg_cols:
                conn.execute(
                    "ALTER TABLE subtitle_segments ADD COLUMN is_op_post INTEGER DEFAULT 0"
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
        tags_str = json.dumps(profile.tags, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO voice_profiles
                (profile_id, display_name, tier, category, tags_json, voice_id_or_sample_path, sample_ref_text,
                 speed_rate, pitch_hz, emotion_prompt, dsp_preset, cloud_vendor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    tier=excluded.tier,
                    category=excluded.category,
                    tags_json=excluded.tags_json,
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
                    profile.category.value,
                    tags_str,
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
        """Return all registered voice profiles ordered cleanly by category and priority."""
        default_order = {vp.profile_id: idx for idx, vp in enumerate(DEFAULT_VOICE_PROFILES)}
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM voice_profiles ORDER BY rowid ASC").fetchall()
        profiles: List[VoiceProfileDTO] = []
        for r in rows:
            raw_cat = r["category"] if "category" in r.keys() and r["category"] else "MOVIE_DUB"
            try:
                cat_enum = VoiceUseCaseCategory(raw_cat)
            except ValueError:
                cat_enum = VoiceUseCaseCategory.MOVIE_DUB
            try:
                parsed_tags = json.loads(r["tags_json"] or "[]") if "tags_json" in r.keys() else []
            except Exception:
                parsed_tags = []
            profiles.append(
                VoiceProfileDTO(
                    profile_id=r["profile_id"],
                    display_name=r["display_name"],
                    tier=VoiceTier(r["tier"]),
                    category=cat_enum,
                    tags=parsed_tags if isinstance(parsed_tags, list) else [],
                    voice_id_or_sample_path=r["voice_id_or_sample_path"],
                    sample_ref_text=r["sample_ref_text"] or "",
                    speed_rate=float(r["speed_rate"]),
                    pitch_hz=float(r["pitch_hz"]),
                    emotion_prompt=r["emotion_prompt"] or "",
                    dsp_preset=r["dsp_preset"] or "movie_male_deep",
                    cloud_vendor=r["cloud_vendor"],
                )
            )
        # Put custom user-cloned voices right at the top of their category, followed by curated order
        profiles.sort(
            key=lambda p: (
                0 if p.profile_id not in default_order else 1,
                default_order.get(p.profile_id, 999),
            )
        )
        return profiles

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
        parent_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a new project record in DRAFT state (optionally linked to a parent project group)."""
        now = _utc_now_iso()
        clean_group = (parent_group_id or "").strip() or None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects
                (id, name, mode, state, target_min_sec, target_max_sec, request_payload_json, parent_group_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    name,
                    mode.value,
                    JobState.DRAFT.value,
                    target_min_sec,
                    target_max_sec,
                    request_payload_json,
                    clean_group,
                    now,
                    now,
                ),
            )
        return self.get_project(project_id) or {}

    def list_project_groups(self) -> List[ProjectGroupDTO]:
        """List all parent project containers with live child counts."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT g.*,
                       COUNT(p.id) AS project_count,
                       SUM(CASE WHEN p.state = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_count
                FROM project_groups g
                LEFT JOIN projects p ON p.parent_group_id = g.group_id
                GROUP BY g.group_id
                ORDER BY g.updated_at DESC
                """
            ).fetchall()
        return [
            ProjectGroupDTO(
                group_id=r["group_id"],
                name=r["name"],
                description=r["description"] or "",
                color_tag=r["color_tag"] or "#0ea5e9",
                created_at=r["created_at"] or "",
                updated_at=r["updated_at"] or "",
                project_count=int(r["project_count"] or 0),
                completed_count=int(r["completed_count"] or 0),
            )
            for r in rows
        ]

    def upsert_project_group(
        self,
        group_id: str,
        name: str,
        description: str = "",
        color_tag: str = "#0ea5e9",
    ) -> ProjectGroupDTO:
        """Create or update a parent project folder."""
        now = _utc_now_iso()
        clean_color = (color_tag or "#0ea5e9").strip()[:24]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO project_groups (group_id, name, description, color_tag, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    color_tag=excluded.color_tag,
                    updated_at=excluded.updated_at
                """,
                (group_id, name.strip(), description.strip(), clean_color, now, now),
            )
        for g in self.list_project_groups():
            if g.group_id == group_id:
                return g
        return ProjectGroupDTO(
            group_id=group_id,
            name=name.strip(),
            description=description.strip(),
            color_tag=clean_color,
            created_at=now,
            updated_at=now,
        )

    def delete_project_group(self, group_id: str) -> None:
        """Delete parent project group while keeping all child projects intact (unassigned)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE projects SET parent_group_id = NULL WHERE parent_group_id = ?",
                (group_id,),
            )
            conn.execute("DELETE FROM project_groups WHERE group_id = ?", (group_id,))

    def assign_project_to_group(self, project_id: str, group_id: Optional[str]) -> None:
        """Move a child project into a parent project group (or detach when group_id is None/empty)."""
        clean_gid = (group_id or "").strip() or None
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "UPDATE projects SET parent_group_id = ?, updated_at = ? WHERE id = ?",
                (clean_gid, now, project_id),
            )
            if clean_gid:
                conn.execute(
                    "UPDATE project_groups SET updated_at = ? WHERE group_id = ?",
                    (now, clean_gid),
                )

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
                         is_real_demo_slot, callout_label, voice_speed_override, voice_pitch_override,
                         voice_profile_override, speaker_handle, display_card_text, likes_display, is_op_post)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            line.voice_profile_override,
                            line.speaker_handle,
                            line.display_card_text,
                            line.likes_display,
                            1 if line.is_op_post else 0,
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

    def list_bg_videos(self) -> List[SavedBgVideoDTO]:
        """Return saved reusable background videos whose files still exist on disk."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bg_videos ORDER BY created_at DESC"
            ).fetchall()
        items: List[SavedBgVideoDTO] = []
        for r in rows:
            p = Path(r["local_path"])
            if not p.exists():
                continue
            items.append(
                SavedBgVideoDTO(
                    bg_id=r["bg_id"],
                    title=r["title"],
                    category_tag=r["category_tag"] or "Chill / Đời sống",
                    local_path=p,
                    duration_ms=int(r["duration_ms"] or 0),
                    width=int(r["width"] or 1080),
                    height=int(r["height"] or 1920),
                    created_at=r["created_at"] or "",
                )
            )
        return items

    def upsert_bg_video(self, bg: SavedBgVideoDTO) -> SavedBgVideoDTO:
        """Save or update a reusable background video in the Studio Background Library."""
        now = bg.created_at or _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bg_videos (bg_id, title, category_tag, local_path, duration_ms, width, height, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bg_id) DO UPDATE SET
                    title=excluded.title,
                    category_tag=excluded.category_tag,
                    local_path=excluded.local_path,
                    duration_ms=excluded.duration_ms,
                    width=excluded.width,
                    height=excluded.height
                """,
                (
                    bg.bg_id,
                    bg.title.strip(),
                    bg.category_tag.strip(),
                    str(bg.local_path),
                    bg.duration_ms,
                    bg.width,
                    bg.height,
                    now,
                ),
            )
        return bg.model_copy(update={"created_at": now})

    def delete_bg_video(self, bg_id: str) -> Optional[Path]:
        """Remove a background video entry from SQLite and return its path."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT local_path FROM bg_videos WHERE bg_id = ?", (bg_id,)
            ).fetchone()
            conn.execute("DELETE FROM bg_videos WHERE bg_id = ?", (bg_id,))
        return Path(row["local_path"]) if row and row["local_path"] else None


