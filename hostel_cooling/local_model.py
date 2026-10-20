"""Pinned, checksum-verified local inference runtime. No system-wide installation."""

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import urllib.request
import zipfile
import zlib

from .paths import ROOT

RUNTIME = ROOT / "runtime" / "llm"
MODEL_NAME = "Qwen3-4B-Q4_K_M"
MODEL_FILE = "Qwen3-4B-Q4_K_M.gguf"
MODEL_SHA256 = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
MODEL_REVISION = "bc640142c66e1fdd12af0bd68f40445458f3869b"
MODEL_URL = (
    f"https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/{MODEL_REVISION}/" + MODEL_FILE
)
VERSION = "b11756"
BINARIES = {
    "cpu": (
        "llama-b11756-bin-win-cpu-x64.zip",
        "d164195b8f3e92f8fd92bc3a5c0eeaef8707b2f1a979e36360ce8192ebf4fbb3",
    ),
    "vulkan": (
        "llama-b11756-bin-win-vulkan-x64.zip",
        "75ce69fdda503c3d6d3b3401f61369bd072194746ec65fbbc5fd7e749edd2914",
    ),
}
PORT = 8766


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, target, expected_sha256):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha256(target) == expected_sha256:
        print(f"Verified existing {target.name}", flush=True)
        return
    part = target.with_suffix(target.suffix + ".part")
    offset = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Hostel-Cooling-Lab",
            **({"Range": f"bytes={offset}-"} if offset else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        append = offset and response.status == 206
        if not append:
            offset = 0
        total = int(response.headers.get("Content-Length", "0")) + offset
        done = offset
        last = time.monotonic()
        with open(part, "ab" if append else "wb") as stream:
            while chunk := response.read(2 * 1024 * 1024):
                stream.write(chunk)
                done += len(chunk)
                if time.monotonic() - last > 8:
                    print(
                        f"{target.name}: {done / 1e6:.0f}/{total / 1e6:.0f} MB",
                        flush=True,
                    )
                    last = time.monotonic()
    if sha256(part) != expected_sha256:
        raise RuntimeError(
            f"Checksum mismatch for {target.name}; no unverified file will be executed."
        )
    part.replace(target)
    print(f"Downloaded and SHA256 verified {target.name}", flush=True)


def setup(acceleration="cpu"):
    if platform.system() != "Windows" or platform.machine().lower() not in (
        "amd64",
        "x86_64",
    ):
        raise RuntimeError(
            "The portable bootstrap supports Windows x64. Other platforms can run llama-server separately and set COOLING_LLM_URL."
        )
    filename, digest = BINARIES[acceleration]
    archive = RUNTIME / filename
    download(
        f"https://github.com/ggml-org/llama.cpp/releases/download/{VERSION}/{filename}",
        archive,
        digest,
    )
    binary_dir = RUNTIME / acceleration
    binary_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            resolved = (binary_dir / entry.filename).resolve()
            if not resolved.is_relative_to(binary_dir.resolve()):
                raise RuntimeError("Unsafe archive member")
        for entry in z.infolist():
            existing = binary_dir / entry.filename
            if existing.is_file() and existing.stat().st_size == entry.file_size:
                with existing.open("rb") as stream:
                    crc = 0
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        crc = zlib.crc32(chunk, crc)
                if crc == entry.CRC:
                    continue
            z.extract(entry, binary_dir)
    download(MODEL_URL, RUNTIME / MODEL_FILE, MODEL_SHA256)
    manifest = {
        "model": MODEL_NAME,
        "model_sha256": MODEL_SHA256,
        "runtime": VERSION,
        "acceleration": acceleration,
        "model_license": "Apache-2.0",
        "source": MODEL_URL,
    }
    (RUNTIME / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def health(base_url=None):
    base_url = base_url or os.getenv("COOLING_LLM_URL", f"http://127.0.0.1:{PORT}")
    try:
        with urllib.request.urlopen(
            base_url.rstrip("/") + "/health", timeout=2
        ) as response:
            return json.load(response).get("status") == "ok"
    except Exception:
        return False


def ensure_server():
    endpoint = os.getenv("COOLING_LLM_URL", f"http://127.0.0.1:{PORT}")
    if health(endpoint):
        with urllib.request.urlopen(
            endpoint.rstrip("/") + "/v1/models", timeout=5
        ) as response:
            models = json.load(response)
        if MODEL_NAME not in [item["id"] for item in models.get("data", [])]:
            raise RuntimeError(
                "Port 8766 hosts a different model. Stop that server or configure COOLING_LLM_URL explicitly."
            )
        return endpoint
    if os.getenv("COOLING_LLM_URL"):
        raise RuntimeError("The configured COOLING_LLM_URL server is unavailable.")
    manifest_path = RUNTIME / "manifest.json"
    if not manifest_path.exists() or not (RUNTIME / MODEL_FILE).exists():
        raise RuntimeError(
            "Local model is not installed. Run: python -m hostel_cooling setup-model"
        )
    manifest = json.loads(manifest_path.read_text())
    binaries = list((RUNTIME / manifest["acceleration"]).rglob("llama-server.exe"))
    if not binaries:
        raise RuntimeError("Local inference binary missing. Rerun setup-model.")
    if sha256(RUNTIME / MODEL_FILE) != MODEL_SHA256:
        raise RuntimeError("Model checksum changed. Rerun setup-model.")
    args = [
        str(binaries[0]),
        "-m",
        str(RUNTIME / MODEL_FILE),
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
        "-c",
        "4096",
        "-t",
        "6",
        "-np",
        "1",
        "--alias",
        MODEL_NAME,
        "--no-webui",
    ]
    if manifest["acceleration"] == "vulkan":
        args += ["-ngl", "99"]
    else:
        args += ["-ngl", "0"]
    with (
        open(RUNTIME / "server.stdout.log", "ab") as out,
        open(RUNTIME / "server.stderr.log", "ab") as err,
    ):
        proc = subprocess.Popen(
            args,
            cwd=str(binaries[0].parent),
            stdout=out,
            stderr=err,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    (RUNTIME / "server.pid").write_text(str(proc.pid))
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if health(endpoint):
            return endpoint
        if proc.poll() is not None:
            raise RuntimeError(
                "Local model server exited; see runtime/llm/server.stderr.log."
            )
        time.sleep(0.5)
    raise RuntimeError(
        "Local model did not become ready within 90 seconds; see runtime/llm logs."
    )
