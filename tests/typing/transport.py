import httpx2
from tenacity import AsyncRetrying, Retrying
from typing_extensions import assert_type

from rune_sdk import (
    AsyncRuneClient,
    DecisionsResponse,
    ListModelsResponse,
    Noul,
    RuneClient,
)
from rune_sdk._core.config import Config
from rune_sdk._core.endpoints import prepare_decide, prepare_models
from rune_sdk._core.transport import Request, RequestState, send, send_async


def sync(config: Config, client: RuneClient, http_client: httpx2.Client, retry: Retrying, response: httpx2.Response) -> None:
    models = prepare_models(config, None, None)
    decide = prepare_decide(config, "x", {"q": Noul(instructions="?")}, None, None, None, None, DecisionsResponse)
    assert_type(models, Request[ListModelsResponse])
    assert_type(decide, Request[DecisionsResponse])
    assert_type(RequestState(models).parse(response), ListModelsResponse)
    assert_type(RequestState(decide).parse(response), DecisionsResponse)
    assert_type(send(http_client, retry, models), ListModelsResponse)
    assert_type(send(http_client, retry, decide), DecisionsResponse)
    assert_type(client._request(models), ListModelsResponse)
    assert_type(client._request(decide), DecisionsResponse)


async def asynchronous(config: Config, client: AsyncRuneClient, http_client: httpx2.AsyncClient, retry: AsyncRetrying) -> None:
    models = prepare_models(config, None, None)
    decide = prepare_decide(config, "x", {"q": Noul(instructions="?")}, None, None, None, None, DecisionsResponse)
    assert_type(await send_async(http_client, retry, models), ListModelsResponse)
    assert_type(await send_async(http_client, retry, decide), DecisionsResponse)
    assert_type(await client._request(models), ListModelsResponse)
    assert_type(await client._request(decide), DecisionsResponse)
