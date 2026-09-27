from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

import httpx2
from typing_extensions import assert_type

from rune_sdk import (
    AsyncRuneClient,
    Choice,
    ChoiceAnswer,
    ChoiceModel,
    DecisionsResponse,
    ImageInput,
    ListModelsResponse,
    Questions,
    RetryPolicy,
    RuneClient,
    Score,
)


def sync(client: RuneClient) -> None:
    objects: dict[str, Choice] = {"q": Choice(instructions="?", criteria={"a": None})}
    data: dict[str, ChoiceModel] = {"q": {"type": "choice", "instructions": "?", "criteria": {"a": None}}}
    # Abstract inputs: a MappingProxyType with a nested tuple as state, and tuple score criteria.
    state = MappingProxyType({"items": ("a", None)})
    assert_type(client.decide(state, {"s": Score(criteria=("low", "high"))}), DecisionsResponse)
    assert_type(client.decide({"nullable": None}, objects, retry=RetryPolicy(), timeout=httpx2.Timeout(None)), DecisionsResponse)
    assert_type(client.decide("x", data, model="test", extra_headers={"x-call": "test"}), DecisionsResponse)
    future_questions = cast(Questions, {"q": {"type": "noul", "instructions": "?", "weight": 2}})
    assert_type(client.decide("x", future_questions, retry=RetryPolicy(max_retries=1)), DecisionsResponse)
    assert_type(client.decide("x", data, extra_body={"beam_width": 4, "nullable": None}), DecisionsResponse)
    assert_type(client.models.list(retry=RetryPolicy(), timeout=2.0, extra_headers={"x-call": "test"}), ListModelsResponse)
    RuneClient(retry=RetryPolicy(max_retries=1))
    images: tuple[ImageInput, ...] = ("data:image/png;base64,aW1hZ2U=", {"url": "data:image/png;base64,aW1hZ2U="})
    assert_type(client.decide("Inspect these images", objects, images=images, thinking=False), DecisionsResponse)
    result = client.decide("An uncertain decision", objects, thinking=True)
    if (thinking := result.choices["q"].thinking) is not None:
        assert_type(thinking.tokens, int)
        assert_type(thinking.closed, bool)
        if isinstance(thinking.onepass, ChoiceAnswer):
            assert_type(thinking.onepass.choice, str)


async def asynchronous(client: AsyncRuneClient) -> None:
    objects: Mapping[str, Choice] = {"q": Choice(instructions="?", criteria={"a": None})}
    data: dict[str, ChoiceModel] = {"q": {"type": "choice", "instructions": "?", "criteria": {"a": None}}}
    assert_type(await client.decide({"nullable": None}, objects, retry=RetryPolicy(), timeout=2.0), DecisionsResponse)
    assert_type(await client.decide("x", data, model="test", extra_headers={"x-call": "test"}), DecisionsResponse)
    future_questions = cast(Questions, {"q": {"type": "noul", "instructions": "?", "weight": 2}})
    assert_type(await client.decide("x", future_questions, retry=RetryPolicy()), DecisionsResponse)
    assert_type(await client.decide("x", data, extra_body={"beam_width": 4, "nullable": None}), DecisionsResponse)
    assert_type(await client.models.list(retry=RetryPolicy(), timeout=2.0, extra_headers={"x-call": "test"}), ListModelsResponse)
    AsyncRuneClient(retry=RetryPolicy(max_retries=1))
    assert_type(await client.decide("Inspect this image", objects, images=[{"url": "data:image/png;base64,aW1hZ2U="}]), DecisionsResponse)
    assert_type(await client.decide("An uncertain decision", objects, thinking=True), DecisionsResponse)
