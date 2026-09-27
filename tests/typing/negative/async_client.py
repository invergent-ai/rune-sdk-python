import httpx2
from tenacity import Retrying

from rune_sdk import AsyncRuneClient


async def invalid_arguments(client: AsyncRuneClient) -> None:
    await client.decide(None, {})  # E: Argument `None` is not assignable to parameter `state`
    AsyncRuneClient(api_key="test", retry=Retrying())  # E: Argument `Retrying` is not assignable to parameter `retry`
    AsyncRuneClient(api_key="test", http_client=httpx2.Client())  # E: Argument `Client` is not assignable to parameter `http_client`
    await client.decide("x", {}, retry=Retrying())  # E: Argument `Retrying` is not assignable to parameter `retry`
    await client.decide("x", {}, response_model=int)  # E: No matching overload
    await client.decide("x", {}, response_model=object())  # E: No matching overload
