"""Local stdio MCP control plane for the Agent Speak HTTP gateway.

MCP carries small commands and JSON results. Audio remains a bounded WAV transfer to
the existing HTTP API; real-time media and events belong on HTTP/WebSocket.
"""

from __future__ import annotations

import io
import ipaddress
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol


class ControlError(RuntimeError):
    """A safe, user-actionable control-plane failure."""


class HTTPClient(Protocol):
    def json(self, method: str, path: str, body: object | None = None) -> dict[str, Any]: ...
    def wav(self, method: str, path: str, payload: bytes) -> dict[str, Any]: ...
    def bytes(self, path: str) -> bytes: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


class GatewayHTTPClient:
    """Small bounded HTTP client dedicated to the local Agent Speak gateway."""

    def __init__(self, base_url: str, *, timeout: float = 30.0, max_download_bytes: int = 8 * 1024 * 1024) -> None:
        normalized = base_url.rstrip("/")
        parsed = urllib.parse.urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
            raise ValueError("AGENT_SPEAK_URL must be an http(s) origin URL")
        if parsed.username or parsed.password or parsed.path or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("AGENT_SPEAK_URL must contain only scheme, host, and optional port")
        if parsed.scheme == "http":
            try:
                loopback = ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                loopback = parsed.hostname.lower() == "localhost"
            if not loopback:
                raise ValueError("Plain HTTP is allowed only for a loopback Agent Speak gateway; use HTTPS remotely")
        self.base_url = normalized
        self.timeout = timeout
        self.max_download_bytes = max_download_bytes
        self._opener = urllib.request.build_opener(_NoRedirect())

    def _request(self, method: str, path: str, *, data: bytes | None = None, content_type: str | None = None) -> bytes:
        if not path.startswith("/"):
            raise ControlError("Gateway path must be absolute")
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                length = response.headers.get("Content-Length")
                if length:
                    try:
                        declared_length = int(length)
                    except ValueError as exc:
                        raise ControlError("Gateway returned an invalid Content-Length") from exc
                    if declared_length < 0 or declared_length > self.max_download_bytes:
                        raise ControlError("Gateway response exceeds the configured limit")
                payload = response.read(self.max_download_bytes + 1)
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise ControlError(f"Gateway HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ControlError(f"Cannot reach Agent Speak gateway: {exc}") from exc
        if len(payload) > self.max_download_bytes:
            raise ControlError("Gateway response exceeds the configured limit")
        return payload

    def json(self, method: str, path: str, body: object | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        payload = self._request(method, path, data=data, content_type="application/json" if data is not None else None)
        try:
            result = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControlError("Gateway returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ControlError("Gateway returned an unexpected JSON value")
        return result

    def wav(self, method: str, path: str, payload: bytes) -> dict[str, Any]:
        response = self._request(method, path, data=payload, content_type="audio/wav")
        try:
            result = json.loads(response)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControlError("Gateway returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ControlError("Gateway returned an unexpected JSON value")
        return result

    def bytes(self, path: str) -> bytes:
        return self._request("GET", path)


Runner = Callable[..., subprocess.CompletedProcess[str]]
_ALSA_DEVICE = re.compile(r"^(?:default|sysdefault|front|surround\d+|hw|plughw|plug):?[A-Za-z0-9_.-]*(?:,[0-9]+)?$")


def _default_runner(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)


class AgentSpeakControl:
    def __init__(self, *, http: HTTPClient, runner: Runner = _default_runner, temp_dir: Path | None = None) -> None:
        self.http = http
        self.runner = runner
        self.temp_dir = temp_dir

    def status(self) -> dict[str, Any]:
        try:
            health = self.http.json("GET", "/api/v1/health")
            capabilities = self.http.json("GET", "/api/v1/capabilities")
            return {"reachable": True, "health": health, "capabilities": capabilities}
        except ControlError as exc:
            return {"reachable": False, "error": str(exc)}

    def capabilities(self) -> dict[str, Any]:
        return self.http.json("GET", "/api/v1/capabilities")

    def _device_query(self, command: str) -> dict[str, Any]:
        try:
            result = self.runner([command, "-l"], timeout=5.0)
        except FileNotFoundError:
            return {"available": False, "devices": "", "error": f"{command} is not installed"}
        except subprocess.TimeoutExpired:
            return {"available": False, "devices": "", "error": f"{command} timed out after 5 seconds"}
        output = (result.stdout or "").strip()
        if result.returncode != 0:
            error = (result.stderr or output or f"{command} exited {result.returncode}").strip()
            return {"available": False, "devices": output, "error": error}
        has_device = bool(re.search(r"(?im)^card\s+\d+:", output))
        return {
            "available": has_device,
            "devices": output,
            "error": None if has_device else "No audio device reported",
        }

    def list_audio_devices(self) -> dict[str, Any]:
        return {"capture": self._device_query("arecord"), "playback": self._device_query("aplay")}

    @staticmethod
    def _validate_device(device: str) -> str:
        if not _ALSA_DEVICE.fullmatch(device):
            raise ControlError("Invalid ALSA device; use values such as default, hw:1,0, or plughw:1,0")
        return device

    @staticmethod
    def _require_confirmation(user_confirmed: bool, action: str) -> None:
        if not user_confirmed:
            raise ControlError(f"{action} requires explicit user confirmation for this tool call")

    @staticmethod
    def _validate_pcm_wav(payload: bytes) -> dict[str, int]:
        try:
            with wave.open(io.BytesIO(payload), "rb") as source:
                details = {
                    "channels": source.getnchannels(),
                    "sample_width": source.getsampwidth(),
                    "rate_hz": source.getframerate(),
                    "frames": source.getnframes(),
                }
        except (wave.Error, EOFError) as exc:
            raise ControlError("Audio device did not produce a valid PCM WAV") from exc
        if details["channels"] not in {1, 2} or details["sample_width"] != 2:
            raise ControlError("Audio device did not produce a valid 16-bit mono/stereo PCM WAV")
        if not 8_000 <= details["rate_hz"] <= 48_000 or details["frames"] <= 0:
            raise ControlError("Audio device produced an empty or unsupported PCM WAV")
        return details

    def _record(self, *, duration_seconds: int, device: str) -> tuple[bytes, dict[str, Any]]:
        if not 1 <= duration_seconds <= 30:
            raise ControlError("duration_seconds must be between 1 and 30")
        device = self._validate_device(device)
        descriptor, name = tempfile.mkstemp(suffix=".wav", dir=self.temp_dir)
        os.close(descriptor)
        path = Path(name)
        command = [
            "arecord", "-q", "-D", device, "-d", str(duration_seconds),
            "-f", "S16_LE", "-r", "16000", "-c", "1", str(path),
        ]
        try:
            try:
                result = self.runner(command, timeout=float(duration_seconds + 3))
            except FileNotFoundError as exc:
                raise ControlError("arecord is not installed; install ALSA utilities") from exc
            except subprocess.TimeoutExpired as exc:
                raise ControlError("Microphone capture timed out") from exc
            if result.returncode != 0:
                raise ControlError(f"Microphone capture failed: {(result.stderr or 'unknown arecord error').strip()}")
            payload = path.read_bytes()
            if not payload:
                raise ControlError("Microphone capture produced no audio")
            wav_details = self._validate_pcm_wav(payload)
            details: dict[str, Any] = {
                "bytes": len(payload),
                "duration_requested": duration_seconds,
                "device": device,
                **wav_details,
            }
            return payload, details
        finally:
            path.unlink(missing_ok=True)

    def microphone_smoke(
        self, duration_seconds: int = 2, device: str = "default", user_confirmed: bool = False
    ) -> dict[str, Any]:
        self._require_confirmation(user_confirmed, "Microphone capture")
        _, details = self._record(duration_seconds=duration_seconds, device=device)
        return {"captured": True, **details}

    def listen_once(
        self, duration_seconds: int = 3, device: str = "default", user_confirmed: bool = False
    ) -> dict[str, Any]:
        self._require_confirmation(user_confirmed, "Microphone capture")
        payload, capture = self._record(duration_seconds=duration_seconds, device=device)
        result = self.http.wav("POST", "/api/v1/audio/asr", payload)
        return {**result, "capture": capture}

    def speak(
        self, text: str, playback: bool = False, device: str = "default", user_confirmed: bool = False
    ) -> dict[str, Any]:
        text = text.strip()
        if not text or len(text) > 4000:
            raise ControlError("text must contain 1 to 4000 characters")
        if playback:
            self._require_confirmation(user_confirmed, "Physical speaker playback")
        synthesized = self.http.json("POST", "/api/v1/tts/synthesize", {"text": text})
        audio_url = synthesized.get("audio_url")
        if not isinstance(audio_url, str) or not audio_url.startswith("/api/v1/artifacts/"):
            raise ControlError("Gateway returned an unsafe or invalid audio_url")
        result: dict[str, Any] = {"synthesized": True, "audio_url": audio_url, "played": False}
        if not playback:
            return result
        device = self._validate_device(device)
        playback_devices = self._device_query("aplay")
        if not playback_devices["available"]:
            result["playback_error"] = f"No playback device available: {playback_devices.get('error')}"
            return result
        audio = self.http.bytes(audio_url)
        self._validate_pcm_wav(audio)
        descriptor, name = tempfile.mkstemp(suffix=".wav", dir=self.temp_dir)
        os.close(descriptor)
        path = Path(name)
        try:
            path.write_bytes(audio)
            try:
                played = self.runner(["aplay", "-q", "-D", device, str(path)], timeout=60.0)
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                result["playback_error"] = f"Playback failed: {exc}"
                return result
            if played.returncode != 0:
                result["playback_error"] = f"Playback failed: {(played.stderr or 'unknown aplay error').strip()}"
                return result
            result["played"] = True
            return result
        finally:
            path.unlink(missing_ok=True)


def create_mcp_server(control: AgentSpeakControl | None = None) -> Any:
    """Create the FastMCP server; import SDK only at executable startup."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised by the entry script
        raise RuntimeError("MCP SDK is missing; run ./scripts/setup.sh") from exc

    active = control or AgentSpeakControl(
        http=GatewayHTTPClient(os.getenv("AGENT_SPEAK_URL", "http://127.0.0.1:8765"))
    )
    server = FastMCP("agent-speak")

    @server.tool()
    def status() -> dict[str, Any]:
        """Check gateway reachability, health, and active provider capabilities."""
        return active.status()

    @server.tool()
    def capabilities() -> dict[str, Any]:
        """Return the gateway's provider and feature capability metadata."""
        return active.capabilities()

    @server.tool()
    def list_audio_devices() -> dict[str, Any]:
        """List local ALSA capture/playback devices with bounded command timeouts."""
        return active.list_audio_devices()

    @server.tool()
    def microphone_smoke(
        duration_seconds: int = 2, device: str = "default", user_confirmed: bool = False
    ) -> dict[str, Any]:
        """Record a bounded local WAV only after explicit end-user confirmation; the WAV is deleted."""
        return active.microphone_smoke(duration_seconds, device, user_confirmed)

    @server.tool()
    def listen_once(
        duration_seconds: int = 3, device: str = "default", user_confirmed: bool = False
    ) -> dict[str, Any]:
        """After explicit end-user confirmation, capture one WAV and transcribe it through HTTP ASR."""
        return active.listen_once(duration_seconds, device, user_confirmed)

    @server.tool()
    def speak(
        text: str, playback: bool = False, device: str = "default", user_confirmed: bool = False
    ) -> dict[str, Any]:
        """Synthesize speech; physical playback additionally requires explicit end-user confirmation."""
        return active.speak(text, playback, device, user_confirmed)

    return server


def main() -> None:
    """Run a stdio MCP server. Never write logs or status text to stdout."""
    from dotenv import load_dotenv

    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env", override=False)
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
