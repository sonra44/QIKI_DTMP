import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class OpenAIResponsesError(RuntimeError):
    pass


def _http_post_json(
    *,
    url: str,
    headers: Dict[str, str],
    body: Dict[str, Any],
    timeout_s: float,
) -> Dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(body).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        payload = response.read().decode("utf-8")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise OpenAIResponsesError(f"Invalid JSON from OpenAI: {exc}") from exc


def _extract_output_text(response: Dict[str, Any]) -> str:
    output = response.get("output")
    if not isinstance(output, list):
        raise OpenAIResponsesError("OpenAI response missing 'output' array")

    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") != "output_text":
                continue
            text = chunk.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise OpenAIResponsesError("OpenAI response missing output_text content")


@dataclass(frozen=True)
class OpenAIResponsesClient:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_s: float = 20.0
    max_output_tokens: int = 500
    max_retries: int = 3
    temperature: float = 0.2

    def create_response_json_schema(
        self,
        *,
        system_prompt: str,
        user_json: Dict[str, Any],
        json_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/responses"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        body: Dict[str, Any] = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_json, ensure_ascii=False)},
            ],
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "text": {
                "format": {
                    "type": "json_schema",
                    "strict": True,
                    "schema": json_schema,
                }
            },
        }

        attempt = 0
        last_error: Optional[BaseException] = None
        while attempt <= self.max_retries:
            try:
                return _http_post_json(
                    url=url,
                    headers=headers,
                    body=body,
                    timeout_s=self.timeout_s,
                )
            except urllib.error.HTTPError as exc:
                last_error = exc
                status = getattr(exc, "code", None)
                if status in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    backoff_s = (0.5 * (2**attempt)) + random.uniform(0, 0.25)  # noqa: S311
                    time.sleep(backoff_s)
                    attempt += 1
                    continue
                try:
                    detail = exc.read().decode("utf-8")
                except Exception:  # noqa: BLE001
                    detail = ""
                raise OpenAIResponsesError(
                    f"OpenAI HTTP error {status}: {detail[:300]}"
                ) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    backoff_s = (0.5 * (2**attempt)) + random.uniform(0, 0.25)  # noqa: S311
                    time.sleep(backoff_s)
                    attempt += 1
                    continue
                raise OpenAIResponsesError(f"OpenAI request failed: {exc}") from exc

        raise OpenAIResponsesError(f"OpenAI request failed after retries: {last_error}")


def parse_response_json(*, response: Dict[str, Any]) -> Dict[str, Any]:
    text = _extract_output_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAIResponsesError(f"Model output was not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise OpenAIResponsesError("Model output JSON must be an object")
    return data

