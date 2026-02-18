"""Tests for marksync.hardware_detect."""

from __future__ import annotations

from unittest import mock

from marksync.hardware_detect import (
    GPUInfo,
    SystemInfo,
    detect,
    detect_amd_gpu,
    detect_gpu,
    detect_nvidia_gpu,
    detect_ram,
    is_ollama_installed,
    is_ollama_running,
    list_ollama_models,
    suggest_model,
)


# ── suggest_model ──────────────────────────────────────────────────────────────

def test_suggest_model_high_vram():
    model, api = suggest_model(16, 64)
    assert model == "qwen2.5-coder:14b"
    assert api is False


def test_suggest_model_medium_vram():
    model, api = suggest_model(6, 32)
    assert model == "qwen2.5-coder:7b"
    assert api is False


def test_suggest_model_min_vram_boundary():
    model, api = suggest_model(4, 8)
    assert model == "qwen2.5-coder:7b"
    assert api is False


def test_suggest_model_cpu_enough_ram():
    model, api = suggest_model(0, 32)
    assert model == "qwen2.5-coder:7b"
    assert api is False


def test_suggest_model_cpu_boundary_ram():
    model, api = suggest_model(0, 16)
    assert model == "qwen2.5-coder:7b"
    assert api is False


def test_suggest_model_low_resources():
    model, api = suggest_model(0, 8)
    assert model == ""
    assert api is True


def test_suggest_model_no_resources():
    model, api = suggest_model(0, 0)
    assert model == ""
    assert api is True


# ── detect_nvidia_gpu ──────────────────────────────────────────────────────────

def test_detect_nvidia_gpu_not_installed():
    with mock.patch("shutil.which", return_value=None):
        gpu = detect_nvidia_gpu()
    assert gpu.available is False
    assert gpu.vram_gb == 0
    assert gpu.name == ""


def test_detect_nvidia_gpu_success():
    mock_result = mock.Mock()
    mock_result.returncode = 0
    mock_result.stdout = "NVIDIA GeForce RTX 3080, 10240\n"
    with mock.patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        with mock.patch("subprocess.run", return_value=mock_result):
            gpu = detect_nvidia_gpu()
    assert gpu.available is True
    assert gpu.name == "NVIDIA GeForce RTX 3080"
    assert gpu.vram_gb == 10


def test_detect_nvidia_gpu_nonzero_return():
    mock_result = mock.Mock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    with mock.patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        with mock.patch("subprocess.run", return_value=mock_result):
            gpu = detect_nvidia_gpu()
    assert gpu.available is False


def test_detect_nvidia_gpu_exception():
    with mock.patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        with mock.patch("subprocess.run", side_effect=Exception("timeout")):
            gpu = detect_nvidia_gpu()
    assert gpu.available is False


# ── detect_amd_gpu ─────────────────────────────────────────────────────────────

def test_detect_amd_gpu_not_installed():
    with mock.patch("shutil.which", return_value=None):
        gpu = detect_amd_gpu()
    assert gpu.available is False


def test_detect_amd_gpu_success():
    mock_result = mock.Mock()
    mock_result.returncode = 0
    mock_result.stdout = "card0,VRAM Total,8589934592\n"
    with mock.patch("shutil.which", return_value="/usr/bin/rocm-smi"):
        with mock.patch("subprocess.run", return_value=mock_result):
            gpu = detect_amd_gpu()
    assert gpu.available is True
    assert gpu.vram_gb == 8


# ── detect_gpu ─────────────────────────────────────────────────────────────────

def test_detect_gpu_prefers_nvidia():
    nvidia = GPUInfo(name="NVIDIA RTX 3080", vram_gb=10, available=True)
    amd = GPUInfo(name="AMD GPU", vram_gb=8, available=True)
    with mock.patch("marksync.hardware_detect.detect_nvidia_gpu", return_value=nvidia):
        with mock.patch("marksync.hardware_detect.detect_amd_gpu", return_value=amd):
            result = detect_gpu()
    assert result.name == "NVIDIA RTX 3080"


def test_detect_gpu_falls_back_to_amd():
    no_gpu = GPUInfo()
    amd = GPUInfo(name="AMD GPU", vram_gb=8, available=True)
    with mock.patch("marksync.hardware_detect.detect_nvidia_gpu", return_value=no_gpu):
        with mock.patch("marksync.hardware_detect.detect_amd_gpu", return_value=amd):
            result = detect_gpu()
    assert result.name == "AMD GPU"


def test_detect_gpu_none_available():
    no_gpu = GPUInfo()
    with mock.patch("marksync.hardware_detect.detect_nvidia_gpu", return_value=no_gpu):
        with mock.patch("marksync.hardware_detect.detect_amd_gpu", return_value=no_gpu):
            result = detect_gpu()
    assert result.available is False


# ── detect_ram ─────────────────────────────────────────────────────────────────

def test_detect_ram_from_free():
    mock_result = mock.Mock()
    mock_result.stdout = (
        "              total        used        free\n"
        "Mem:    17179869184   5000000000  9000000000\n"
    )
    with mock.patch("subprocess.run", return_value=mock_result):
        ram = detect_ram()
    assert ram == 16  # 17179869184 // 1024**3


def test_detect_ram_fallback_proc():
    with mock.patch("subprocess.run", side_effect=Exception("no free")):
        proc_content = "MemTotal:       16777216 kB\nMemFree:        8388608 kB\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=proc_content)):
            ram = detect_ram()
    assert ram == 16  # 16777216 // (1024*1024)


def test_detect_ram_all_fail():
    with mock.patch("subprocess.run", side_effect=Exception("no free")):
        with mock.patch("builtins.open", side_effect=Exception("no proc")):
            ram = detect_ram()
    assert ram == 0


# ── is_ollama_installed ────────────────────────────────────────────────────────

def test_is_ollama_installed_true():
    with mock.patch("shutil.which", return_value="/usr/bin/ollama"):
        assert is_ollama_installed() is True


def test_is_ollama_installed_false():
    with mock.patch("shutil.which", return_value=None):
        assert is_ollama_installed() is False


# ── is_ollama_running ──────────────────────────────────────────────────────────

def test_is_ollama_running_true():
    mock_resp = mock.MagicMock()
    mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
    mock_resp.__exit__ = mock.Mock(return_value=False)
    mock_resp.status = 200
    with mock.patch("urllib.request.urlopen", return_value=mock_resp):
        assert is_ollama_running() is True


def test_is_ollama_running_false():
    with mock.patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
        assert is_ollama_running() is False


def test_is_ollama_running_custom_url():
    with mock.patch("urllib.request.urlopen", side_effect=Exception("error")):
        assert is_ollama_running("http://remote:11434") is False


# ── list_ollama_models ─────────────────────────────────────────────────────────

def test_list_ollama_models_success():
    mock_resp = mock.MagicMock()
    mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
    mock_resp.__exit__ = mock.Mock(return_value=False)
    mock_resp.read.return_value = b'{"models": [{"name": "qwen2.5-coder:7b"}, {"name": "llama3.2:3b"}]}'
    with mock.patch("urllib.request.urlopen", return_value=mock_resp):
        models = list_ollama_models()
    assert "qwen2.5-coder:7b" in models
    assert "llama3.2:3b" in models
    assert len(models) == 2


def test_list_ollama_models_empty():
    mock_resp = mock.MagicMock()
    mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
    mock_resp.__exit__ = mock.Mock(return_value=False)
    mock_resp.read.return_value = b'{"models": []}'
    with mock.patch("urllib.request.urlopen", return_value=mock_resp):
        models = list_ollama_models()
    assert models == []


def test_list_ollama_models_failure():
    with mock.patch("urllib.request.urlopen", side_effect=Exception("error")):
        models = list_ollama_models()
    assert models == []


# ── detect (integration) ───────────────────────────────────────────────────────

def test_detect_full_gpu():
    gpu = GPUInfo(name="RTX 3080", vram_gb=10, available=True)
    with mock.patch("marksync.hardware_detect.detect_gpu", return_value=gpu), \
         mock.patch("marksync.hardware_detect.detect_ram", return_value=32), \
         mock.patch("marksync.hardware_detect.is_ollama_installed", return_value=True), \
         mock.patch("marksync.hardware_detect.is_ollama_running", return_value=True), \
         mock.patch("marksync.hardware_detect.list_ollama_models", return_value=["qwen2.5-coder:14b"]):
        info = detect()

    assert info.gpu.name == "RTX 3080"
    assert info.ram_gb == 32
    assert info.ollama_installed is True
    assert info.ollama_running is True
    assert info.ollama_models == ["qwen2.5-coder:14b"]
    assert info.suggested_model == "qwen2.5-coder:14b"
    assert info.recommend_api is False


def test_detect_recommend_api():
    no_gpu = GPUInfo()
    with mock.patch("marksync.hardware_detect.detect_gpu", return_value=no_gpu), \
         mock.patch("marksync.hardware_detect.detect_ram", return_value=8), \
         mock.patch("marksync.hardware_detect.is_ollama_installed", return_value=False), \
         mock.patch("marksync.hardware_detect.is_ollama_running", return_value=False), \
         mock.patch("marksync.hardware_detect.list_ollama_models", return_value=[]):
        info = detect()

    assert info.recommend_api is True
    assert info.suggested_model == ""
    assert info.ollama_running is False


def test_detect_skips_model_list_when_not_running():
    no_gpu = GPUInfo()
    list_models_mock = mock.Mock(return_value=["some-model"])
    with mock.patch("marksync.hardware_detect.detect_gpu", return_value=no_gpu), \
         mock.patch("marksync.hardware_detect.detect_ram", return_value=32), \
         mock.patch("marksync.hardware_detect.is_ollama_installed", return_value=True), \
         mock.patch("marksync.hardware_detect.is_ollama_running", return_value=False), \
         mock.patch("marksync.hardware_detect.list_ollama_models", list_models_mock):
        info = detect()

    list_models_mock.assert_not_called()
    assert info.ollama_models == []
