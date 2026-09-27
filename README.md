# Invergent Rune Python SDK

Python clients for the Rune decisions API, maintained by Invergent. Requires Python 3.10+.

## Install

Install from this repository until a registry release is available:

```bash
python -m pip install "rune-sdk @ git+https://github.com/invergent-ai/rune-sdk-python.git"
```

The Python package is `rune_sdk`. Set `RUNE_API_KEY` in your environment.

## Quickstart

```python
from rune_sdk import Choice, Noul, RuneClient, Score

with RuneClient() as client:
    result = client.decide(
        state={"message": "I was charged twice. Please help."},
        questions={
            "category": Choice(
                instructions="What is this ticket about?",
                criteria={"billing": None, "technical": None, "other": None},
            ),
            "refund": Noul(instructions="Does the customer request a refund?"),
            "urgency": Score(
                instructions="How urgent is this request?",
                criteria=["Low", "Medium", "High"],
            ),
        },
    )

print(result.choices["category"].choice)
print(result.nouls["refund"].noul)
print(result.scores["urgency"].score)
```

The default API root is `https://rune.surogate.ai`, the model is `rune-v3`, and
`decide()` sends `POST /v1/decisions`. Authentication uses `Authorization: Bearer`.
State can be text, a JSON object or an array. Choice and score questions need 2–255
options. Missing choice descriptions use their labels; a Noul supplies `true` and
`false` descriptions automatically. Instructions omitted from helpers become empty
strings. Nested JSON values are preserved, and request inputs are not mutated.

## Async

```python
import asyncio
from rune_sdk import AsyncRuneClient, Noul

async def main():
    async with AsyncRuneClient() as client:
        result = await client.decide("The customer is happy.", {"happy": Noul(instructions="Is the customer happy?")})
        print(result.nouls["happy"].noul)

asyncio.run(main())
```

## Images and thinking

Pass image data URLs through `images`, for example
`client.decide(state, questions, images=["data:image/png;base64,..."])`.
Objects of the form `{"url": "data:image/png;base64,..."}` are also accepted.
Encode local image bytes as base64 before calling; remote image URLs are not supported.

<!-- skip: next -->
```python
import base64
from pathlib import Path
from rune_sdk import Noul, RuneClient

image = base64.b64encode(Path("photo.png").read_bytes()).decode("ascii")
with RuneClient() as client:
    result = client.decide(
        state="Inspect the attached photo.",
        questions={"damaged": Noul(instructions="Is the package visibly damaged?")},
        images=[f"data:image/png;base64,{image}"],
    )
print(result.nouls["damaged"].noul)
```

For uncertain text decisions, pass `thinking=True`. An answer that used reasoning
includes `answer.thinking.tokens`, `answer.thinking.closed` and its typed
`answer.thinking.onepass` result. `result.usage.reasoning_tokens` reports reasoning usage.
The current API does not support combining images and thinking in one request.

```python
with RuneClient() as client:
    result = client.decide(
        state="The package arrived late, but the customer says they can still use it.",
        questions={"refund": Noul(instructions="Does the customer want a refund?")},
        thinking=True,
    )

answer = result.nouls["refund"]
if answer.thinking is not None:
    print(answer.thinking.tokens, answer.thinking.onepass)
```

Thinking is opt-in and may take longer. Answers that do not need reasoning omit the
`thinking` metadata. Both options also work with `AsyncRuneClient`.

## Models, configuration and errors

`client.models.list().data` contains model objects with `id`, `object`, `created` and
`owned_by`. Use a model's `id` in the client's `model` option or a per-call override.

The constructor accepts `api_key`, `base_url`, `model`, `timeout` (seconds) and
`retry=RetryPolicy(...)`. The corresponding environment variables are `RUNE_API_KEY`,
`RUNE_BASE_URL`, `RUNE_DEFAULT_MODEL` and `RUNE_LOG_LEVEL`. Explicit options take precedence.
The default HTTP timeout is 120 seconds. Each decision call also supports `timeout`,
`retry`, `extra_headers`, `extra_body` and a custom Pydantic `response_model`.

The SDK retries eligible connection failures, timeouts, HTTP 408, 429 and 5xx responses
up to twice, honoring `Retry-After`. Use `RetryPolicy(max_retries=0)` to disable retries.
The default retry budget is 30 seconds; it stops additional attempts when exhausted,
without shortening a running request's HTTP timeout. Catch `RuneAPIError` for HTTP errors
or its subclasses such as `RuneAuthenticationError` and `RuneRateLimitError`.

Response models preserve typed answers and expose the original response through
`raw_http_response`. Debug logging includes request and response bodies; enable it only
when appropriate for your data. Known credential headers are redacted.

## Development

```bash
uv sync --dev
uv run pytest -m "not integration"
uv run ruff check .
uv build
```

Live tests are opt-in through `RUNE_API_KEY`; `uv run pytest tests/test_integration.py`
exercises the public API. Do not put API keys in source files.

This is a fork of the MIT-licensed TypeSafe Python SDK. See [UPSTREAM.md](UPSTREAM.md)
for attribution and [LICENSE](LICENSE) for the original license.
