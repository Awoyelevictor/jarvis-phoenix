import json

from app.assistant import Assistant
from app.config import Settings
from app.providers import OpenAICompatibleProvider, ProviderError


class FakeStreamResponse:
    def __init__(self, lines):
        self.lines = [line.encode("utf-8") for line in lines]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(self.lines)


def test_cloud_provider_yields_sse_content_deltas(monkeypatch):
    response = FakeStreamResponse([
        'data: {"choices":[{"delta":{"content":"Hello"}}]}\\n',
        'data: {"choices":[{"delta":{"content":" there"}}]}\\n',
        "data: [DONE]\\n",
    ])
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return response

    monkeypatch.setattr("app.providers.urlopen", fake_urlopen)
    settings = Settings(
        cloud_base_url="https://example.test/v1",
        cloud_api_key="test-key",
        cloud_model="test-model",
    )
    provider = OpenAICompatibleProvider(settings)

    assert list(provider.stream_chat([{"role": "user", "content": "Hi"}])) == ["Hello", " there"]
    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert payload["stream"] is True
    assert captured["request"].get_header("Accept") == "text/event-stream"


class FakeCloud:
    configured = True

    def __init__(self, fragments=None, error=None):
        self.fragments = fragments or []
        self.error = error

    def stream_chat(self, messages):
        if self.error:
            raise self.error
        yield from self.fragments


class FakeLocal:
    def __init__(self, answer="local answer"):
        self.answer = answer

    def chat(self, messages):
        return self.answer


def make_assistant(tmp_path):
    assistant = Assistant(Settings(memory_db_path=str(tmp_path / "memory.sqlite3")))
    assistant.cloud = FakeCloud()
    assistant.local = FakeLocal()
    return assistant


def test_assistant_streams_fragments_and_saves_completed_turn(tmp_path):
    assistant = make_assistant(tmp_path)
    assistant.cloud = FakeCloud(["Hello", " from", " ULTRON"])

    assert list(assistant.respond_stream("Say hello")) == ["Hello", " from", " ULTRON"]
    assert assistant.messages[-1] == {
        "role": "assistant",
        "content": "Hello from ULTRON",
    }


def test_assistant_uses_local_fallback_when_cloud_fails_before_first_token(tmp_path):
    assistant = make_assistant(tmp_path)
    assistant.cloud = FakeCloud(error=ProviderError("cloud unavailable"))

    assert list(assistant.respond_stream("Say hello")) == ["local answer"]
    assert assistant.messages[-1]["content"] == "local answer"


def test_assistant_rejects_empty_stream_prompt(tmp_path):
    assistant = make_assistant(tmp_path)

    try:
        list(assistant.respond_stream("   "))
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected empty prompt to be rejected")
