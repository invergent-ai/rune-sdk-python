import asyncio
import logging
from importlib.metadata import version
from typing import Any, cast

import httpx2
import pytest
from pydantic import ValidationError
from pydantic_core import from_json, to_json
from typing_extensions import assert_type

from rune_sdk import (
    AsyncRuneClient,
    Choice,
    ChoiceAnswer,
    JSONValue,
    ModelMetadata,
    Noul,
    NoulAnswer,
    QuestionModel,
    Questions,
    RuneAPIConnectionError,
    RuneAPIError,
    RuneAPIResponseValidationError,
    RuneAPITimeoutError,
    RuneAuthenticationError,
    RuneBadRequestError,
    RuneClient,
    RuneError,
    RuneInternalServerError,
    RuneNotFoundError,
    RunePermissionDeniedError,
    RuneRateLimitError,
    RuneUnprocessableEntityError,
    Score,
    ScoreAnswer,
    Usage,
)
from tests.conftest import ClientFactory
from tests.helpers import TrackingTransport, decide, models

RESULT = {
    "model": "rune-v3",
    "usage": {"input_tokens": 12, "output_tokens": 3},
    "answers": {
        "spam": {"type": "noul", "noul": 0.98},
        "tone": {"type": "choice", "choice": "friendly", "confidence": 0.9, "probabilities": {"friendly": 0.9, "hostile": 0.1}},
        "quality": {
            "type": "score",
            "score": 1.7,
            "confidence": 0.8,
            "legend": {"0": "bad", "1": "ok", "2": "great"},
            "probabilities": {"0": 0.1, "1": 0.1, "2": 0.8},
        },
    },
}
CARD = {"id": "rune-v3", "object": "model", "created": 0, "owned_by": "test"}


@pytest.mark.parametrize("question_form", ["dataclass", "raw", "mixed"])
async def test_round_trip(clients: ClientFactory, question_form: str) -> None:
    criteria: list[str | dict[str, JSONValue | None] | list[JSONValue | None]] = ["bad", "ok", "great"]
    raw: dict[str, QuestionModel] = {
        "spam": {"type": "noul", "instructions": "Spam?", "criteria": {"true": "true", "false": "false"}},
        "tone": {"type": "choice", "instructions": "Tone?", "criteria": {"friendly": "friendly", "hostile": "hostile"}},
        "quality": {"type": "score", "instructions": "Quality?", "criteria": criteria},
    }
    questions: Questions
    if question_form == "raw":
        questions = raw
    else:
        questions = {
            "spam": Noul(instructions="Spam?") if question_form == "dataclass" else raw["spam"],
            "tone": Choice(instructions="Tone?", criteria={"friendly": None, "hostile": None}),
            "quality": Score(instructions="Quality?", criteria=criteria),
        }
    expected: dict[str, JSONValue | None] = {
        "state": {"document": "Hello 🌍"},
        "model": "rune-v3",
        "questions": {
            "spam": {"type": "noul", "instructions": "Spam?", "criteria": {"true": "true", "false": "false"}},
            "tone": {"type": "choice", "instructions": "Tone?", "criteria": {"friendly": "friendly", "hostile": "hostile"}},
            "quality": {"type": "score", "instructions": "Quality?", "criteria": ["bad", "ok", "great"]},
        },
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://rune.surogate.ai/v1/decisions"
        assert from_json(request.content) == expected
        assert request.headers["content-type"] == "application/json"
        return httpx2.Response(200, content=to_json(RESULT))

    result = await decide(
        clients(handler),
        state={"document": "Hello 🌍"},
        questions=questions,
    )
    assert "nouls" not in result.__dict__
    assert "choices" not in result.__dict__
    assert "scores" not in result.__dict__
    assert_type(result.nouls, dict[str, NoulAnswer])
    assert_type(result.choices, dict[str, ChoiceAnswer])
    assert_type(result.scores, dict[str, ScoreAnswer])
    assert result.nouls is result.nouls
    assert result.choices is result.choices
    assert result.scores is result.scores
    assert result.model == "rune-v3"
    assert result.usage == Usage(input_tokens=12, output_tokens=3)
    assert set(result.nouls) == {"spam"}
    assert set(result.choices) == {"tone"}
    assert set(result.scores) == {"quality"}
    assert result.nouls["spam"].noul == 0.98
    assert result.choices["tone"].choice == "friendly"
    assert result.choices["tone"].confidence == 0.9
    assert result.choices["tone"].probabilities == {"friendly": 0.9, "hostile": 0.1}
    assert result.scores["quality"].score == 1.7
    assert result.scores["quality"].confidence == 0.8
    assert result.scores["quality"].legend == {0: "bad", 1: "ok", 2: "great"}
    assert result.scores["quality"].probabilities == {0: 0.1, 1: 0.1, 2: 0.8}
    assert result.answers["quality"] is result.scores["quality"]
    assert result.answers["spam"] is result.nouls["spam"]
    assert result.answers["tone"] is result.choices["tone"]
    assert set(result.answers) == {"spam", "tone", "quality"}
    with pytest.raises(ValidationError):
        cast(Any, result).model = "other"


async def test_extra_body_shallow_override(clients: ClientFactory) -> None:
    expected = {
        "state": "hi",
        "model": "override-model",
        "questions": {"q": {"type": "noul", "instructions": "?", "criteria": {"true": "true", "false": "false"}}},
        "beam_width": 4,
        "nullable": None,
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert from_json(request.content) == expected
        return httpx2.Response(200, content=to_json(RESULT))

    await decide(
        clients(handler),
        state="hi",
        questions={"q": {"type": "noul", "instructions": "?"}},
        model="call-model",
        extra_body={"model": "override-model", "beam_width": 4, "nullable": None},
    )


async def test_unserializable_request_body_raises(clients: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("An unencodable request body reached the network")

    with pytest.raises(RuneError, match="could not be encoded as JSON"):
        await decide(
            clients(handler),
            state="x",
            questions={"q": {"type": "noul", "instructions": "?"}},
            extra_body=cast(Any, {"bad": object()}),
        )


async def test_raw_question_passthrough(clients: ClientFactory) -> None:
    # Explicit escape hatch for fields introduced by the API before this SDK models them.
    questions = cast(
        Questions,
        {
            "q": {"type": "noul", "instructions": "Spam?", "weight": 3, "nested": {"k": None}},
            "choice": {"type": "choice", "criteria": {"a": None}, "weight": 2},
            "score": {"type": "score", "criteria": ["bad", "good"], "weight": 1},
        },
    )
    expected = {"state": "hi", "model": "rune-v3", "questions": {
        "q": {"type": "noul", "instructions": "Spam?", "weight": 3, "nested": {"k": None}, "criteria": {"true": "true", "false": "false"}},
        "choice": {"type": "choice", "instructions": "", "criteria": {"a": "a"}, "weight": 2},
        "score": {"type": "score", "instructions": "", "criteria": ["bad", "good"], "weight": 1},
    }}

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert from_json(request.content) == expected
        return httpx2.Response(200, content=to_json(RESULT))

    await decide(clients(handler), state="hi", questions=questions)


# Raw dictionary questions are passed through untouched: the SDK leaves their schema validation to
# the API. (Typed `Noul`/`Choice`/`Score` objects instead validate eagerly on construction.)
@pytest.mark.parametrize(
    "question",
    [
        {"type": "noul", "instructions": 1},
        {"type": "choice", "criteria": ["invalid", "shape"]},
    ],
)
async def test_question_schema_validation_is_left_to_api(clients: ClientFactory, question: Any) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        actual = from_json(request.content)["questions"]["q"]
        for key, value in question.items():
            assert actual[key] == value
        return httpx2.Response(422, json={"detail": "Invalid question"})

    with pytest.raises(RuneUnprocessableEntityError, match="Invalid question"):
        await decide(clients(handler), state="x", questions={"q": question})


async def test_rich_descriptions(clients: ClientFactory) -> None:
    criteria = {"summary": "duplicated", "examples": ["charged twice"]}
    expected = {
        "state": "a ticket",
        "model": "custom",
        "questions": {
            "duplicate": {"type": "noul", "instructions": {"question": "Duplicate?"}, "criteria": {"true": criteria, "false": "false"}},
            "team": {"type": "choice", "instructions": "Team?", "criteria": {"billing": criteria, "other": "other"}},
            "risk": {"type": "score", "instructions": "Risk?", "criteria": [criteria, "other"]},
        },
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert from_json(request.content) == expected
        return httpx2.Response(
            200,
            json={
                "model": "custom",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "answers": {
                    "risk": {"type": "score", "score": 0, "confidence": 1, "legend": {"0": criteria}, "probabilities": {"0": 1}},
                },
            },
        )

    result = await decide(
        clients(handler),
        state="a ticket",
        model="custom",
        questions={
            "duplicate": {
                "type": "noul",
                "instructions": {"question": "Duplicate?"},
                "criteria": {"true": {"summary": "duplicated", "examples": ["charged twice"]}},
            },
            "team": Choice(
                instructions="Team?",
                criteria={"billing": {"summary": "duplicated", "examples": ["charged twice"]}, "other": None},
            ),
            "risk": Score(instructions="Risk?", criteria=[{"summary": "duplicated", "examples": ["charged twice"]}, "other"]),
        },
    )
    assert result.scores["risk"].legend[0] == criteria


async def test_models_shape(clients: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/models"
        assert request.content == b""
        return httpx2.Response(200, content=to_json({"data": [CARD]}))

    assert await models(clients(handler)) == (ModelMetadata(**CARD),)


async def test_models_ignore_unknown_fields(clients: ClientFactory) -> None:
    card = {**CARD, "context_window": 128000, "pricing": None}
    client = clients(lambda request: httpx2.Response(200, content=to_json({"data": [card]})))
    response = await client.models.list() if isinstance(client, AsyncRuneClient) else client.models.list()
    [model] = response.models
    assert model.name == "rune-v3"
    # Unmodeled fields are dropped from the card but remain available via the raw response.
    assert response.raw_http_response.json()["data"][0]["context_window"] == 128000


@pytest.mark.parametrize("body", [None, {}, {"data": "bad"}, {"data": [{"name": "x"}]}])
async def test_invalid_models_response(clients: ClientFactory, body: object) -> None:
    with pytest.raises(RuneAPIResponseValidationError):
        await models(clients(lambda request: httpx2.Response(200, json=body)))


@pytest.mark.parametrize(
    "questions,match",
    [
        ({}, "At least one question"),
        ({"rating": Score(instructions="?", criteria=[])}, '"rating" has no criteria'),
    ],
)
async def test_validation_before_network(clients: ClientFactory, questions: Any, match: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("Invalid questions reached the network")

    with pytest.raises(RuneError, match=match):
        await decide(clients(handler), state="x", questions=questions)


@pytest.mark.parametrize(
    "status,error",
    [
        (400, RuneBadRequestError),
        (401, RuneAuthenticationError),
        (403, RunePermissionDeniedError),
        (404, RuneNotFoundError),
        (422, RuneUnprocessableEntityError),
        (429, RuneRateLimitError),
        (500, RuneInternalServerError),
        (503, RuneInternalServerError),
        (408, RuneAPIError),
        (409, RuneAPIError),
        (302, RuneAPIError),
    ],
)
async def test_error_mapping(clients: ClientFactory, status: int, error: type[RuneAPIError]) -> None:
    body = {"detail": {"message": "Server explanation"}}
    with pytest.raises(error) as caught:
        await models(
            clients(lambda request: httpx2.Response(status, json=body, headers={"x-request-id": "req_123", "retry-after-ms": "125"}))
        )
    assert type(caught.value) is error
    assert caught.value.status == status
    assert caught.value.body == body
    assert caught.value.request_id == "req_123"
    assert str(caught.value) == f"GET https://rune.surogate.ai/v1/models: {status} Server explanation (request_id=req_123)"
    assert caught.value.headers["retry-after-ms"] == "125"
    if isinstance(caught.value, RuneRateLimitError):
        assert caught.value.retry_after_ms == 125


@pytest.mark.parametrize(
    "body,message",
    [
        ({"error": "error", "message": "message", "detail": "detail"}, "error"),
        ({"error": {"message": "nested error"}, "message": "message"}, "nested error"),
        ({"message": "message", "detail": "detail"}, "message"),
        ({"detail": "detail"}, "detail"),
        ({"detail": {"message": "nested detail"}}, "nested detail"),
        (
            {"detail": [{"loc": ["body", "questions", "q", "score", "criteria", 0], "msg": "Invalid"}, {"msg": "Missing"}, {}]},
            "questions.q.score.criteria.0: Invalid; Missing",
        ),
        ("plain text", "plain text"),
        ({"unexpected": True}, '{"unexpected":true}'),
    ],
)
async def test_error_messages(clients: ClientFactory, body: object, message: str) -> None:
    content = body.encode() if isinstance(body, str) else to_json(body)
    with pytest.raises(RuneAPIError, match="400") as caught:
        await models(clients(lambda request: httpx2.Response(400, content=content)))
    assert str(caught.value) == f"GET https://rune.surogate.ai/v1/models: 400 {message}"


@pytest.mark.parametrize(
    "transport_error,sdk_error",
    [
        (httpx2.LocalProtocolError, RuneAPIConnectionError),
        (httpx2.ConnectError, RuneAPIConnectionError),
        (httpx2.ReadError, RuneAPIConnectionError),
        (httpx2.RemoteProtocolError, RuneAPIConnectionError),
        (httpx2.ConnectTimeout, RuneAPITimeoutError),
        (httpx2.ReadTimeout, RuneAPITimeoutError),
    ],
)
async def test_transport_errors(clients: ClientFactory, transport_error: type[httpx2.RequestError], sdk_error: type[RuneError]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise transport_error("failed", request=request)

    with pytest.raises(sdk_error) as caught:
        await models(clients(handler), timeout=1.25)
    assert type(caught.value) is sdk_error
    assert isinstance(caught.value.__cause__, transport_error)
    assert str(caught.value.__cause__) == "failed"
    assert caught.value.__context__ is None
    if isinstance(caught.value, RuneAPITimeoutError):
        assert caught.value.timeout == 1.25


@pytest.mark.parametrize("timeout", [None, 2.0, httpx2.Timeout(3.0, read=9.0), httpx2.Timeout(None)])
async def test_decide_timeout_override(clients: ClientFactory, timeout: float | httpx2.Timeout | None) -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=RESULT)

    client = clients(handler, timeout=7.0)
    await decide(client, state="hello", questions={"q": Noul(instructions="?")}, timeout=timeout)
    await decide(client, state="hello", questions={"q": Noul(instructions="?")})
    expected = httpx2.Timeout(7.0 if timeout is None else timeout).as_dict()
    assert requests[0].extensions["timeout"] == expected
    assert requests[1].extensions["timeout"] == httpx2.Timeout(7.0).as_dict()


async def test_headers_timeout_and_logging(clients: ClientFactory, caplog: pytest.LogCaptureFixture) -> None:
    protected = {
        "authorization": "injected-secret",
        "accept": "text/plain",
        "user-agent": "wrong",
        "x-rune-sdk": "wrong",
        "x-rune-runtime": "wrong",
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "https://example.test/prefix/v1/decisions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.headers["accept"] == "application/json"
        assert request.headers["user-agent"] == f"rune-sdk/{version('rune-sdk')}"
        assert request.headers["x-rune-sdk"] == request.headers["user-agent"]
        assert request.headers["x-rune-runtime"].startswith("python/")
        assert "x-rune-retry-count" not in request.headers
        assert request.headers["x-team"] == "call"
        assert request.headers["x-default"] == "kept"
        assert request.headers["content-type"] == "application/json"
        assert request.extensions["timeout"] == {"connect": 2.0, "read": 2.0, "write": 2.0, "pool": 2.0}
        return httpx2.Response(200, json=RESULT, headers={"set-cookie": "response-secret", "x-request-id": "req_log"})

    with caplog.at_level(logging.DEBUG, logger="rune_sdk"):
        client = clients(
            handler,
            base_url="https://example.test/prefix///",
            timeout=7,
            headers={**protected, "X-Team": "default", "X-Default": "kept", "X-API-Key": "key-secret", "cookie": "cookie-secret"},
        )
        await decide(
            client,
            state="hello",
            questions={"q": {"type": "noul", "instructions": "?"}},
            timeout=2.0,
            extra_headers={**protected, "x-team": "call", "x-rune-retry-count": "99", "content-type": "wrong"},
        )
    for secret in ("test-key", "injected-secret", "key-secret", "cookie-secret", "response-secret"):
        assert secret not in caplog.text
    assert "req_log" in caplog.text
    assert "hello" in caplog.text


async def test_http_client_settings(clients: ClientFactory) -> None:
    requests: list[httpx2.Request] = []

    async def async_hook(request: httpx2.Request) -> None:
        requests.append(request)

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url).startswith("https://rune.surogate.ai/v1/")
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.headers["accept"] == "application/json"
        assert request.headers["user-agent"].startswith("rune-sdk/")
        assert request.headers["x-rune-sdk"] == request.headers["user-agent"]
        assert request.headers["x-rune-runtime"].startswith("python/")
        assert request.headers["x-http-default"] == "kept"
        assert request.headers["x-sdk-default"] == "sdk"
        assert request.headers["x-call"] == "call"
        if request.method == "POST":
            assert request.headers["content-type"] == "application/json"
        return httpx2.Response(200, json=RESULT if request.method == "POST" else {"data": []})

    headers = {
        "authorization": "wrong",
        "accept": "text/plain",
        "content-type": "text/plain",
        "user-agent": "wrong",
        "x-rune-sdk": "wrong",
        "x-rune-runtime": "wrong",
        "x-http-default": "kept",
        "x-sdk-default": "http",
        "x-call": "http",
    }
    http_client = (
        httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler),
            event_hooks={"request": [async_hook]},
            headers=headers,
            auth=("wrong", "credentials"),
            base_url="https://wrong.test",
        )
        if clients.async_mode
        else httpx2.Client(
            transport=httpx2.MockTransport(handler),
            event_hooks={"request": [requests.append]},
            headers=headers,
            auth=("wrong", "credentials"),
            base_url="https://wrong.test",
        )
    )
    original_headers = httpx2.Headers(http_client.headers)
    original_base_url = http_client.base_url
    client = clients(handler, http_client=http_client, headers={"x-sdk-default": "sdk", "x-call": "sdk"})
    assert client._http_client is http_client
    assert await models(client, extra_headers={"x-call": "call"}) == ()
    await decide(client, state="x", questions={"q": Noul(instructions="?")}, extra_headers={"x-call": "call"})
    assert [request.method for request in requests] == ["GET", "POST"]
    assert http_client.headers == original_headers
    assert http_client.base_url == original_base_url


@pytest.mark.parametrize("use_context", [False, True])
@pytest.mark.parametrize("supply_http_client", [False, True])
async def test_supplied_network_resources_closed(clients: ClientFactory, use_context: bool, supply_http_client: bool) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "https://rune.surogate.ai/v1/models"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx2.Response(200, json={"data": []})

    transport = TrackingTransport(handler)
    if supply_http_client:
        http_client = httpx2.AsyncClient(transport=transport) if clients.async_mode else httpx2.Client(transport=transport)
        client = clients(handler, http_client=http_client)
        assert client._http_client is http_client
    else:
        client = clients(handler, transport=transport)
    assert await models(client) == ()
    if isinstance(client, AsyncRuneClient):
        if use_context:
            async with client:
                assert (await client.models.list()).models == ()
        else:
            await client.aclose()
        await client.aclose()
        assert transport.aclose_calls == 1
        assert transport.close_calls == 0
    else:
        if use_context:
            with client:
                assert client.models.list().models == ()
        else:
            client.close()
        client.close()
        assert transport.close_calls == 1
        assert transport.aclose_calls == 0
    assert client._http_client.is_closed
    with pytest.raises(RuntimeError, match="closed"):
        await models(client)


async def test_owned_http_client_closed() -> None:
    with RuneClient(api_key="test") as client:
        assert not client._http_client.is_closed
        assert client._http_client.timeout == httpx2.Timeout(120.0)
    assert client._http_client.is_closed
    async with AsyncRuneClient(api_key="test") as async_client:
        assert not async_client._http_client.is_closed
        assert async_client._http_client.timeout == httpx2.Timeout(120.0)
    assert async_client._http_client.is_closed


@pytest.mark.parametrize("kind", [ValueError, asyncio.CancelledError])
async def test_exceptional_context_closes_http_client(clients: ClientFactory, kind: type[BaseException]) -> None:
    failure = kind("original failure")

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise failure

    transport = TrackingTransport(handler)
    http_client = httpx2.AsyncClient(transport=transport) if clients.async_mode else httpx2.Client(transport=transport)
    client = clients(handler, http_client=http_client)
    assert client._http_client is http_client
    with pytest.raises(kind) as caught:
        if isinstance(client, AsyncRuneClient):
            async with client:
                await client.models.list()
        else:
            with client:
                client.models.list()
    assert caught.value is failure
    assert transport.aclose_calls == int(clients.async_mode)
    assert transport.close_calls == int(not clients.async_mode)
    assert client._http_client.is_closed


async def test_task_cancellation_closes_context() -> None:
    started = asyncio.Event()

    async def handler(request: httpx2.Request) -> httpx2.Response:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("Cancelled request returned")

    transport = TrackingTransport(handler)
    client = AsyncRuneClient(api_key="test", http_client=httpx2.AsyncClient(transport=transport))

    async def run() -> None:
        async with client:
            await client.decide("x", {"q": Noul(instructions="?")})

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert transport.aclose_calls == 1
    assert client._http_client.is_closed


async def test_cancellation_propagates() -> None:
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        raise asyncio.CancelledError

    async with AsyncRuneClient(api_key="test", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))) as client:
        with pytest.raises(asyncio.CancelledError):
            await client.models.list()
    assert attempts == 1
