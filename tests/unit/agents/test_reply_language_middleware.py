from langchain.agents.middleware import ModelRequest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from octop.infra.agents.middleware.reply_language import REPLY_LANGUAGE_POLICY, _with_reply_language


def test_vos_language_policy_preserves_history_and_existing_instructions(monkeypatch):
    monkeypatch.setenv("VA_SKILLS_DIR", "/product/skills")
    messages = [
        HumanMessage(content="你是谁"),
        AIMessage(content="我是助手"),
        HumanMessage(content="Who are you?"),
    ]
    request = ModelRequest(
        model=FakeListChatModel(responses=["fixture"]),
        messages=messages,
        system_message=SystemMessage(content="Keep the user's workspace instructions."),
    )
    routed = _with_reply_language(request)
    assert routed.messages == messages
    assert "Keep the user's workspace instructions." in str(routed.system_message.content)
    assert REPLY_LANGUAGE_POLICY in str(routed.system_message.content)
    assert _with_reply_language(routed) is routed
    assert request.system_message.content == "Keep the user's workspace instructions."


def test_standalone_prompt_is_unchanged(monkeypatch):
    monkeypatch.delenv("VA_SKILLS_DIR", raising=False)
    request = ModelRequest(model=FakeListChatModel(responses=["fixture"]), messages=[])
    assert _with_reply_language(request) is request
