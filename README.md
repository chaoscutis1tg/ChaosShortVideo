# ShortVideo Studio AI — YouTube Shorts & TikTok

Hệ thống **Local Web Studio** tạo video ngắn đa năng chạy trực tiếp trên máy tính cá nhân (tối ưu cho **NVIDIA GeForce RTX 3060 12GB VRAM + FFmpeg `h264_nvenc`**), tuân thủ nghiêm ngặt kiến trúc phân rã **08 Module độc lập (`M00 -> M07`)** để dễ dàng kế thừa và chia việc làm nhóm.

---

## 1. Cách Khởi Động Nhanh (1 Chạm)

1. Bấm đúp vào tệp **[`start_studio.bat`](./start_studio.bat)** tại thư mục gốc `d:\ToolShortVideo`.
2. Trình duyệt sẽ tự động mở giao diện Studio tại: `http://127.0.0.1:8000`
3. Nhấn nút **⚙️ Cài đặt API Keys** ở góc phải trên màn hình để dán khóa `GEMINI_API_KEY` (lấy miễn phí tại Google AI Studio) cho tính năng viết kịch bản, dịch ngữ cảnh phim bộ và sinh gói SEO.

---

## 2. Cấu Trúc 08 Module Độc Lập Làm Việc Nhóm

| Module | Đường dẫn Backend | Đường dẫn Frontend | Trách nhiệm chính |
| :--- | :--- | :--- | :--- |
| **`M00`** | `backend/app/m00_core_contracts/` | `frontend/src/modules/m00_core_contracts/` | Hợp đồng `Pydantic DTOs`, `ABC Interfaces`, CSDL `SQLite` & khóa `GPUResourceManager`. |
| **`M01`** | `backend/app/m01_media_ingest/` | `frontend/src/modules/m01_m04_movie_studio/` | Nhập file máy, tải link `yt-dlp` / `m3u8`, kiểm tra `ffprobe`, tách WAV `16kHz` & ảnh mẫu. |
| **`M02`** | `backend/app/m02_asr_transcription/` | — | Nhận diện thoại bằng GPU (`Faster-Whisper` + tự giải phóng VRAM) & đọc `.srt` rời. |
| **`M03`** | `backend/app/m03_ai_content_brain/` | `frontend/src/modules/m03_topic_studio/` | Viết kịch bản từ chủ đề, dịch ngữ cảnh phim, chia tập thông minh `65–120s` & sinh gói SEO. |
| **`M04`** | `backend/app/m04_visual_producer/` | — | Sinh Ảnh AI chuyển động `Ken Burns` & tìm tải Stock Video dọc (`Pexels` / `Pixabay`). |
| **`M05`** | `backend/app/m05_voice_audio_mixer/` | `frontend/src/modules/m05_voice_lab/` | Giọng thuyết minh 3 tầng (`Edge-TTS`, `F5-TTS Voice Clone GPU`, `Cloud API`), `Audio Ducking 18%` & phụ đề `.ass`. |
| **`M06`** | `backend/app/m06_nvenc_compositor/` | `frontend/src/modules/m06_canvas_916/` | 3 bố cục `9:16`, bám mặt `Auto-Reframe`, che chữ ngoại ngữ gốc (`Hardsub Mask`), lách bản quyền & `h264_nvenc`. |
| **`M07`** | `backend/app/m07_studio_api/` | `frontend/src/modules/m07_review_and_seo/` | `PipelineOrchestrator`, REST API, WebSocket tiến độ, duyệt kịch bản trung gian & Copy SEO 1 chạm. |

---

## 3. Chạy Bộ Kiểm Thử Đơn Vị & Hợp Đồng Khớp Nối (Pytest)

```powershell
$env:PYTHONPATH="d:\ToolShortVideo\backend"
python -m pytest d:\ToolShortVideo\backend\tests -v
```

*(Tùy chọn nâng cấp Tầng 2 — Nhái giọng trang phim bất kỳ trên GPU RTX 3060: cài thêm `pip install f5-tts` khi bạn muốn kích hoạt mô hình huấn luyện/nhái giọng trực tiếp từ tệp mẫu 10–15s).*

