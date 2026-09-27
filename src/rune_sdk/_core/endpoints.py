"""Endpoint-specific request builders, layered over the generic `transport.prepare`."""

from collections.abc import Mapping, Sequence
from typing import Any

import httpx2

from rune_sdk._core.config import Config
from rune_sdk._core.constants import DECISIONS_PATH, MODELS_PATH
from rune_sdk._core.json_types import JSONContent, JSONValue
from rune_sdk._core.question_types import ImageInput, Question
from rune_sdk._core.questions import normalize_questions
from rune_sdk._core.response_types import ListModelsResponse
from rune_sdk._core.transport import Request, ResponseT, prepare


def prepare_decide(
    config: Config,
    state: JSONContent,
    questions: Mapping[str, Question],
    model: str | None,
    extra_body: Mapping[str, JSONValue | None] | None,
    timeout: float | httpx2.Timeout | None,
    headers: Mapping[str, str] | None,
    response_type: type[ResponseT],
    images: Sequence[ImageInput] | None = None,
    thinking: bool | None = None,
) -> Request[ResponseT]:
    body: dict[str, Any] = {
        "state": state,
        "model": config.default_model if model is None else model,
        "questions": normalize_questions(questions),
    }
    if images is not None:
        body["images"] = list(images)
    if thinking is not None:
        body["thinking"] = thinking
    if extra_body is not None:
        body.update(extra_body)
    return prepare(config, "POST", DECISIONS_PATH, body, timeout, headers, response_type)


def prepare_models(config: Config, timeout: float | httpx2.Timeout | None, headers: Mapping[str, str] | None) -> Request[ListModelsResponse]:
    return prepare(config, "GET", MODELS_PATH, None, timeout, headers, ListModelsResponse)
