# ChaosShortVideo — Hệ Thống Dựng Video Bán Hàng, Cắt Dịch Phim & Sáng Tạo Nội Dung AI

**ChaosShortVideo** là nền tảng biên tập video ngắn đa năng (`9:16`, `4:5`, `1:1`) chạy trực tiếp trên máy tính cá nhân và chia sẻ qua mạng Wi-Fi nội bộ (LAN). Hệ thống được tối ưu tăng tốc phần cứng trên card đồ họa **NVIDIA GeForce RTX (`CUDA` + `h264_nvenc` ~200 fps)** đồng thời tương thích hoàn toàn với máy chỉ có CPU, tuân thủ kiến trúc phân rã **08 Module độc lập (`M00 -> M07`)**.

---

## 1. Yêu Cầu Phần Mềm Trước Khi Clone

Trên máy tính mới (Windows 10/11 64-bit), bạn chỉ cần cài sẵn 3 công cụ nền tảng sau:

1. **Git**: [https://git-scm.com/download/win](https://git-scm.com/download/win)
2. **Python `3.10` – `3.12`** *(khuyên dùng Python `3.10` hoặc `3.11`)*: [https://www.python.org/downloads/](https://www.python.org/downloads/)
   > **Quan trọng:** Khi cài Python trên Windows, bắt buộc tích chọn ô **`Add Python to PATH`** ở màn hình đầu tiên.
3. **Node.js `18 LTS` hoặc `20 LTS`** *(để đóng gói giao diện React)*: [https://nodejs.org/](https://nodejs.org/)
4. *(Khuyên dùng nếu máy có card rời NVIDIA GTX/RTX)*: Cài **NVIDIA Game Ready / Studio Driver** mới nhất để mở khóa tăng tốc `CUDA` (nhận diện thoại `Faster-Whisper`, vẽ cảnh AI `LCM_Dreamshaper_v7`) và xuất video phần cứng `h264_nvenc`.

---

## 2. Hướng Dẫn Clone Từ GitHub & Cài Môi Trường (Tự Động 1 Chạm — Khuyên Dùng)

Mở **Command Prompt (`cmd`)** hoặc **PowerShell** tại ổ đĩa bạn muốn lưu dự án (ví dụ `D:\`) và chạy:

```powershell
git clone https://github.com/chaoscutis1tg/ChaosShortVideo.git
cd ChaosShortVideo
```

Sau khi clone xong, bạn chỉ cần làm **2 bước**:

### Bước 1: Chạy bộ cài đặt môi trường tự động (`setup_env.bat`)
Bấm đúp chuột vào tệp **[`setup_env.bat`](./setup_env.bat)** (hoặc gõ `.\setup_env.bat` trong Terminal). Kịch bản sẽ **tự động thực hiện từ A–Z**:
- Tạo tệp cấu hình `.env` từ `.env.example`.
- Tạo môi trường ảo Python cô lập tại `.venv/` (không làm ảnh hưởng Python hệ thống).
- Tự động kiểm tra máy có card đồ họa **NVIDIA** hay không để cài đúng bản **PyTorch CUDA 12.4 + cuBLAS/cuDNN** (hoặc bản CPU nếu máy không có card rời) cùng toàn bộ thư viện trong `backend/requirements.txt`.
- Chạy `npm install` và `npm run build` để đóng gói giao diện Web vào `frontend/dist/`.
- Tự động tải bộ công cụ **`FFmpeg 7.0.2` chuẩn NVENC** (`assets/bin/ffmpeg.exe`, `ffprobe.exe`) và mô hình giọng đọc Offline **Ngọc Huyền** (`assets/tts_models/vi_VN-vais1000-medium.onnx`) vốn vượt quá giới hạn 100MB của GitHub.
- In bảng **Báo cáo Kiểm tra Môi trường** xác nhận trạng thái GPU, NVENC, Giọng đọc và Giao diện.

### Bước 2: Khởi động hệ thống (`start_studio.bat`)
1. Bấm đúp vào **[`start_studio.bat`](./start_studio.bat)**.
2. Trình duyệt sẽ tự động mở tại địa chỉ: **`http://127.0.0.1:8000`** *(Nếu bạn bấm thẳng `start_studio.bat` ngay sau khi clone mà quên chạy `setup_env.bat`, hệ thống cũng sẽ tự động gọi `setup_env.bat` giúp bạn)*.
3. Trên thanh tiêu đề góc phải giao diện Web, bấm **`API & Sao lưu`** -> dán khóa **`GEMINI_API_KEY`** (lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/apikey)) -> bấm **Lưu cấu hình**.

---

## 3. Cài Đặt Thủ Công Bằng Dòng Lệnh (Dành Cho Lập Trình Viên)

Nếu bạn muốn tự kiểm soát từng lệnh trong **PowerShell** thay vì dùng tệp `.bat`:

```powershell
# 1. Clone dự án & tạo tệp .env
git clone https://github.com/chaoscutis1tg/ChaosShortVideo.git
cd ChaosShortVideo
Copy-Item .env.example .env

# 2. Tạo và kích hoạt môi trường ảo Python (.venv)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel setuptools

# 3A. Nếu máy CÓ card đồ họa NVIDIA (RTX / GTX):
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12

# 3B. (Hoặc) Nếu máy KHÔNG có card rời NVIDIA (chỉ chạy CPU):
# pip install torch

# 4. Cài toàn bộ thư viện Backend
pip install -r backend/requirements.txt

# 5. Cài đặt & build giao diện Frontend React
cd frontend
npm install
npm run build
cd ..

# 6. Tải tự động FFmpeg 7.0.2 NVENC + Giọng đọc Offline tiếng Việt & kiểm tra hệ thống
python scripts/bootstrap_assets.py
# (Tùy chọn) Tải sẵn luôn mô hình vẽ ảnh AI 9:16 (~2.1 GB) vào bộ nhớ đệm:
# python scripts/bootstrap_assets.py --preload-ai

# 7. Chạy máy chủ ChaosShortVideo tại cổng 8000
$env:PATH = "$PWD\assets\bin;$env:PATH"
$env:PYTHONPATH = "$PWD\backend"
python -m uvicorn app.m07_studio_api.main:app --host 0.0.0.0 --port 8000
```

*Để phát triển giao diện Frontend chế độ Hot-Reload (cổng `5173` kết nối song song Backend cổng `8000`): mở thêm 1 cửa sổ Terminal tại thư mục `frontend/` và chạy `npm run dev`.*

---

## 4. Chuyển Dữ Liệu Cửa Hàng & Giọng Nhái Sang Máy Mới

Khi chuyển sang máy tính mới sau khi `git clone`:
- Ở máy cũ: Bấm nút **`API & Sao lưu`** góc phải trên -> chọn **`Xuất gói Sao lưu (.ZIP)`** để tải tệp `ChaosShortVideo_StoreBackup.zip` (chứa sẵn Bộ nhận diện thương hiệu, Logo, Mẫu sản phẩm và Hồ sơ giọng đọc).
- Ở máy mới: Mở **`API & Sao lưu`** -> chọn **`Khôi phục từ tệp .ZIP`** để nạp lại toàn bộ cấu hình trong 1 giây.

---

## 5. Cấu Trúc 08 Module Độc Lập (`M00 -> M07`)

| Module | Đường dẫn Backend | Đường dẫn Frontend | Trách nhiệm chính |
| :--- | :--- | :--- | :--- |
| **`M00`** | `backend/app/m00_core_contracts/` | `frontend/src/modules/m00_core_contracts/` | Hợp đồng `Pydantic DTOs`, `ABC Interfaces`, CSDL `SQLite` & khóa `GPUResourceManager`. |
| **`M01`** | `backend/app/m01_media_ingest/` | `frontend/src/modules/m01_m04_movie_studio/` | Nhập tệp nội bộ, cắt đoạn nhanh (`Media Trimmer`), tải link `yt-dlp` / `m3u8`, tách WAV `16kHz`. |
| **`M02`** | `backend/app/m02_asr_transcription/` | — | Nhận diện thoại bằng GPU (`Faster-Whisper` + tự giải phóng VRAM) & đọc `.srt` rời. |
| **`M03`** | `backend/app/m03_ai_content_brain/` | `frontend/src/modules/m03_topic_studio/` | Phân tích ý tưởng ngắn bằng AI (`Brief Expander`), viết kịch bản chủ đề & bán hàng, dịch phim & sinh SEO. |
| **`M04`** | `backend/app/m04_visual_producer/` | `frontend/src/modules/m08_product_studio/` | Vẽ cảnh AI `9:16` trên GPU (`LCM_Dreamshaper_v7`), khung sản phẩm tách nền & Stock Video. |
| **`M05`** | `backend/app/m05_voice_audio_mixer/` | `frontend/src/modules/m05_voice_lab/` | Kho 30 giọng đọc theo nền tảng, tách/nhái giọng trực tiếp từ YouTube (`F5-TTS`), `Audio Ducking` & `.ass`. |
| **`M06`** | `backend/app/m06_nvenc_compositor/` | `frontend/src/modules/m06_canvas_916/` | Khung `9:16 / 4:5 / 1:1` thông minh theo ngữ cảnh, `Cover Studio`, che chữ gốc & xuất `h264_nvenc`. |
| **`M07`** | `backend/app/m07_studio_api/` | `frontend/src/modules/m07_review_and_seo/` | Khung Studio `100vh` Sticky, quản lý **Dự Án Cha → Dự Án Con** 2 cột, lưu nháp tự động, QR LAN & xuất `.ZIP`. |

---

## 6. Kiểm Thử Hệ Thống & Hợp Đồng Module (`Pytest`)

```powershell
# Kiểm tra nhanh toàn bộ môi trường & phần cứng
python scripts/bootstrap_assets.py --verify-only

# Chạy bộ kiểm thử đơn vị và kiểm thử cấm phụ thuộc chéo (M00 -> M07)
$env:PYTHONPATH="$PWD\backend"
python -m pytest backend/tests -v
```
