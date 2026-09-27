from types import MappingProxyType
from typing import get_type_hints

import httpx2
import pytest
from pydantic import TypeAdapter, ValidationError
from pydantic_core import from_json

from rune_sdk import (
    AsyncRuneClient,
    Choice,
    JSONContent,
    JSONValue,
    Noul,
    Questions,
    RuneClient,
    Score,
)
from rune_sdk._core.json import _fallback
from tests.conftest import ClientFactory
from tests.helpers import decide


def test_str_subclasses_fallback_to_strings() -> None:
    class StrSubclass(str):
        __slots__ = ()

    value = _fallback(StrSubclass("ARPANET"))
    assert value == "ARPANET"
    assert type(value) is str


def test_json_value_and_state_exclude_top_level_none() -> None:
    # `state` is annotated with the `JSONContent` alias.
    for client in (AsyncRuneClient, RuneClient):
        assert get_type_hints(client.decide)["state"] is JSONContent
    # Both JSON aliases forbid a bare top-level `None`, while accepting the text, mapping, and
    # sequence forms — and `None` remains valid *nested* as a value.
    for alias in (JSONContent, JSONValue):
        adapter: TypeAdapter[object] = TypeAdapter(alias)
        with pytest.raises(ValidationError):
            adapter.validate_python(None)
        assert adapter.validate_python("text") == "text"
        assert adapter.validate_python({"key": None}) == {"key": None}
        assert adapter.validate_python(["item", None]) == ["item", None]


@pytest.mark.parametrize("raw", [False, True])
async def test_array_inputs(clients: ClientFactory, raw: bool) -> None:
    state: list[JSONValue | None] = [{"message": "Classify"}, None]
    instructions: list[JSONValue | None] = ["Read the message", {"context": None}]
    description: list[JSONValue | None] = ["Example", None]
    questions: Questions
    if raw:
        questions = {
            "yes": {"type": "noul", "instructions": instructions, "criteria": {"true": description, "false": "false"}},
            "label": {"type": "choice", "instructions": instructions, "criteria": {"a": description, "b": "b"}},
            "rating": {"type": "score", "instructions": instructions, "criteria": [description, "other"]},
        }
    else:
        questions = {
            "yes": Noul(instructions=instructions, criteria={"true": description, "false": None}),
            "label": Choice(instructions=instructions, criteria={"a": description, "b": None}),
            "rating": Score(instructions=instructions, criteria=[description, "other"]),
        }

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = from_json(request.content)
        assert body["state"] == state
        assert body["questions"] == {
            "yes": {"type": "noul", "instructions": instructions, "criteria": {"true": description, "false": "false"}},
            "label": {"type": "choice", "instructions": instructions, "criteria": {"a": description, "b": "b"}},
            "rating": {"type": "score", "instructions": instructions, "criteria": [description, "other"]},
        }
        return httpx2.Response(200, json={"model": "rune-v3", "usage": {}, "answers": {}})

    await decide(clients(handler), state=state, questions=questions)


async def test_raw_optional_fields_materialize_defaults(clients: ClientFactory) -> None:
    questions: Questions = {
        "yes": {"type": "noul", "instructions": None, "criteria": None},
        "label": {"type": "choice", "instructions": None, "criteria": {"a": None}},
        "rating": {"type": "score", "instructions": None, "criteria": ["bad", "good"]},
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert from_json(request.content)["questions"] == {
            "yes": {"type": "noul", "instructions": "", "criteria": {"true": "true", "false": "false"}},
            "label": {"type": "choice", "instructions": "", "criteria": {"a": "a"}},
            "rating": {"type": "score", "instructions": "", "criteria": ["bad", "good"]},
        }
        return httpx2.Response(200, json={"model": "rune-v3", "usage": {}, "answers": {}})

    await decide(clients(handler), state="x", questions=questions)


async def test_explicitly_nullable_json_values(clients: ClientFactory) -> None:
    state: dict[str, JSONValue | None] = {"missing": None, "items": [None, {"nested": None}]}
    instructions: dict[str, JSONValue | None] = {"text": "Classify", "extra": None}

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = from_json(request.content)
        assert body["state"] == state
        assert body["questions"] == {
            "yes": {"type": "noul", "instructions": instructions, "criteria": {"true": {"extra": None}, "false": "false"}},
            "label": {"type": "choice", "instructions": instructions, "criteria": {"a": "a", "b": {"extra": None}}},
            "rating": {"type": "score", "instructions": instructions, "criteria": [{"extra": None}, "other"]},
        }
        return httpx2.Response(200, json={"model": "rune-v3", "usage": {}, "answers": {}})

    client = clients(handler)
    questions = {
        "yes": Noul(instructions=instructions, criteria={"true": {"extra": None}}),
        "label": Choice(instructions=instructions, criteria={"a": None, "b": {"extra": None}}),
        "rating": Score(instructions=instructions, criteria=[{"extra": None}, "other"]),
    }
    if isinstance(client, AsyncRuneClient):
        await client.decide(state, questions)
    else:
        client.decide(state, questions)


async def test_abstract_input_containers_encode(clients: ClientFactory) -> None:
    # Inputs are typed as Mapping/Sequence at every level: a MappingProxyType with a nested tuple, and
    # tuple criteria, must type-check and encode like dict/list.
    state = MappingProxyType({"items": ("a", None)})
    questions: Questions = {
        "label": Choice(instructions=("read", {"ctx": None}), criteria=MappingProxyType({"a": None, "b": "x"})),
        "rating": Score(criteria=("low", "high")),
        "raw": {"type": "score", "criteria": ("bad", "good")},
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert from_json(request.content) == {
            "state": {"items": ["a", None]},
            "model": "rune-v3",
            "questions": {
                "label": {"type": "choice", "instructions": ["read", {"ctx": None}], "criteria": {"a": "a", "b": "x"}},
                "rating": {"type": "score", "instructions": "", "criteria": ["low", "high"]},
                "raw": {"type": "score", "instructions": "", "criteria": ["bad", "good"]},
            },
        }
        return httpx2.Response(200, json={"model": "rune-v3", "usage": {}, "answers": {}})

    await decide(clients(handler), state=state, questions=questions, model="rune-v3")
