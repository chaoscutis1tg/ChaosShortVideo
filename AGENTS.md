# QUY TẮC KIẾN TRÚC, CODE SẠCH & PHÁT TRIỂN THEO MODULE (AGENT & TEAM RULES)

Mọi AI Agent và lập trình viên tham gia phát triển dự án **ShortVideo Studio AI** tại workspace này BẮT BUỘC tuân thủ nghiêm ngặt các quy tắc dưới đây trong mọi tác vụ thiết kế, viết mới, sửa đổi và kiểm thử mã nguồn.

## 1. Tuân Thủ Tài Liệu Phân Tích & Thiết Kế Hệ Thống
- Nguồn tham chiếu chuẩn duy nhất (Single Source of Truth) về kiến trúc, sơ đồ UML, biểu mẫu Use Case và phân rã module nằm tại `docs/Tai_Lieu_Phan_Tich_Thiet_Ke_He_Thong.md`.
- Khi triển khai tính năng, **bắt buộc làm lần lượt theo từng Module (`M00` -> `M07`)** đã định nghĩa trong Chương 6 của tài liệu, không viết gộp logic nhiều module vào một tệp lớn (God Object / Monolithic Script).

## 2. Phân Rã Module Độc Lập Để Làm Việc Nhóm (Team Collaboration)
Hệ thống Backend (`backend/app/`) và Frontend (`frontend/src/modules/`) phải giữ ranh giới cô lập tuyệt đối theo 8 Module để nhiều lập trình viên có thể chia nhánh Git làm song song mà không xung đột code:
1. `m00_core_contracts`: Chứa **duy nhất** các Hợp đồng Dữ liệu (`Pydantic v2 DTOs`), Lớp giao diện trừu tượng (`ABC Interfaces`), ngoại lệ chuẩn (`Custom Exceptions`), cấu hình và bộ khóa `GPUResourceManager`.
2. `m01_media_ingest`: Nhập tệp nội bộ, tải liên kết `yt-dlp` / `m3u8`, kiểm tra `ffprobe`, trích xuất âm thanh chuẩn và ảnh chụp mẫu.
3. `m02_asr_transcription`: Nhận diện lời thoại bằng GPU (`Faster-Whisper`) và đọc tệp phụ đề rời (`.srt`).
4. `m03_ai_content_brain`: Sinh kịch bản từ chủ đề, dịch lời thoại theo ngữ cảnh phim, chia tập thông minh (`65–120s`) và tạo gói SEO Shorts/TikTok.
5. `m04_visual_producer`: Tạo Ảnh AI kèm chuyển động `Ken Burns` và tìm tải Stock Video miễn phí (`Pexels` / `Pixabay`).
6. `m05_voice_audio_mixer`: Tổng hợp giọng thuyết minh 3 tầng (`Edge-TTS`, `F5-TTS Voice Clone GPU`, `Cloud API`), trộn âm `Audio Ducking` dìm nền gốc và xuất phụ đề `.ass`.
7. `m06_nvenc_compositor`: Dựng khung dọc `9:16` (3 bố cục), bám khuôn mặt `Auto-Reframe`, che chữ ngoại ngữ gốc (`Hardsub Mask`), áp bộ lọc lách bản quyền và kết xuất bằng `FFmpeg h264_nvenc`.
8. `m07_studio_api` & `frontend`: Tầng điều phối Pipeline (`Orchestrator`), REST API, WebSocket báo tiến độ và giao diện người dùng React.

**Quy tắc cấm phụ thuộc chéo:**
- Các module từ `m01` đến `m06` **TUYỆT ĐỐI KHÔNG** import trực tiếp các lớp nội bộ của nhau.
- Mọi module chỉ được phép import các `DTO` và `Interface` từ `m00_core_contracts`. Việc ghép nối luồng thực thi giữa các module chỉ được thực hiện tại tầng điều phối (`PipelineOrchestrator` trong `m07_studio_api`) hoặc qua Dependency Injection.

## 3. Khớp Nối Chặt Chẽ Đầu Vào — Đầu Ra (Strict Input/Output Contract Matching)
- Mọi hàm giao tiếp ở biên module bắt buộc khai báo đầy đủ kiểu dữ liệu (`Type Hints` trong Python / `TypeScript` hoặc `PropTypes` rõ ràng ở Frontend) sử dụng các `DTO` đã chốt trong `m00_core_contracts`:
  - `Output` của `m01_media_ingest` (`MediaAssetDTO`) phải khớp 100% với `Input` của `m02_asr_transcription`, `m05_voice_audio_mixer` và `m06_nvenc_compositor`.
  - `Output` của `m02_asr_transcription` (`TranscriptResultDTO`) phải khớp 100% với `Input` của `m03_ai_content_brain`.
  - `Output` của `m03_ai_content_brain` (`CutPlanDTO` chứa `List[ClipSpecDTO]`) dùng chung đồng nhất cho cả 2 chế độ (*Tạo từ chủ đề* và *Cắt phim dài*), khớp 100% làm `Input` cho `m04_visual_producer` và `m05_voice_audio_mixer`.
  - `Output` của `m04` (`VisualAssetListDTO`) và `m05` (`MasterAudioAndSubDTO`) phải khớp 100% vào `RenderJobSpecDTO` của `m06_nvenc_compositor`.
- **Chuẩn đơn vị dữ liệu toàn hệ thống:**
  - Mọi mốc thời gian và thời lượng đều lưu bằng **số nguyên mili-giây (`int`, hậu tố `_ms`)**.
  - Mọi đường dẫn tệp sử dụng `pathlib.Path` mã hóa UTF-8.
  - Mọi tọa độ vùng khung hình (như vùng che Hardsub, vị trí Logo) chuẩn hóa theo tỷ lệ `0.0 -> 1.0`.
- Nếu cần thay đổi bất kỳ trường nào của `DTO`, phải cập nhật tại `m00_core_contracts` và tài liệu trước, đồng thời chạy lại toàn bộ Contract Tests.

## 4. Đảm Bảo Tính Kế Thừa, Mở Rộng (SOLID) & Code Sạch (Clean Code)
- **Nguyên lý Open/Closed & Strategy Pattern:** Các thành phần có nhiều nhà cung cấp hoặc biến thể thuật toán (`ITTSProvider`, `IVisualProvider`, `ILLMService`, `BaseLayoutStrategy`) bắt buộc kế thừa từ lớp cơ sở trừu tượng (`abc.ABC`). Khi bổ sung công nghệ mới (VD: thêm giọng đọc API mới hoặc bố cục dựng thứ 4), chỉ tạo lớp con kế thừa mới và đăng ký vào `Factory`, không sửa đổi logic hiện hữu.
- **Tiêu chuẩn Code Sạch:**
  - Đặt tên biến, hàm, lớp rõ nghĩa đúng thuật ngữ miền bài toán; không dùng hằng số ma thuật (*Magic Numbers* — mọi ngưỡng như `ducking_ratio=0.18`, `default_min_sec=65` phải đưa vào hằng số cấu hình).
  - Mỗi hàm chỉ làm một nhiệm vụ duy nhất (ngắn gọn, dễ đọc, có `Docstring` mô tả rõ `Args`, `Returns`, `Raises`).
  - Xử lý ngoại lệ tường minh (không dùng `except Exception: pass` nuốt lỗi ngầm); đảm bảo giải phóng tài nguyên tệp tạm và bộ nhớ `CUDA VRAM` (`GPUResourceManager`) trong khối `try...finally` hoặc `Context Manager`.
- **Kiểm thử độc lập từng Module:** Mỗi khi hoàn thành một module `m0X`, bắt buộc kèm theo bộ kiểm thử đơn vị và kiểm thử hợp đồng đầu vào/đầu ra (`backend/tests/test_m0X_*.py`) sử dụng dữ liệu `Mock DTO` để chứng minh module hoạt động độc lập trước khi ghép vào hệ thống tổng.

