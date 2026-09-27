"""Model resource for the synchronous client, exposed as `RuneClient.models`."""

from collections.abc import Mapping

import httpx2
from tenacity import Retrying

from rune_sdk._core.config import Config
from rune_sdk._core.endpoints import prepare_models
from rune_sdk._core.response_types import ListModelsResponse
from rune_sdk._core.retry import RetryPolicy
from rune_sdk._core.transport import send


class Models:
    """Access to the models available to the account, reached through `RuneClient.models`."""

    def __init__(self, config: Config, http_client: httpx2.Client, retry: Retrying) -> None:
        self._config = config
        self._http_client = http_client
        self._retry = retry

    def list(
        self,
        *,
        retry: RetryPolicy | None = None,
        timeout: float | httpx2.Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> ListModelsResponse:
        """List the models available to the account.

        Args:
            retry: An optional retry policy to override the client-level value for this call only.
            timeout: Per-operation timeout override; `None` inherits the client setting.
            extra_headers: Overrides for additional request headers; authentication, SDK identification,
                and `Accept` remain protected.

        Returns:
            A `ListModelsResponse` whose `models` holds each model's name, description,
            and release date.

        Raises:
            RuneAPIError: The server returns an unsuccessful HTTP response after any retries.
            RuneAPIConnectionError: The request cannot connect or times out after any retries.

        Examples:
            ```python
            from rune_sdk import RuneClient

            with RuneClient() as client:
                models = client.models.list()
            ```
        """
        return send(self._http_client, self._retry, prepare_models(self._config, timeout, extra_headers), retry)
