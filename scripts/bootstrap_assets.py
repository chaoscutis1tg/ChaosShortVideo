"""Automated post-clone asset bootstrapper & environment health verifier for ChaosShortVideo.

Downloads large binary/model files excluded from Git (>100MB GitHub limit):
1. `assets/bin/ffmpeg.exe` & `ffprobe.exe` (FFmpeg 7.0.2 Essentials — unlocks RTX `h264_nvenc` without requiring 570+ drivers).
2. `assets/tts_models/vi_VN-vais1000-medium.onnx` & `.onnx.json` (Offline 0.1s Vietnamese VITS voice).
3. Optional `--preload-ai`: Pre-caches `SimianLuo/LCM_Dreamshaper_v7` for offline 9:16 AI scene generation.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = WORKSPACE_ROOT / "assets" / "bin"
TTS_MODELS_DIR = WORKSPACE_ROOT / "assets" / "tts_models"

FFMPEG_702_ZIP_URL = (
    "https://github.com/GyanD/codexffmpeg/releases/download/7.0.2/ffmpeg-7.0.2-essentials_build.zip"
)
PIPER_MODELS = (
    (
        "vi_VN-vais1000-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium",
        "Giọng Offline Bắc Ngọc Huyền (~60 MB)",
    ),
    (
        "vi_VN-25hours_single-low.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/25hours_single/low/vi_VN-25hours_single-low",
        "Giọng Offline Nữ Thuyết Minh Quỳnh Mai (~60 MB)",
    ),
    (
        "vi_VN-vivos-x_low.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vivos/x_low/vi_VN-vivos-x_low",
        "Bộ Giọng Offline Miền Nam VIVOS Đa Nhân Vật (~28 MB)",
    ),
)


def _download_with_progress(url: str, dest: Path, label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".part")
    print(f"  -> Đang tải {label}...")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ChaosShortVideo-Bootstrap/3.2"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp_path, "wb") as out_f:
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        last_pct = -10
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = int(downloaded * 100 / total)
                if pct >= last_pct + 10 or pct == 100:
                    mb_done = downloaded / (1024 * 1024)
                    mb_tot = total / (1024 * 1024)
                    print(f"     [{pct:3d}%] {mb_done:.1f} / {mb_tot:.1f} MB", flush=True)
                    last_pct = pct
    tmp_path.replace(dest)


def ensure_ffmpeg_binaries() -> bool:
    """Ensure `assets/bin/ffmpeg.exe` and `ffprobe.exe` exist on Windows (or system ffmpeg on Linux/macOS)."""
    if os.name != "nt":
        return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

    ffmpeg_exe = BIN_DIR / "ffmpeg.exe"
    ffprobe_exe = BIN_DIR / "ffprobe.exe"
    if ffmpeg_exe.exists() and ffprobe_exe.exists() and ffmpeg_exe.stat().st_size > 1_000_000:
        print("[OK] Đã có sẵn FFmpeg & FFprobe chuẩn NVENC tại assets/bin/")
        return True

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "ffmpeg_702.zip"
        try:
            _download_with_progress(
                FFMPEG_702_ZIP_URL,
                zip_path,
                "FFmpeg 7.0.2 Essentials (hỗ trợ tăng tốc phần cứng NVIDIA NVENC)",
            )
            print("  -> Đang giải nén ffmpeg.exe & ffprobe.exe vào assets/bin/...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    base = Path(member).name.lower()
                    if base in ("ffmpeg.exe", "ffprobe.exe"):
                        target = BIN_DIR / base
                        with zf.open(member) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            if ffmpeg_exe.exists() and ffprobe_exe.exists():
                print("[OK] Cài đặt thành công FFmpeg 7.0.2 vào assets/bin/")
                return True
        except Exception as exc:
            print(f"[CẢNH BÁO] Không thể tải tự động FFmpeg 7.0.2: {exc}")
            if shutil.which("ffmpeg") and shutil.which("ffprobe"):
                print("  -> Sẽ sử dụng FFmpeg có sẵn trong PATH hệ thống.")
                return True
    return False


def _patch_piper_json_phoneme_map(json_path: Path) -> None:
    if not json_path.exists():
        return
    try:
        import json

        cfg = json.loads(json_path.read_text(encoding="utf-8"))
        id_map = cfg.get("phoneme_id_map") or {}
        pmap = cfg.get("phoneme_map") or {}
        for ch in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "\u032a", "\u032f", "\u0329"):
            if ch not in id_map and ch not in pmap:
                pmap[ch] = []
        cfg["phoneme_map"] = pmap
        json_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def ensure_piper_vietnamese_voice() -> bool:
    """Ensure all 3 offline Vietnamese Piper VITS models (`vais1000`, `25hours_single`, `vivos`) exist."""
    all_ok = True
    for filename, base_url, label in PIPER_MODELS:
        onnx_path = TTS_MODELS_DIR / filename
        json_path = TTS_MODELS_DIR / f"{filename}.json"
        if onnx_path.exists() and onnx_path.stat().st_size > 1_000_000 and json_path.exists():
            _patch_piper_json_phoneme_map(json_path)
            print(f"[OK] Đã có sẵn {label} ({filename})")
            continue
        try:
            _download_with_progress(f"{base_url}.onnx.json", json_path, f"Cấu hình {filename}.json")
            _patch_piper_json_phoneme_map(json_path)
            _download_with_progress(f"{base_url}.onnx", onnx_path, label)
            print(f"[OK] Tải hoàn tất {label}!")
        except Exception as exc:
            print(f"[CẢNH BÁO] Chưa tải được {filename} (sẽ tự tải khi dùng): {exc}")
            all_ok = False
    return all_ok


def preload_gpu_scene_model() -> None:
    """Optionally pre-download `SimianLuo/LCM_Dreamshaper_v7` into HuggingFace cache."""
    try:
        import torch  # type: ignore
        from diffusers import DiffusionPipeline  # type: ignore

        print("  -> Đang tải trước mô hình vẽ cảnh AI 9:16 (SimianLuo/LCM_Dreamshaper_v7)...")
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        DiffusionPipeline.from_pretrained(
            "SimianLuo/LCM_Dreamshaper_v7",
            torch_dtype=dtype,
            safety_checker=None,
        )
        print("[OK] Đã lưu đệm mô hình vẽ cảnh AI SimianLuo/LCM_Dreamshaper_v7!")
    except Exception as exc:
        print(f"[CẢNH BÁO] Bỏ qua bước tải trước mô hình vẽ cảnh AI: {exc}")


def verify_environment() -> int:
    """Print a clear diagnostic table of all ChaosShortVideo components."""
    os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ.get("PATH", "")
    print("\n" + "=" * 68)
    print("  BÁO CÁO KIỂM TRA MÔI TRƯỜNG CHAOSSHORTVIDEO")
    print("=" * 68)

    # 1. Python
    print(f"  [OK] Python           : {sys.version.split()[0]} ({sys.executable})")

    # 2. PyTorch & CUDA GPU
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"  [OK] PyTorch + CUDA   : {torch.__version__} -> {gpu_name} ({vram_gb:.1f} GB VRAM)")
        else:
            print(f"  [OK] PyTorch (CPU)    : {torch.__version__} (Chế độ CPU ổn định)")
    except ImportError:
        print("  [!!] PyTorch          : Chưa cài đặt (cần chạy setup_env.bat)")

    # 3. FFmpeg & NVENC
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        nvenc_ok = False
        try:
            proc = subprocess.run(
                [
                    ffmpeg_bin,
                    "-hide_banner",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=640x360:d=0.2",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:v",
                    "h264_nvenc",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            nvenc_ok = proc.returncode == 0
        except Exception:
            nvenc_ok = False
        enc_label = "h264_nvenc (GPU Siêu tốc)" if nvenc_ok else "libx264 (CPU Đa nhân)"
        print(f"  [OK] FFmpeg & Encoder : {ffmpeg_bin} -> {enc_label}")
    else:
        print("  [!!] FFmpeg           : Không tìm thấy!")

    # 4. Offline Voice
    onnx_ok = (TTS_MODELS_DIR / "vi_VN-vais1000-medium.onnx").exists()
    print(
        f"  [{'OK' if onnx_ok else '!!'}] Giọng Offline    : "
        f"{'Sẵn sàng (Ngọc Huyền 0.1s)' if onnx_ok else 'Chưa tải'}"
    )

    # 5. Frontend Build
    dist_index = WORKSPACE_ROOT / "frontend" / "dist" / "index.html"
    print(
        f"  [{'OK' if dist_index.exists() else '!!'}] Giao diện Web    : "
        f"{'Đã đóng gói (frontend/dist)' if dist_index.exists() else 'Chưa build (cần npm run build)'}"
    )

    # 6. .env Configuration
    env_file = WORKSPACE_ROOT / ".env"
    has_gemini = False
    if env_file.exists():
        for ln in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ln.strip().startswith("GEMINI_API_KEY=") and len(ln.split("=", 1)[1].strip()) > 10:
                has_gemini = True
    print(
        f"  [{'OK' if env_file.exists() else '!!'}] Tệp cấu hình .env: "
        f"{'Đã điền GEMINI_API_KEY' if has_gemini else 'Đã tạo .env (nhập GEMINI_API_KEY trên giao diện Web)'}"
    )
    print("=" * 68 + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ChaosShortVideo Asset Bootstrapper")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Chỉ kiểm tra trạng thái môi trường, không tải tệp mới.",
    )
    parser.add_argument(
        "--preload-ai",
        action="store_true",
        help="Tải trước mô hình vẽ cảnh AI SimianLuo/LCM_Dreamshaper_v7 (~2.1 GB).",
    )
    args = parser.parse_args()

    if not args.verify_only:
        ensure_ffmpeg_binaries()
        ensure_piper_vietnamese_voice()
        if args.preload_ai:
            preload_gpu_scene_model()

    return verify_environment()


if __name__ == "__main__":
    raise SystemExit(main())

