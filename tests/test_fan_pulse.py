import json
from unittest.mock import patch

from fan_pulse import FanPulseService, search_x_with_grok


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
def test_grok_x_search_uses_only_xai_key_and_returns_usage_count(mock_open):
    mock_open.return_value = _Response(json.dumps({
        "output_text": json.dumps({
            "summary": "In this sample, fans are excited.", "intensity": 78, "level": "high",
            "game_context": "A close match is in progress.", "event": "yellow_card",
            "event_confidence": "high",
        }),
        "usage": {"server_side_tool_usage_details": {"x_posts_fetched": 12, "web_search_calls": 1}},
    }).encode())
    assert search_x_with_grok("Georgia Tech", "key") == {
        "summary": "In this sample, fans are excited.", "intensity": 78, "level": "high",
        "game_context": "A close match is in progress.", "event": "yellow_card",
        "event_confidence": "high", "sampled_posts": 12, "web_searches": 1,
    }
    request = mock_open.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer key"
    assert request.full_url.endswith("/responses")
    payload = json.loads(request.data.decode())
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["tools"] == [{"type": "web_search"}, {"type": "x_search"}]


def test_service_reports_missing_credentials_without_network(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    service = FanPulseService("Georgia Tech")
    service._run_once()
    assert service.latest().error == "missing credentials"


@patch("fan_pulse.urlopen", side_effect=TimeoutError("timed out"))
def test_grok_x_search_turns_timeout_into_actionable_error(_mock_open):
    try:
        search_x_with_grok("Georgia Tech", "key")
    except RuntimeError as error:
        assert "45 seconds" in str(error)
    else:
        raise AssertionError("timeout should be reported as a RuntimeError")
