"""Keep VOS reply language tied to the current user message, not the UI locale."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

REPLY_LANGUAGE_POLICY = (
    "Response language policy: Follow an explicit output-language request in the latest user "
    "message. Otherwise reply in the language of that latest user message: answer English "
    "questions in English and Chinese questions in Chinese, including when the user switches "
    "languages within an existing conversation. For translation, use the requested target "
    "language. UI locale, earlier conversation language, tool output language and default "
    "language preferences in workspace files or memory must not override this rule. "
    "Judge the user's own request, rather than the language of quoted documents or code."
)


def _with_reply_language(request: ModelRequest[Any]) -> ModelRequest[Any]:
    if not os.environ.get("VA_SKILLS_DIR"):
        return request
    previous = request.system_message
    if previous is None:
        message = SystemMessage(content=REPLY_LANGUAGE_POLICY)
    else:
        content = previous.content
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else list(content)
        if any(
            isinstance(block, dict) and block.get("text") == REPLY_LANGUAGE_POLICY
            for block in blocks
        ):
            return request
        blocks.append({"type": "text", "text": REPLY_LANGUAGE_POLICY})
        message = previous.model_copy(update={"content": blocks})
    return request.override(system_message=message)


class ReplyLanguageMiddleware(AgentMiddleware[Any, Any]):
    def wrap_model_call(
        self, request: ModelRequest[Any], handler: Callable[[ModelRequest[Any]], ModelResponse[Any]]
    ) -> ModelResponse[Any]:
        return handler(_with_reply_language(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        return await handler(_with_reply_language(request))
