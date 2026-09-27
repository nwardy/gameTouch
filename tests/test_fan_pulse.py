import json
from unittest.mock import patch

from fan_pulse import FanPulseService, fetch_recent_posts, summarize_with_grok


class _Response:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@patch("fan_pulse.urlopen")
def test_fetch_recent_posts_is_bounded_and_uses_bearer_auth(mock_open):
    mock_open.return_value = _Response(json.dumps({"data": [{"text": "Great goal"}]}).encode())
    assert fetch_recent_posts("Georgia Tech", "token", max_results=999) == ["Great goal"]
    request = mock_open.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer token"
    assert "max_results=100" in request.full_url


@patch("fan_pulse.urlopen")
def test_grok_summary_extracts_content(mock_open):
    mock_open.return_value = _Response(json.dumps({
        "choices": [{"message": {"content": "In this sample, fans are excited."}}]
    }).encode())
    assert summarize_with_grok(["What a finish"], "key") == "In this sample, fans are excited."


def test_service_reports_missing_credentials_without_network(monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    service = FanPulseService("Georgia Tech")
    service._run()
    assert service.latest().error == "missing credentials"
