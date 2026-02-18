"""
marksync.hardware_detect — Auto-detect system resources and suggest LLM configuration.

Usage:
    from marksync.hardware_detect import detect
    info = detect()
    print(info.suggested_model)   # "qwen2.5-coder:14b"
    print(info.recommend_api)     # False
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field

log = logging.getLogger("marksync.hardware_detect")


@dataclass
class GPUInfo:
    name: str = ""
    vram_gb: int = 0
    available: bool = False


@dataclass
class SystemInfo:
    gpu: GPUInfo = field(default_factory=GPUInfo)
    ram_gb: int = 0
    ollama_installed: bool = False
    ollama_running: bool = False
    ollama_models: list[str] = field(default_factory=list)
    suggested_model: str = ""
    recommend_api: bool = False


def detect_nvidia_gpu() -> GPUInfo:
    """Query nvidia-smi for GPU name and VRAM."""
    if not shutil.which("nvidia-smi"):
        return GPUInfo()
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return GPUInfo()
        line = result.stdout.strip().splitlines()[0]
        name, vram_mb_str = line.split(",", 1)
        vram_gb = int(float(vram_mb_str.strip())) // 1024
        return GPUInfo(name=name.strip(), vram_gb=vram_gb, available=True)
    except Exception as exc:
        log.debug("nvidia-smi detection failed: %s", exc)
        return GPUInfo()


def detect_amd_gpu() -> GPUInfo:
    """Query rocm-smi for AMD GPU VRAM."""
    if not shutil.which("rocm-smi"):
        return GPUInfo()
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--csv"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return GPUInfo()
        for line in result.stdout.splitlines():
            if "Total" in line or "total" in line:
                parts = line.split(",")
                if len(parts) >= 2:
                    try:
                        vram_bytes = int(parts[-1].strip())
                        vram_gb = vram_bytes // (1024 ** 3)
                        return GPUInfo(name="AMD GPU", vram_gb=vram_gb, available=True)
                    except (ValueError, IndexError):
                        pass
        return GPUInfo(name="AMD GPU", vram_gb=0, available=True)
    except Exception as exc:
        log.debug("rocm-smi detection failed: %s", exc)
        return GPUInfo()


def detect_gpu() -> GPUInfo:
    """Detect best available GPU (NVIDIA preferred, then AMD)."""
    gpu = detect_nvidia_gpu()
    if gpu.available:
        return gpu
    return detect_amd_gpu()


def detect_ram() -> int:
    """Return total system RAM in GB."""
    try:
        result = subprocess.run(["free", "-b"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if line.startswith("Mem:"):
                return int(line.split()[1]) // (1024 ** 3)
    except Exception:
        pass
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // (1024 * 1024)
    except Exception:
        pass
    return 0


def is_ollama_installed() -> bool:
    """Check if the ollama binary is in PATH."""
    return shutil.which("ollama") is not None


def is_ollama_running(url: str = "http://localhost:11434") -> bool:
    """Check if Ollama HTTP API is reachable."""
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def list_ollama_models(url: str = "http://localhost:11434") -> list[str]:
    """Return list of model names available in Ollama."""
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def suggest_model(gpu_vram_gb: int, ram_gb: int) -> tuple[str, bool]:
    """Return (suggested_model, recommend_api_instead) based on available resources.

    Rules:
        GPU >= 8 GB  → qwen2.5-coder:14b
        GPU >= 4 GB  → qwen2.5-coder:7b
        No GPU, RAM >= 16 GB → qwen2.5-coder:7b (CPU)
        No GPU, RAM < 16 GB  → "" + recommend_api=True
    """
    if gpu_vram_gb >= 8:
        return "qwen2.5-coder:14b", False
    if gpu_vram_gb >= 4:
        return "qwen2.5-coder:7b", False
    if ram_gb >= 16:
        return "qwen2.5-coder:7b", False
    return "", True


def detect(ollama_url: str = "http://localhost:11434") -> SystemInfo:
    """Run full system detection and return a SystemInfo summary."""
    gpu = detect_gpu()
    ram_gb = detect_ram()
    installed = is_ollama_installed()
    running = is_ollama_running(ollama_url) if installed else False
    models = list_ollama_models(ollama_url) if running else []
    suggested, recommend_api = suggest_model(gpu.vram_gb, ram_gb)
    return SystemInfo(
        gpu=gpu,
        ram_gb=ram_gb,
        ollama_installed=installed,
        ollama_running=running,
        ollama_models=models,
        suggested_model=suggested,
        recommend_api=recommend_api,
    )
