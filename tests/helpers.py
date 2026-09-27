from collections.abc import Mapping

import httpx2
from typing_extensions import override

from rune_sdk import (
    AsyncRuneClient,
    DecisionsResponse,
    JSONContent,
    JSONValue,
    ModelMetadata,
    Questions,
    RetryPolicy,
    RuneClient,
)


class TrackingTransport(httpx2.MockTransport):
    close_calls = 0
    aclose_calls = 0

    @override
    def close(self) -> None:
        self.close_calls += 1

    @override
    async def aclose(self) -> None:
        self.aclose_calls += 1


async def models(
    client: RuneClient | AsyncRuneClient,
    *,
    retry: RetryPolicy | None = None,
    timeout: float | httpx2.Timeout | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> tuple[ModelMetadata, ...]:
    if isinstance(client, AsyncRuneClient):
        return (await client.models.list(retry=retry, timeout=timeout, extra_headers=extra_headers)).models
    else:
        return client.models.list(retry=retry, timeout=timeout, extra_headers=extra_headers).models


async def decide(
    client: RuneClient | AsyncRuneClient,
    *,
    state: JSONContent,
    questions: Questions,
    model: str | None = None,
    extra_body: Mapping[str, JSONValue | None] | None = None,
    retry: RetryPolicy | None = None,
    timeout: float | httpx2.Timeout | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> DecisionsResponse:
    if isinstance(client, AsyncRuneClient):
        return await client.decide(
            state, questions, model=model, extra_body=extra_body, retry=retry, timeout=timeout, extra_headers=extra_headers
        )
    else:
        return client.decide(
            state, questions, model=model, extra_body=extra_body, retry=retry, timeout=timeout, extra_headers=extra_headers
        )
