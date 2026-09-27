from typing import TypeVar

from pydantic import BaseModel
from typing_extensions import assert_type

from rune_sdk import (
    AsyncRuneClient,
    ChoiceAnswer,
    DecisionsResponse,
    Noul,
    NoulAnswer,
    RuneClient,
    ScoreAnswer,
)
from tests.test_pydantic_response_models import KnownResponse, TypedDecisionsResponse

PydanticT = TypeVar("PydanticT", bound=BaseModel)


def sync(client: RuneClient, response_model: type[KnownResponse] | None) -> None:
    questions = {"spam": Noul()}
    assert_type(client.decide("x", questions), DecisionsResponse)
    assert_type(client.decide("x", questions, response_model=None), DecisionsResponse)
    assert_type(client.decide("x", questions, response_model=DecisionsResponse), DecisionsResponse)
    assert_type(client.decide("x", questions, response_model=response_model), KnownResponse | DecisionsResponse)
    standalone = client.decide("x", questions, response_model=KnownResponse)
    assert_type(standalone, KnownResponse)
    assert_type(standalone.answers.spam, NoulAnswer)
    typed = client.decide("x", {"spam": Noul()}, response_model=TypedDecisionsResponse)
    assert_type(typed, TypedDecisionsResponse)
    assert_type(typed.spam, NoulAnswer)
    assert_type(typed.nouls, dict[str, NoulAnswer])
    assert_type(typed.choices, dict[str, ChoiceAnswer])
    assert_type(typed.scores, dict[str, ScoreAnswer])


async def asynchronous(client: AsyncRuneClient, response_model: type[KnownResponse] | None) -> None:
    questions = {"spam": Noul()}
    assert_type(await client.decide("x", questions), DecisionsResponse)
    assert_type(await client.decide("x", questions, response_model=None), DecisionsResponse)
    assert_type(await client.decide("x", questions, response_model=DecisionsResponse), DecisionsResponse)
    assert_type(await client.decide("x", questions, response_model=response_model), KnownResponse | DecisionsResponse)
    standalone = await client.decide("x", questions, response_model=KnownResponse)
    assert_type(standalone, KnownResponse)
    assert_type(standalone.answers.spam, NoulAnswer)
    typed = await client.decide("x", {"spam": Noul()}, response_model=TypedDecisionsResponse)
    assert_type(typed, TypedDecisionsResponse)
    assert_type(typed.spam, NoulAnswer)
    assert_type(typed.nouls, dict[str, NoulAnswer])
    assert_type(typed.choices, dict[str, ChoiceAnswer])
    assert_type(typed.scores, dict[str, ScoreAnswer])


def generic_sync(client: RuneClient, response_model: type[PydanticT]) -> PydanticT:
    return client.decide("x", {"spam": Noul()}, response_model=response_model)


async def generic_async(client: AsyncRuneClient, response_model: type[PydanticT]) -> PydanticT:
    return await client.decide("x", {"spam": Noul()}, response_model=response_model)
