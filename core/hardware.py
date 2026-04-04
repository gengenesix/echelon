import sys
import subprocess
import psutil
from dataclasses import dataclass, field
from typing import List
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HardwareInfo:
    ram_gb: float = 0.0
    cpu_cores: int = 0
    cpu_name: str = ""
    has_cuda: bool = False
    has_gpu: bool = False
    gpu_name: str = ""
    gpu_vram_gb: float = 0.0
    recommended_mode: str = "balanced"
    onnx_providers: List[str] = field(default_factory=list)


class HardwareDetector:
    def detect(self) -> HardwareInfo:
        info = HardwareInfo()

        mem = psutil.virtual_memory()
        info.ram_gb = mem.total / (1024 ** 3)
        info.cpu_cores = psutil.cpu_count(logical=True) or 1
        info.cpu_name = self._get_cpu_name()

        # ── Auto-detect best ONNX execution provider ──────────────────────────
        info.onnx_providers = self._detect_providers(info)

        # Determine if we have a usable GPU
        has_cuda     = any("CUDA"     in p for p in info.onnx_providers)
        has_directml = any("DirectML" in p for p in info.onnx_providers)
        has_coreml   = any("CoreML"   in p for p in info.onnx_providers)

        info.has_cuda = has_cuda
        info.has_gpu  = has_cuda or has_directml or has_coreml

        # GPU details from nvidia-smi (CUDA only)
        if has_cuda:
            info.gpu_name, info.gpu_vram_gb = self._nvidia_info()

        # Recommended performance mode
        if has_cuda and info.gpu_vram_gb >= 4:
            info.recommended_mode = "quality"
        elif info.has_gpu or info.ram_gb >= 16:
            info.recommended_mode = "balanced"
        else:
            info.recommended_mode = "speed"

        return info

    def _detect_providers(self, info: HardwareInfo) -> List[str]:
        """Return ordered list of ONNX providers — best first."""
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
        except Exception:
            return ["CPUExecutionProvider"]

        providers = []

        # 1. NVIDIA CUDA — fastest, requires CUDA toolkit
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
            logger.info("GPU: NVIDIA CUDA detected")

        # 2. DirectML — works on ANY GPU on Windows (AMD, Intel, Nvidia)
        elif "DmlExecutionProvider" in available:
            providers.append("DmlExecutionProvider")
            logger.info("GPU: DirectML detected (Windows GPU acceleration)")

        # 3. Apple CoreML — macOS Apple Silicon & Intel GPU
        elif "CoreMLExecutionProvider" in available:
            providers.append("CoreMLExecutionProvider")
            logger.info("GPU: Apple CoreML detected")

        # 4. ROCm — AMD GPU on Linux
        elif "ROCMExecutionProvider" in available:
            providers.append("ROCMExecutionProvider")
            logger.info("GPU: AMD ROCm detected")

        # Always include CPU as fallback
        providers.append("CPUExecutionProvider")

        if len(providers) == 1:
            logger.info("No GPU acceleration available — using CPU")

        return providers

    def _nvidia_info(self):
        """Get NVIDIA GPU name and VRAM via nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    return parts[0].strip(), int(parts[1].strip()) / 1024
        except Exception:
            pass
        return "NVIDIA GPU", 0.0

    def _get_cpu_name(self) -> str:
        try:
            if sys.platform == "win32":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                )
                name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                winreg.CloseKey(key)
                return name.strip()
            elif sys.platform == "darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            else:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
        except Exception:
            pass
        return "Unknown CPU"

    def log_system_info(self, info: HardwareInfo):
        logger.info(f"RAM: {info.ram_gb:.1f} GB")
        logger.info(f"CPU: {info.cpu_name} ({info.cpu_cores} cores)")
        logger.info(f"GPU acceleration: {info.has_gpu} | Providers: {info.onnx_providers}")
        if info.has_gpu and info.gpu_name:
            logger.info(f"GPU: {info.gpu_name} ({info.gpu_vram_gb:.1f} GB VRAM)")
        logger.info(f"Recommended mode: {info.recommended_mode}")
