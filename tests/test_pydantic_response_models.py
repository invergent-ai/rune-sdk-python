from typing import Literal

import httpx2
import pytest
from pydantic import BaseModel, ConfigDict

from rune_sdk import (
    AsyncRuneClient,
    DecisionsResponse,
    Noul,
    NoulAnswer,
    RuneAPIResponseValidationError,
    RuneBadRequestError,
)
from tests.conftest import ClientFactory
from tests.test_clients import RESULT


class KnownAnswers(BaseModel):
    spam: NoulAnswer


class KnownResponse(BaseModel):
    model: str
    answers: KnownAnswers


class ToneProbabilities(BaseModel):
    friendly: float
    hostile: float


class Tone(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    choice: Literal["friendly", "hostile"]
    probabilities: ToneProbabilities


class TypedDecisionsResponse(DecisionsResponse):
    spam: NoulAnswer
    tone: Tone
    missing: NoulAnswer | None = None


@pytest.mark.parametrize("extra_answer_fields", [{}, {"explanation": "spammy"}])
async def test_standalone_pydantic_response_model(clients: ClientFactory, extra_answer_fields: dict[str, str]) -> None:
    body = {**RESULT, "answers": {**RESULT["answers"], "spam": {**RESULT["answers"]["spam"], **extra_answer_fields}}}
    client = clients(lambda request: httpx2.Response(200, json=body))
    if isinstance(client, AsyncRuneClient):
        result = await client.decide("x", {"spam": Noul()}, response_model=KnownResponse)
    else:
        result = client.decide("x", {"spam": Noul()}, response_model=KnownResponse)
    assert type(result) is KnownResponse
    assert result.model == "rune-v3"
    assert result.answers.spam.noul == 0.98


@pytest.mark.parametrize("response_model", [None, DecisionsResponse])
async def test_explicit_default_response_model(clients: ClientFactory, response_model: type[DecisionsResponse] | None) -> None:
    client = clients(lambda request: httpx2.Response(200, json=RESULT, headers={"x-request-id": "req-default"}))
    if isinstance(client, AsyncRuneClient):
        result = await client.decide("x", {"spam": Noul()}, response_model=response_model)
    else:
        result = client.decide("x", {"spam": Noul()}, response_model=response_model)
    assert isinstance(result, DecisionsResponse)
    assert result.nouls["spam"].noul == 0.98
    assert result.request_id == "req-default"
    assert result.raw_http_response.json() == RESULT


async def test_pydantic_decide_response_subclass(clients: ClientFactory) -> None:
    body = {**RESULT, "answers": {**RESULT["answers"], "future": {"type": "future", "value": 1}}}
    client = clients(lambda request: httpx2.Response(200, json=body, headers={"x-request-id": "req-pydantic"}))
    if isinstance(client, AsyncRuneClient):
        result = await client.decide("x", {"spam": Noul()}, response_model=TypedDecisionsResponse)
    else:
        result = client.decide("x", {"spam": Noul()}, response_model=TypedDecisionsResponse)
    assert type(result) is TypedDecisionsResponse
    assert result.spam.noul == 0.98
    assert result.tone.choice == "friendly"
    assert result.tone.probabilities.friendly == 0.9
    assert result.missing is None
    assert result.nouls["spam"].noul == 0.98
    assert result.choices["tone"].choice == "friendly"
    assert result.scores["quality"].score == 1.7
    assert "future" not in result.answers
    assert result.request_id == "req-pydantic"
    assert result.raw_http_response.json() == body
    assert "_raw" not in result.model_dump()
    assert "_request_id" not in result.model_dump()


@pytest.mark.parametrize(
    "response_model,body,field_path",
    [
        (KnownResponse, {"model": "test", "answers": {"spam": {"type": "noul"}}}, "answers.spam.noul"),
        (
            TypedDecisionsResponse,
            {**RESULT, "answers": {**RESULT["answers"], "tone": {**RESULT["answers"]["tone"], "choice": "unknown"}}},
            "tone.choice",
        ),
    ],
)
async def test_pydantic_response_validation(
    clients: ClientFactory, response_model: type[BaseModel], body: dict[str, object], field_path: str
) -> None:
    client = clients(lambda request: httpx2.Response(200, json=body, headers={"x-request-id": "req-invalid"}))
    if isinstance(client, AsyncRuneClient):
        with pytest.raises(RuneAPIResponseValidationError) as caught:
            await client.decide("x", {"spam": Noul()}, response_model=response_model)
    else:
        with pytest.raises(RuneAPIResponseValidationError) as caught:
            client.decide("x", {"spam": Noul()}, response_model=response_model)
    assert caught.value.field_path == field_path
    assert caught.value.request_id == "req-invalid"
    assert caught.value.body == body


async def test_custom_response_preserves_api_errors(clients: ClientFactory) -> None:
    body = {"detail": "Invalid request"}
    client = clients(lambda request: httpx2.Response(400, json=body, headers={"x-request-id": "req-error"}))
    if isinstance(client, AsyncRuneClient):
        with pytest.raises(RuneBadRequestError) as caught:
            await client.decide("x", {"spam": Noul()}, response_model=KnownResponse)
    else:
        with pytest.raises(RuneBadRequestError) as caught:
            client.decide("x", {"spam": Noul()}, response_model=KnownResponse)
    assert caught.value.status == 400
    assert caught.value.body == body
    assert caught.value.request_id == "req-error"
