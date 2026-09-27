"""Synchronous API client."""

from collections.abc import Mapping, Sequence
from functools import cached_property
from types import TracebackType
from typing import overload

import httpx2
from typing_extensions import Self

from rune_sdk._core.client.sync.models import Models
from rune_sdk._core.config import Config
from rune_sdk._core.endpoints import prepare_decide
from rune_sdk._core.json_types import JSONContent, JSONValue
from rune_sdk._core.question_types import ImageInput, Question
from rune_sdk._core.response_types import DecisionsResponse
from rune_sdk._core.retry import RetryPolicy, build_tenacity
from rune_sdk._core.transport import Request, ResponseT, send


class RuneClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        retry: RetryPolicy | None = None,
        timeout: float | httpx2.Timeout | None = None,
        headers: Mapping[str, str] | None = None,
        transport: httpx2.BaseTransport | None = None,
        http_client: httpx2.Client | None = None,
        base_url: str | None = None,
    ) -> None:
        """Create an HTTP client for the [Surogate Rune API](https://github.com/invergent-ai/rune-sdk-python).

        Explicit options take precedence over environment variables; empty or whitespace-only
        environment values are ignored.

        !!! tip "Logging setup"
            The SDK logs to the `rune_sdk` logger; configure it through standard logging, or set
            `RUNE_LOG_LEVEL` (`debug`, `info`, ...) for a quick default. Secret headers are
            redacted from log output; request and response bodies are not.

        Args:
            api_key: Required API key; may be set via the `RUNE_API_KEY` environment variable.
                Leading and trailing whitespace is stripped. Empty keys, internal whitespace,
                control characters, and non-ASCII characters are rejected.
            model: Model name; may be set via the `RUNE_DEFAULT_MODEL` environment variable.
            retry: A `RetryPolicy` controlling retry behavior; see `RetryPolicy` for the available options and their
                defaults. Pass `RetryPolicy(max_retries=0)` to disable retries.
            timeout: Timeout for HTTP operations. Inherits `http_client.timeout` when supplied, otherwise the SDK default.
            headers: Additional request headers to set.
            transport: Optional custom HTTP transport, closed when this SDK client closes.
            http_client: Optional `httpx2.Client`; mutually exclusive with `transport`.
                Closed when this SDK client closes.
            base_url: API root; may be set via the `RUNE_BASE_URL` environment variable.

        Raises:
            RuneError: The API key is missing or invalid, or the timeout is invalid.
            ValueError: Both `transport` and `http_client` are supplied.

        Examples:
            ```python
            from rune_sdk import Choice, Noul, RuneClient

            with RuneClient() as client:
                result = client.decide(
                    state="I was charged twice. Please help.",
                    questions={
                        "billing": Noul(instructions="Is this about billing?"),
                        "tone": Choice(
                            instructions="What is the tone?",
                            criteria={"calm": None, "angry": None},
                        ),
                    },
                )
                assert 0 <= result.nouls["billing"].noul <= 1
                assert result.choices["tone"].choice in {"calm", "angry"}
            ```
        """
        if transport is not None and http_client is not None:
            raise ValueError("transport and http_client are mutually exclusive.")
        if timeout is None and http_client is not None:
            timeout = http_client.timeout
        self._config = Config.resolve(api_key, base_url, model, timeout, headers)
        self._retry = build_tenacity(retry)
        self._http_client = httpx2.Client(timeout=self._config.timeout, transport=transport) if http_client is None else http_client

    @cached_property
    def models(self) -> Models:
        """An accessor for the Models API resource.

        Examples:
            ```python
            with RuneClient() as client:
                models = client.models.list()
            ```
        """
        return Models(self._config, self._http_client, self._retry)

    @overload
    def decide(
        self,
        state: JSONContent,
        questions: Mapping[str, Question],
        *,
        model: str | None = None,
        retry: RetryPolicy | None = None,
        timeout: float | httpx2.Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, JSONValue | None] | None = None,
        images: Sequence[ImageInput] | None = None,
        thinking: bool | None = None,
        response_model: None = None,
    ) -> DecisionsResponse: ...

    @overload
    def decide(
        self,
        state: JSONContent,
        questions: Mapping[str, Question],
        *,
        model: str | None = None,
        retry: RetryPolicy | None = None,
        timeout: float | httpx2.Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, JSONValue | None] | None = None,
        images: Sequence[ImageInput] | None = None,
        thinking: bool | None = None,
        response_model: type[ResponseT],
    ) -> ResponseT: ...

    def decide(
        self,
        state: JSONContent,
        questions: Mapping[str, Question],
        *,
        model: str | None = None,
        retry: RetryPolicy | None = None,
        timeout: float | httpx2.Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, JSONValue | None] | None = None,
        images: Sequence[ImageInput] | None = None,
        thinking: bool | None = None,
        response_model: type[ResponseT] | None = None,
    ) -> DecisionsResponse | ResponseT:
        """Answer named questions about text or structured state.

        See [Decisions](https://github.com/invergent-ai/rune-sdk-python#readme) for details.

        Args:
            state: Text, a JSON object, or an array to evaluate.
                See [state](https://github.com/invergent-ai/rune-sdk-python#readme) for details.
            questions: Nonempty mapping of names to question objects or raw dictionaries.
            model: Model override; `None` inherits the client default.
            retry: An optional retry policy to override the client-level value for this call only.
            timeout: An optional timeout for http operations to override the client-level value for this call only, in seconds.
            extra_headers: Additional request headers to set.
            extra_body: Additional top-level request-body fields, shallow-merged over the body after
                `state`, `model`, and `questions` are set. Merging is last-write-wins: a key that
                collides with `state`, `model`, or `questions` overrides it, and object values are
                replaced rather than deep-merged.
            images: Optional image data URLs, as strings or objects with a `url` field.
            thinking: Request reasoning for uncertain text decisions. Cannot be combined with images.
            response_model: Optional Pydantic `BaseModel` type describing the JSON response body,
                including any nested answer models.

        Returns:
            An instance of `response_model`, or `DecisionsResponse` with answers keyed by question
            name and model and token usage details when no custom model is supplied.

        Raises:
            RuneError: Questions are empty or a score question has fewer than two criteria.
            RuneAPIError: The server returns an unsuccessful HTTP response after any retries.
            RuneAPIConnectionError: The request cannot connect or times out after any retries.
            RuneAPIResponseValidationError: The response body does not match the response model.

        Examples:
            Create questions with named arguments:

            ```python
            with RuneClient() as client:
                result = client.decide(
                    state="I was charged twice. Please help.",
                    questions={
                        "billing": Noul(instructions="Is this about billing?"),
                        "tone": Choice(
                            instructions="What is the tone?",
                            criteria={"calm": None, "angry": None},
                        ),
                    },
                )
                assert 0 <= result.nouls["billing"].noul <= 1
                assert result.choices["tone"].choice in {"calm", "angry"}
            ```

            Pass questions as dictionaries:

            ```python
            with RuneClient() as client:
                result = client.decide(
                    state={"message": "I was charged twice. Please help."},
                    questions={
                        "billing": {"type": "noul", "instructions": "Is this about billing?"},
                        "tone": {
                            "type": "choice",
                            "instructions": "What is the tone?",
                            "criteria": {"calm": None, "angry": None},
                        },
                    },
                )
                assert 0 <= result.nouls["billing"].noul <= 1
                assert result.choices["tone"].choice in {"calm", "angry"}
            ```
        """
        return self._request(
            prepare_decide(
                self._config,
                state,
                questions,
                model,
                extra_body,
                timeout,
                extra_headers,
                DecisionsResponse if response_model is None else response_model,
                images=images,
                thinking=thinking,
            ),
            retry=retry,
        )

    def _request(self, request: Request[ResponseT], *, retry: RetryPolicy | None = None) -> ResponseT:
        return send(self._http_client, self._retry, request, retry)

    def close(self) -> None:
        """Release network resources and close the underlying HTTP client, including a supplied one."""
        self._http_client.close()

    def __enter__(self) -> Self:
        """Enter the client context."""
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        """Close the client context."""
        self.close()
