"""Tests for utils/api — async client + error taxonomy (httpx MockTransport).

No network: every test swaps httpx.AsyncClient's transport for a mock.
"""

from __future__ import annotations

import httpx
import pytest

from utils import api


@pytest.fixture
def mock_transport():
    """Factory: install a transport that replies with (status, json_body)."""

    def install(status: int = 200, body: dict | None = None, exc: Exception | None = None):
        def handler(request: httpx.Request) -> httpx.Response:
            if exc is not None:
                raise exc
            return httpx.Response(status, json=body if body is not None else {})

        transport = httpx.MockTransport(handler)

        class PatchedClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        return PatchedClient

    return install


VERDICT_BODY = {
    "verdict": {
        "is_scam": True,
        "confidence": 0.9,
        "scam_type": "bank_kyc",
        "risk_level": "critical",
        "red_flags": ["asks for OTP"],
        "summary": "scam",
        "recommended_action": "block",
        "evidence": [],
    },
    "analysis_metadata": {"input_type": "text"},
}


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------

class TestSuccess:
    async def test_analyze_text_posts_multipart(self, mock_transport, monkeypatch):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = request.content
            return httpx.Response(200, json=VERDICT_BODY)

        transport = httpx.MockTransport(handler)

        class C(httpx.AsyncClient):
            def __init__(self, *a, **k):
                k["transport"] = transport
                super().__init__(*a, **k)

        monkeypatch.setattr(httpx, "AsyncClient", C)
        out = await api.analyze_text("your account will be blocked")
        assert out["verdict"]["is_scam"] is True
        assert seen["url"].endswith("/analyze")
        assert b"text=" in seen["body"]  # multipart form contains the field

    async def test_analyze_url_uses_url_endpoint(self, mock_transport, monkeypatch):
        monkeypatch.setattr(httpx, "AsyncClient", mock_transport(200, {"urls_analyzed": []}))
        out = await api.analyze_url("https://example.com")
        assert "urls_analyzed" in out

    async def test_analyze_image_uses_image_endpoint(self, mock_transport, monkeypatch):
        monkeypatch.setattr(
            httpx, "AsyncClient", mock_transport(200, {"ocr_text": "hi", "verdict": {}})
        )
        out = await api.analyze_image("a.png", b"\x89PNG", "image/png")
        assert out["ocr_text"] == "hi"

    async def test_analyze_audio_uses_voice_endpoint(self, mock_transport, monkeypatch):
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            mock_transport(200, {"transcript": "hello", "verdict": {}}),
        )
        out = await api.analyze_audio("n.ogg", b"OggS", "audio/ogg")
        assert out["transcript"] == "hello"

    async def test_health_returns_none_on_error(self, mock_transport, monkeypatch):
        monkeypatch.setattr(httpx, "AsyncClient", mock_transport(500, {}))
        assert await api.health() is None


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

class TestErrors:
    async def test_400_raises_api_error(self, mock_transport, monkeypatch):
        monkeypatch.setattr(
            httpx, "AsyncClient", mock_transport(400, {"detail": "Provide text, url, or file"})
        )
        with pytest.raises(api.ApiError) as exc:
            await api.analyze_text("")
        assert exc.value.status == 400

    async def test_503_raises_api_error(self, mock_transport, monkeypatch):
        monkeypatch.setattr(httpx, "AsyncClient", mock_transport(503, {"detail": "busy"}))
        with pytest.raises(api.ApiError) as exc:
            await api.analyze_text("x")
        assert exc.value.status == 503

    async def test_timeout_raises_api_timeout(self, mock_transport, monkeypatch):
        monkeypatch.setattr(
            httpx, "AsyncClient", mock_transport(exc=httpx.ReadTimeout("slow"))
        )
        with pytest.raises(api.ApiTimeout):
            await api.analyze_text("x")

    async def test_connect_error_raises_connection_error(self, mock_transport, monkeypatch):
        monkeypatch.setattr(
            httpx, "AsyncClient", mock_transport(exc=httpx.ConnectError("refused"))
        )
        with pytest.raises(api.ApiConnectionError):
            await api.analyze_text("x")

    async def test_bad_json_raises_decode_error(self, mock_transport, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not json at all")

        class C(httpx.AsyncClient):
            def __init__(self, *a, **k):
                k["transport"] = httpx.MockTransport(handler)
                super().__init__(*a, **k)

        monkeypatch.setattr(httpx, "AsyncClient", C)
        with pytest.raises(api.ApiDecodeError):
            await api.analyze_text("x")


# ---------------------------------------------------------------------------
# friendly_error mapping (spec 2.1 Step 4 table)
# ---------------------------------------------------------------------------

class TestFriendlyErrors:
    @pytest.mark.parametrize(
        "exc,expected",
        [
            (api.ApiError(400), "Invalid input"),
            (api.ApiError(503), "temporarily busy"),
            (api.ApiError(504), "timed out"),
            (api.ApiError(500), "Something went wrong on the server"),
            (api.ApiTimeout(), "timed out"),
            (api.ApiConnectionError(), "Cannot reach the analysis server"),
            (api.ApiDecodeError(), "server error"),
            (api.ApiError(422, "Unsupported audio format: .xyz"), ".xyz"),
            (RuntimeError("boom"), "Something went wrong"),
        ],
    )
    def test_mapping(self, exc, expected):
        assert expected in api.friendly_error(exc)
