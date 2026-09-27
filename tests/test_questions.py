import copy
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

import httpx2
import pytest
from pydantic import BaseModel, ValidationError
from pydantic_core import from_json, to_json

from rune_sdk import (
    AsyncRuneClient,
    Choice,
    ChoiceModel,
    Noul,
    NoulCriteria,
    NoulModel,
    Question,
    Questions,
    RuneError,
    Score,
    ScoreModel,
)
from rune_sdk._core.questions import normalize_questions
from rune_sdk._schemas import models as wire
from tests.conftest import ClientFactory


def test_normalization_preserves_inputs() -> None:
    questions = {
        "noul": Noul(instructions="Spam?"),
        "choice": Choice(instructions="Tone?", criteria={"calm": None}),
        "score": Score(instructions="Quality?", criteria=["bad", "good"]),
    }
    result = normalize_questions(questions)
    assert questions["noul"].criteria is None
    assert questions["choice"].criteria == {"calm": None}
    assert questions["score"].criteria == ["bad", "good"]
    assert from_json(to_json(result)) == {
        "noul": {"type": "noul", "instructions": "Spam?", "criteria": {"true": "true", "false": "false"}},
        "choice": {"type": "choice", "instructions": "Tone?", "criteria": {"calm": "calm"}},
        "score": {"type": "score", "instructions": "Quality?", "criteria": ["bad", "good"]},
    }


def test_normalization_preserves_unknown_fields_and_copies_raw_inputs() -> None:
    raw = {"type": "future", "nested": {"k": None}}
    before = copy.deepcopy(raw)
    result = normalize_questions(cast(Questions, {"raw": raw}))
    assert result == {"raw": raw}
    assert raw == before
    assert result["raw"] is not raw


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        {"instructions": "Missing type"},
        {"type": "choice"},
        {"type": "score"},
        {"type": ""},
        {"type": None},
        {"type": 1},
        {"type": ["future"]},
        "noul",
        None,
    ],
)
def test_raw_questions_require_structural_keys(invalid: object) -> None:
    with pytest.raises(RuneError, match='Question "invalid"'):
        normalize_questions(cast(Questions, {"invalid": invalid}))


@pytest.mark.parametrize(
    "question,expected",
    [
        (Noul(), {"type": "noul"}),
        (Choice(criteria={"a": None}), {"type": "choice", "criteria": {"a": None}}),
        (Score(criteria=["bad", "good"]), {"type": "score", "criteria": ["bad", "good"]}),
        (Noul(instructions="", criteria={}), {"type": "noul", "instructions": "", "criteria": {}}),
        (Noul(instructions=[], criteria={"true": None}), {"type": "noul", "instructions": [], "criteria": {"true": None}}),
    ],
)
def test_direct_encoding_omits_only_default_fields(question: Noul | Choice | Score, expected: dict[str, Any]) -> None:
    assert from_json(to_json(question)) == expected
    assert question.model_dump() == expected


def test_discriminators_are_automatic() -> None:
    noul = Noul(instructions="Spam?")
    choice = Choice(instructions="Tone?", criteria={"calm": None})
    score = Score(instructions="Quality?", criteria=["bad", "good"])
    for question, wire_type, tag in (
        (noul, wire.NoulQuestion, "noul"),
        (choice, wire.ChoiceQuestion, "choice"),
        (score, wire.ScoreQuestion, "score"),
    ):
        assert isinstance(question, BaseModel)
        assert isinstance(question, wire_type)
        assert question.type == tag
        assert question.model_dump()["type"] == tag
        assert from_json(to_json(question))["type"] == tag
        # Construction is keyword-only: a positional argument is rejected.
        with pytest.raises(TypeError):
            cast(Any, type(question))("Spam?")
        question.instructions = "Updated?"
        assert question.model_dump()["instructions"] == "Updated?"


def test_invalid_typed_question_is_rejected_on_construction() -> None:
    # Unlike raw dictionaries, typed questions validate eagerly rather than deferring to the API.
    with pytest.raises(ValidationError):
        Choice(criteria=cast(Any, ["invalid", "shape"]))


@pytest.mark.parametrize(
    "question_type,kwargs",
    [
        (Noul, {}),
        (Choice, {"criteria": {"a": None}}),
        (Score, {"criteria": ["bad", "good"]}),
    ],
)
def test_typed_questions_reject_unknown_fields(question_type: Any, kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        question_type(**kwargs, unexpected=True)


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize(
    "criteria",
    [
        None,
        {},
        {"true": "Yes"},
        {"false": "No"},
        {"true": "Yes", "false": "No"},
        {"true": {"summary": "Unsolicited", "examples": ["Buy now"]}},
    ],
)
def test_optional_noul_criteria(raw: bool, criteria: NoulCriteria | None) -> None:
    expected: NoulModel = {"type": "noul", "instructions": "Spam?"}
    if criteria is not None:
        expected["criteria"] = criteria
    question: Question
    if raw:
        question = expected.copy()
    else:
        question = Noul(instructions="Spam?", criteria=criteria)
    expected["criteria"] = {"true": (criteria or {}).get("true", "true"), "false": (criteria or {}).get("false", "false")}
    assert from_json(to_json(normalize_questions({"q": question}))) == {"q": expected}


@pytest.mark.parametrize("raw", [False, True])
def test_single_score_criterion_is_preserved(raw: bool) -> None:
    model = cast(ScoreModel, {"type": "score", "instructions": "Quality?", "criteria": ["only"]})
    question = model if raw else Score(instructions=model["instructions"], criteria=model["criteria"])
    assert normalize_questions({"rating": question})["rating"]["criteria"] == ["only"]


def test_typed_noul_criteria_reject_unknown_fields() -> None:
    criteria = cast(NoulCriteria, {"true": "yes", "metadata": {"source": None}})
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Noul(criteria=criteria)


@pytest.mark.parametrize("raw", [False, True])
def test_empty_score_criteria_is_rejected(raw: bool) -> None:
    model = cast(ScoreModel, {"type": "score", "instructions": "Quality?", "criteria": []})
    question = model if raw else Score(instructions=model["instructions"], criteria=model["criteria"])
    with pytest.raises(RuneError, match='"rating" has no criteria'):
        normalize_questions({"rating": question})


async def test_covariant_question_mappings(clients: ClientFactory) -> None:
    nouls = {"q": Noul(instructions="Spam?")}
    choices = {"q": Choice(instructions="Tone?", criteria={"calm": None})}
    scores = {"q": Score(instructions="Quality?", criteria=["bad", "good"])}
    raw_nouls: dict[str, NoulModel] = {"q": {"type": "noul", "instructions": "Spam?"}}
    raw_choices: dict[str, ChoiceModel] = {"q": {"type": "choice", "instructions": "Tone?", "criteria": {"calm": None}}}
    raw_scores: dict[str, ScoreModel] = {"q": {"type": "score", "instructions": "Quality?", "criteria": ["bad", "good"]}}
    read_only: Mapping[str, Choice] = MappingProxyType(choices)
    mixed: Questions = {"one": nouls["q"], "two": raw_choices["q"], "three": scores["q"]}
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        assert from_json(request.content)["questions"]
        return httpx2.Response(200, json={"model": "rune-v3", "usage": {}, "answers": {}})

    client = clients(handler)
    if isinstance(client, AsyncRuneClient):
        await client.decide("x", nouls)
        await client.decide("x", choices)
        await client.decide("x", scores)
        await client.decide("x", raw_nouls)
        await client.decide("x", raw_choices)
        await client.decide("x", raw_scores)
        await client.decide("x", read_only)
        await client.decide("x", mixed)
        await client.decide("x", {"q": {"type": "choice", "instructions": "Tone?", "criteria": {"calm": None}}})
    else:
        client.decide("x", nouls)
        client.decide("x", choices)
        client.decide("x", scores)
        client.decide("x", raw_nouls)
        client.decide("x", raw_choices)
        client.decide("x", raw_scores)
        client.decide("x", read_only)
        client.decide("x", mixed)
        client.decide("x", {"q": {"type": "choice", "instructions": "Tone?", "criteria": {"calm": None}}})
    assert calls == 9
    assert scores["q"].criteria == ["bad", "good"]
    assert raw_scores["q"]["criteria"] == ["bad", "good"]
    assert read_only["q"] is choices["q"]
