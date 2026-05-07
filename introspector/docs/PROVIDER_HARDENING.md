# Provider Hardening

Provider failures are classified through `ProviderCallError` and `ProviderErrorKind`. Auth, rate limit, timeout, network, server, bad request, not found, unprocessable and bad response failures can be represented as structured degraded analysis artifacts.

`/llm/status` is local and fast: it reports configuration and storage state. `/llm/probe` is a live provider check and may perform an external provider call.

LLM artifacts can include requested model, provider model used, structured-output fallback and retryability metadata.
