"""Internal protocol and logging constants."""

MAX_ERROR_BODY_LENGTH = 200

DECISIONS_PATH = "/v1/decisions"
MODELS_PATH = "/v1/models"
SDK_NAME = "rune-sdk"
LOGGER_NAME = "rune_sdk"
JSON_CONTENT_TYPE = "application/json"

AUTHORIZATION_HEADER = "Authorization"
ACCEPT_HEADER = "Accept"
CONTENT_TYPE_HEADER = "Content-Type"
USER_AGENT_HEADER = "User-Agent"
SDK_HEADER = "X-Rune-SDK"
RUNTIME_HEADER = "X-Rune-Runtime"
RETRY_COUNT_HEADER = "X-Rune-Retry-Count"
REQUEST_ID_HEADER = "x-request-id"
RETRY_AFTER_HEADER = "retry-after"
RETRY_AFTER_MS_HEADER = "retry-after-ms"
SECRET_HEADERS = frozenset({"authorization", "proxy-authorization", "x-api-key", "api-key", "cookie", "set-cookie"})
