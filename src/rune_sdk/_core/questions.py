"""Normalize SDK question helpers to the Rune decisions wire format."""

from collections.abc import Mapping, Sequence
from typing import Any

from rune_sdk._core.errors import RuneError
from rune_sdk._core.json_types import JSONContent
from rune_sdk._core.question_types import Choice, Noul, Question, Score


def normalize_questions(questions: Mapping[str, Question]) -> dict[str, dict[str, Any]]:
    if not questions:
        raise RuneError("At least one question is required.")
    normalized: dict[str, dict[str, Any]] = {}
    for name, question in questions.items():
        item: dict[str, Any]
        if isinstance(question, (Choice, Noul, Score)):
            item = question.model_dump()
        else:
            if not isinstance(question, dict) or not isinstance(question.get("type"), str) or not question["type"]:
                raise RuneError(f'Question "{name}" must be a question object or a dictionary with a nonempty string "type".')
            item = dict(question)
        if item["type"] not in ("noul", "choice", "score"):
            normalized[name] = item
            continue
        if item.get("instructions") is None:
            item["instructions"] = ""
        kind = item["type"]
        if kind in ("choice", "score") and "criteria" not in item:
            raise RuneError(f'Question "{name}" requires "criteria".')
        if kind == "noul":
            criteria = item.get("criteria") or {}
            if isinstance(criteria, Mapping):
                item["criteria"] = {**criteria, **{key: criteria.get(key) if criteria.get(key) is not None else key for key in ("true", "false")}}
        elif kind == "choice" and isinstance(item["criteria"], Mapping):
            item["criteria"] = {key: value if value is not None else key for key, value in item["criteria"].items()}
        elif kind == "score":
            _validate_score_criteria(name, item["criteria"])
            item["criteria"] = [value if value is not None else str(index) for index, value in enumerate(item["criteria"])]
        normalized[name] = item
    return normalized


def _validate_score_criteria(name: str, criteria: Sequence[JSONContent]) -> None:
    if len(criteria) < 2:
        raise RuneError(f'Score question "{name}" has fewer than two criteria; at least two scores are required.')
