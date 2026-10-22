from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agent.llm import LLMClient
from src.config import LLMProvider


@pytest.mark.asyncio
async def test_deepseek_uses_json_output_and_non_thinking_mode(monkeypatch):
    monkeypatch.setenv('PUBLIC_DEMO', '0')
    client = LLMClient()
    client.settings = SimpleNamespace(llm=SimpleNamespace(
        provider=LLMProvider.OPENAI, openai_base_url='https://api.deepseek.com',
        openai_model='deepseek-flash', openai_temperature=0.1, openai_max_tokens=1024,
    ))
    create = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"intent":"greeting"}', tool_calls=None))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15), model='deepseek-flash',
    ))
    client._openai_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = await client.chat([{'role': 'user', 'content': 'Return JSON'}], json_mode=True)
    assert result.model == 'deepseek-flash'
    request = create.call_args.kwargs
    assert request['response_format'] == {'type': 'json_object'}
    assert request['extra_body'] == {'thinking': {'type': 'disabled'}}
    assert request['max_tokens'] == 1024
