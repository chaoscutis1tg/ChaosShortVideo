"""Singleton GPU/VRAM lock, Multi-GPU hardware scanner (NVIDIA/AMD/Intel) & encoder detector."""

from contextlib import contextmanager
import gc
import json
import os
from pathlib import Path
import site
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .dtos import GPUAdapterInfoDTO
from .exceptions import GPUResourceError


class GPUResourceManager:
    """Discovers all installed GPUs, tracks live VRAM/temperature, and serializes CUDA workloads."""

    _instance: Optional["GPUResourceManager"] = None
    _instance_lock = threading.Lock()
    _dll_handles: List[Any] = []
    _dlls_registered: bool = False

    def __new__(cls) -> "GPUResourceManager":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._cuda_lock = threading.RLock()
                cls._instance._active_owner = None
                cls._instance._nvenc_checked = False
                cls._instance._nvenc_available = False
                cls._instance._nvenc_note = ""
                cls._instance._preferred_device = os.getenv("STUDIO_GPU_DEVICE", "auto").strip()
                cls._instance._wmi_cache_ts = 0.0
                cls._instance._wmi_cached_cards: List[Dict[str, Any]] = []
                cls._instance._gpu_cache_ts = 0.0
                cls._instance._gpu_cached_adapters: List[GPUAdapterInfoDTO] = []
                cls.register_nvidia_cuda_dlls()
        return cls._instance

    @classmethod
    def register_nvidia_cuda_dlls(cls) -> List[str]:
        """Discover pip-installed NVIDIA CUDA 12 DLLs (`cublas64_12.dll`, `cudnn*.dll`)
        and register them in both Windows `PATH` and `os.add_dll_directory`.
        """
        if cls._dlls_registered:
            return []
        cls._dlls_registered = True

        candidate_roots: List[Path] = []
        for sp in [*site.getsitepackages(), site.getusersitepackages()]:
            if sp:
                p = Path(sp)
                if p.exists():
                    candidate_roots.append(p)
        exe_sp = Path(sys.executable).resolve().parent / "Lib" / "site-packages"
        if exe_sp.exists() and exe_sp not in candidate_roots:
            candidate_roots.append(exe_sp)

        rel_subdirs = (
            Path("nvidia") / "cublas" / "bin",
            Path("nvidia") / "cudnn" / "bin",
            Path("nvidia") / "cuda_runtime" / "bin",
            Path("torch") / "lib",
            Path("ctranslate2"),
        )

        added: List[str] = []
        current_path = os.environ.get("PATH", "")
        bundled_bin = Path(__file__).resolve().parents[3] / "assets" / "bin"
        if bundled_bin.exists() and str(bundled_bin) not in current_path:
            os.environ["PATH"] = str(bundled_bin) + os.pathsep + current_path
            current_path = os.environ["PATH"]
            added.append(str(bundled_bin))

        for root in candidate_roots:
            for sub in rel_subdirs:
                dll_dir = root / sub
                if dll_dir.exists() and dll_dir.is_dir():
                    dir_str = str(dll_dir)
                    if dir_str not in current_path:
                        os.environ["PATH"] = dir_str + os.pathsep + os.environ.get("PATH", "")
                        current_path = os.environ["PATH"]
                    if hasattr(os, "add_dll_directory"):
                        try:
                            cls._dll_handles.append(os.add_dll_directory(dir_str))
                        except OSError:
                            pass
                    added.append(dir_str)
        return added

    @property
    def active_owner(self) -> Optional[str]:
        """Name of the module/model currently holding the CUDA lock."""
        return self._active_owner

    @property
    def preferred_device(self) -> str:
        """Selected compute target: `'auto'`, `'cuda:0'`, `'cuda:1'`, or `'cpu'`."""
        return self._preferred_device

    def set_preferred_device(self, device_id: str) -> str:
        """Switch active compute target at runtime."""
        cleaned = (device_id or "auto").strip().lower()
        self._preferred_device = cleaned
        self._nvenc_checked = False
        self._gpu_cache_ts = 0.0
        os.environ["STUDIO_GPU_DEVICE"] = cleaned
        return self._preferred_device

    @property
    def encoder_diagnostic_note(self) -> str:
        """Human-readable note explaining hardware encoder status."""
        self.is_nvenc_available()
        return self._nvenc_note

    def list_gpu_adapters(self, max_age_sec: float = 4.5) -> List[GPUAdapterInfoDTO]:
        """Scan installed GPUs with short 4.5s telemetry cache so UI polling never spawns excess processes."""
        now_m = time.monotonic()
        if max_age_sec > 0 and self._gpu_cached_adapters and (now_m - self._gpu_cache_ts) < max_age_sec:
            return list(self._gpu_cached_adapters)
        adapters: List[GPUAdapterInfoDTO] = []
        seen_names_lower: set[str] = set()
        nvenc_ok = self.is_nvenc_available()

        # 1. Live NVIDIA GPU telemetry via nvidia-smi (supports 1, 2, or N NVIDIA GPUs!)
        try:
            proc = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu,driver_version",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                for raw_ln in proc.stdout.strip().splitlines():
                    parts = [p.strip() for p in raw_ln.split(",")]
                    if len(parts) < 7:
                        continue
                    idx = int(parts[0]) if parts[0].isdigit() else len(adapters)
                    name = parts[1]
                    v_tot = int(float(parts[2])) if parts[2].replace(".", "").isdigit() else 0
                    v_used = int(float(parts[3])) if parts[3].replace(".", "").isdigit() else 0
                    util = float(parts[4]) if parts[4].replace(".", "").isdigit() else 0.0
                    temp = int(float(parts[5])) if parts[5].replace(".", "").isdigit() else None
                    drv = parts[6]
                    seen_names_lower.add(name.lower())
                    adapters.append(
                        GPUAdapterInfoDTO(
                            device_id=f"cuda:{idx}",
                            index=idx,
                            name=name,
                            vendor="NVIDIA",
                            vram_total_mb=v_tot,
                            vram_used_mb=v_used,
                            utilization_pct=min(100.0, max(0.0, util)),
                            temperature_c=temp,
                            driver_version=drv,
                            supports_cuda=True,
                            supports_hw_encode=nvenc_ok,
                            hw_encoder_name="h264_nvenc" if nvenc_ok else "libx264",
                        )
                    )
        except (FileNotFoundError, subprocess.SubprocessError, ValueError):
            pass

        # 2. Discover additional AMD / Intel / secondary GPUs via cached Windows CIM query
        for extra in self._query_windows_video_controllers_cached():
            w_name = str(extra.get("Name") or "").strip()
            if not w_name or w_name.lower() in seen_names_lower:
                continue
            if "remote" in w_name.lower() or "basic display" in w_name.lower():
                continue
            seen_names_lower.add(w_name.lower())
            low = w_name.lower()
            vendor = (
                "AMD"
                if ("amd" in low or "radeon" in low)
                else "INTEL"
                if ("intel" in low or "arc" in low or "iris" in low or "uhd" in low)
                else "NVIDIA"
                if "nvidia" in low
                else "GPU"
            )
            ram_bytes = int(extra.get("AdapterRAM") or 0)
            vram_mb = max(0, ram_bytes // (1024 * 1024))
            idx_next = len(adapters)
            adapters.append(
                GPUAdapterInfoDTO(
                    device_id=f"gpu:{idx_next}",
                    index=idx_next,
                    name=w_name,
                    vendor=vendor,
                    vram_total_mb=vram_mb,
                    vram_used_mb=0,
                    utilization_pct=0.0,
                    temperature_c=None,
                    driver_version=str(extra.get("DriverVersion") or ""),
                    supports_cuda=False,
                    supports_hw_encode=False,
                    hw_encoder_name="libx264",
                )
            )

        self._gpu_cached_adapters = list(adapters)
        self._gpu_cache_ts = now_m
        return adapters

    def _query_windows_video_controllers_cached(self) -> List[Dict[str, Any]]:
        if os.name != "nt":
            return []
        now = time.monotonic()
        if now - self._wmi_cache_ts < 45.0 and self._wmi_cached_cards:
            return self._wmi_cached_cards
        self._wmi_cache_ts = now
        try:
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress",
                ],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            raw = (proc.stdout or "").strip()
            if proc.returncode == 0 and raw:
                parsed = json.loads(raw)
                self._wmi_cached_cards = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            pass
        return self._wmi_cached_cards

    def resolve_whisper_target(self) -> Tuple[str, int, str]:
        """Return `(device_type, device_index, human_label)` honoring user's GPU selection."""
        if self._preferred_device == "cpu":
            return ("cpu", 0, "CPU Chế độ Ổn định")

        adapters = self.list_gpu_adapters()
        cuda_cards = [a for a in adapters if a.supports_cuda]
        if not cuda_cards:
            return ("cpu", 0, "CPU int8")

        if self._preferred_device.startswith("cuda:"):
            try:
                wanted_idx = int(self._preferred_device.split(":", 1)[1])
                for card in cuda_cards:
                    if card.index == wanted_idx:
                        return ("cuda", card.index, f"{card.name} (GPU #{card.index})")
            except ValueError:
                pass

        # 'auto': Pick the NVIDIA GPU with the largest total VRAM
        best = max(cuda_cards, key=lambda c: c.vram_total_mb)
        return ("cuda", best.index, f"{best.name} (GPU #{best.index})")

    @contextmanager
    def acquire_vram(
        self,
        owner_name: str,
        timeout_sec: float = 600.0,
        cleanup_fn: Optional[Callable[[], None]] = None,
    ) -> Iterator[None]:
        """Acquire exclusive CUDA lock and force VRAM cache cleanup on exit."""
        self.register_nvidia_cuda_dlls()
        acquired = self._cuda_lock.acquire(timeout=timeout_sec)
        if not acquired:
            raise GPUResourceError(
                f"Không thể cấp phát khóa GPU cho '{owner_name}' sau {timeout_sec}s "
                f"(đang bận bởi '{self._active_owner}')."
            )
        self._active_owner = owner_name
        try:
            yield
        finally:
            try:
                if cleanup_fn is not None:
                    cleanup_fn()
            finally:
                self._active_owner = None
                self.flush_cuda_cache()
                self._cuda_lock.release()

    @staticmethod
    def flush_cuda_cache() -> None:
        """Run Python garbage collection and empty PyTorch CUDA cache if installed."""
        gc.collect()
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def is_cuda_available(self) -> bool:
        """Check whether an NVIDIA CUDA GPU is available and not overridden to CPU."""
        if self._preferred_device == "cpu":
            return False
        try:
            proc = subprocess.run(
                ["nvidia-smi", "-L"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            return proc.returncode == 0 and "GPU" in proc.stdout
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    def is_nvenc_available(self) -> bool:
        """Probe FFmpeg once to verify whether hardware encoder `h264_nvenc` works."""
        if self._preferred_device == "cpu":
            return False
        if self._nvenc_checked:
            return self._nvenc_available
        self._nvenc_checked = True
        try:
            proc = subprocess.run(
                [
                    "ffmpeg",
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
            self._nvenc_available = proc.returncode == 0
            if self._nvenc_available:
                self._nvenc_note = "Tăng tốc xuất phần cứng h264_nvenc đang hoạt động."
            else:
                err_low = (proc.stderr or "").lower()
                if "minimum required nvidia driver" in err_low or "nvenc api version" in err_low:
                    self._nvenc_note = (
                        "Đang xuất ổn định qua CPU đa nhân x264 (Cập nhật Driver NVIDIA mới hơn để mở khóa thêm NVENC cho FFmpeg 9)."
                    )
                else:
                    self._nvenc_note = "Đang xuất qua bộ mã hóa chuẩn x264 tốc độ cao."
        except (FileNotFoundError, subprocess.SubprocessError):
            self._nvenc_available = False
            self._nvenc_note = "Không tìm thấy NVENC, sử dụng x264."
        return self._nvenc_available
