from app.assistant import Assistant
from app.config import Settings
from app.providers import ProviderError


class FakeCloud:
    configured = True

    def __init__(self, answer=None, error=None):
        self.answer = answer
        self.error = error
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.answer


class FakeLocal:
    def __init__(self, answer="local answer", error=None):
        self.answer = answer
        self.error = error
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.answer

    def check(self):
        return "Ollama is not reachable."


def make_assistant(history_limit=20):
    assistant = Assistant(Settings(conversation_history_messages=history_limit))
    assistant.cloud = FakeCloud()
    assistant.local = FakeLocal()
    return assistant


def test_cloud_is_preferred_when_available():
    assistant = make_assistant()
    assistant.cloud.answer = "cloud answer"

    assert assistant.respond("Hello") == "cloud answer"
    assert len(assistant.cloud.calls) == 1
    assert assistant.local.calls == []


def test_local_is_used_when_cloud_fails():
    assistant = make_assistant()
    assistant.cloud.error = ProviderError("cloud offline")

    assert assistant.respond("Hello") == "local answer"
    assert len(assistant.local.calls) == 1
    assert assistant.messages[-1] == {
        "role": "assistant",
        "content": "local answer",
    }


def test_conversation_context_is_sent_on_follow_up():
    assistant = make_assistant()
    assistant.cloud.answer = "first answer"
    assistant.respond("Remember my project is Phoenix")

    assistant.cloud.answer = "You are building Phoenix"
    assert assistant.respond("What is my project?") == "You are building Phoenix"

    second_request = assistant.cloud.calls[1]
    assert second_request[0]["role"] == "system"
    assert second_request[1] == {
        "role": "user",
        "content": "Remember my project is Phoenix",
    }
    assert second_request[2] == {
        "role": "assistant",
        "content": "first answer",
    }
    assert second_request[3] == {
        "role": "user",
        "content": "What is my project?",
    }


def test_conversation_history_is_bounded_and_can_be_reset():
    assistant = make_assistant(history_limit=2)
    assistant.cloud.answer = "answer"
    assistant.respond("one")
    assistant.respond("two")

    assert len(assistant.messages) == 2
    assistant.reset_conversation()
    assert assistant.messages == []


def test_failed_providers_do_not_store_an_unanswered_prompt():
    assistant = make_assistant()
    assistant.cloud.error = ProviderError("cloud offline")
    assistant.local.error = ProviderError("local offline")

    try:
        assistant.respond("This should not be remembered")
    except ProviderError:
        pass
    else:
        raise AssertionError("Expected ProviderError")

    assert assistant.messages == []
