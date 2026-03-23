import os
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
        # RAM
        mem = psutil.virtual_memory()
        info.ram_gb = mem.total / (1024 ** 3)
        # CPU
        info.cpu_cores = psutil.cpu_count(logical=True)
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info.cpu_name = line.split(":")[1].strip()
                        break
        except Exception:
            info.cpu_name = "Unknown CPU"
        # ONNX providers
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            if "CUDAExecutionProvider" in providers:
                info.has_cuda = True
                info.has_gpu = True
                info.onnx_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            else:
                info.onnx_providers = ["CPUExecutionProvider"]
        except Exception:
            info.onnx_providers = ["CPUExecutionProvider"]
        # GPU info via nvidia-smi
        if info.has_cuda:
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    parts = result.stdout.strip().split(",")
                    if len(parts) >= 2:
                        info.gpu_name = parts[0].strip()
                        info.gpu_vram_gb = int(parts[1].strip()) / 1024
                        info.has_gpu = True
            except Exception:
                pass
        # Recommended mode
        if info.has_cuda and info.gpu_vram_gb >= 4:
            info.recommended_mode = "quality"
        elif info.has_cuda or info.ram_gb >= 16:
            info.recommended_mode = "balanced"
        else:
            info.recommended_mode = "speed"
        return info

    def log_system_info(self, info: HardwareInfo):
        logger.info(f"RAM: {info.ram_gb:.1f} GB")
        logger.info(f"CPU: {info.cpu_name} ({info.cpu_cores} cores)")
        logger.info(f"CUDA: {info.has_cuda}")
        if info.has_gpu:
            logger.info(f"GPU: {info.gpu_name} ({info.gpu_vram_gb:.1f} GB VRAM)")
        logger.info(f"ONNX providers: {info.onnx_providers}")
        logger.info(f"Recommended mode: {info.recommended_mode}")
