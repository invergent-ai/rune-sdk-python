import httpx2
from tenacity import AsyncRetrying

from rune_sdk import RuneClient


def invalid_arguments(client: RuneClient) -> None:
    client.decide(None, {})  # E: Argument `None` is not assignable to parameter `state`
    RuneClient(api_key="test", retry=AsyncRetrying())  # E: Argument `AsyncRetrying` is not assignable to parameter `retry`
    RuneClient(api_key="test", http_client=httpx2.AsyncClient())  # E: Argument `AsyncClient` is not assignable to parameter `http_client`
    client.decide("x", {}, retry=AsyncRetrying())  # E: Argument `AsyncRetrying` is not assignable to parameter `retry`
    client.decide("x", {}, response_model=int)  # E: No matching overload
    client.decide("x", {}, response_model=object())  # E: No matching overload
