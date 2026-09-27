import copy

import httpx2
import pytest
from pydantic_core import from_json

from rune_sdk import AsyncRuneClient, ImageInput, Noul, NoulAnswer, RuneRateLimitError
from tests.conftest import ClientFactory


@pytest.mark.parametrize("mode", ["text", "image", "thinking"])
async def test_rune_request_and_response_contract(clients: ClientFactory, mode: str) -> None:
    images: list[ImageInput] | None = ["data:image/png;base64,aW1hZ2U=", {"url": "data:image/png;base64,dHdv"}] if mode == "image" else None
    before = copy.deepcopy(images)
    answer = {"type": "noul", "noul": 0.9}
    if mode == "thinking":
        answer["thinking"] = {"tokens": 7, "closed": True, "onepass": {"type": "noul", "noul": 0.55}}
    wire = {
        "id": "dec-test", "model": "rune-v3", "provider": "test",
        "answers": {"yes": answer},
        "usage": {"input_tokens": 10, "output_tokens": 1, "cost": 0, "reasoning_tokens": 7 if mode == "thinking" else 0},
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "https://rune.surogate.ai/v1/decisions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = from_json(request.content)
        expected = {
            "model": "rune-v3", "state": {"value": "test"},
            "questions": {"yes": {"type": "noul", "instructions": "Is this a test?", "criteria": {"true": "true", "false": "false"}}},
        }
        if mode == "image":
            expected["images"] = images
        if mode == "thinking":
            expected["thinking"] = True
        assert body == expected
        return httpx2.Response(200, json=wire)

    client = clients(handler)
    kwargs = {"images": images, "thinking": True if mode == "thinking" else None}
    if isinstance(client, AsyncRuneClient):
        result = await client.decide({"value": "test"}, {"yes": Noul(instructions="Is this a test?")}, **kwargs)
    else:
        result = client.decide({"value": "test"}, {"yes": Noul(instructions="Is this a test?")}, **kwargs)
    assert images == before
    assert result.id == "dec-test"
    assert result.provider == "test"
    assert result.usage.cost == 0
    assert result.model_dump() == wire
    if mode == "thinking":
        thinking = result.nouls["yes"].thinking
        assert thinking is not None
        assert thinking.tokens == 7
        assert isinstance(thinking.onepass, NoulAnswer)
        assert thinking.onepass.noul == 0.55


async def test_rune_rate_limit_envelope(clients: ClientFactory) -> None:
    client = clients(lambda request: httpx2.Response(429, json={"error": {
        "type": "rate_limit_error", "code": "rate_limit_exceeded", "message": "Try again later",
    }}, headers={"Retry-After": "1"}))
    with pytest.raises(RuneRateLimitError, match="Try again later") as caught:
        if isinstance(client, AsyncRuneClient):
            await client.models.list()
        else:
            client.models.list()
    assert caught.value.retry_after_ms == 1000
