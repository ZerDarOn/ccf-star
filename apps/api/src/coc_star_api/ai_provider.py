import asyncio
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AiProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AiReply:
    text: str
    model: str


def _request_completion(base_url: str, api_key: str, model: str, messages: list[dict[str, str]]) -> AiReply:
    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.7}, ensure_ascii=False).encode()
    request = Request(endpoint, data=body, method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
    try:
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise AiProviderError("provider_request_failed") from error
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise AiProviderError("provider_response_invalid") from error
    if not isinstance(text, str) or not text.strip():
        raise AiProviderError("provider_response_empty")
    return AiReply(text=text.strip(), model=str(payload.get("model") or model))


async def complete(base_url: str, api_key: str, model: str, messages: list[dict[str, str]]) -> AiReply:
    return await asyncio.to_thread(_request_completion, base_url, api_key, model, messages)
