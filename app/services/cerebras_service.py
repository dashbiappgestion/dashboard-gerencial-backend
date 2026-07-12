import httpx
from app.config import get_settings

API_URL = "https://api.cerebras.ai/v1/chat/completions"


class CerebrasApiService:
    def __init__(self):
        settings = get_settings()
        self.api_keys = settings.cerebras_api_keys
        self.model = settings.cerebras_model
        self.client = httpx.Client(timeout=60.0)

    def resolver_clave(self, indice: int) -> str:
        if not self.api_keys:
            raise RuntimeError("No hay llaves de Cerebras configuradas")
        return self.api_keys[indice % len(self.api_keys)]

    def chat_completion(self, key_index: int, messages: list, tools: list | None = None) -> dict:
        api_key = self.resolver_clave(key_index)
        body = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        response = self.client.post(API_URL, json=body, headers=headers)
        response.raise_for_status()
        return self._parse_response(response.json())

    def _parse_response(self, raw: dict) -> dict:
        choice = raw.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = []
        for tc in message.get("tool_calls", []) or []:
            function = tc.get("function", {})
            tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "name": function.get("name", ""),
                    "arguments": function.get("arguments", "{}"),
                }
            )
        return {
            "role": message.get("role", "assistant"),
            "content": message.get("content"),
            "tool_calls": tool_calls,
            "finish_reason": choice.get("finish_reason", "stop"),
        }

    def assistant_tool_calls_message(self, resultado: dict) -> dict:
        return {
            "role": "assistant",
            "content": resultado.get("content"),
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in resultado.get("tool_calls", [])
            ],
        }

    def tool_message(self, tool_call_id: str, content: str) -> dict:
        return {"role": "tool", "tool_call_id": tool_call_id, "content": content or ""}


cerebras_api_service = CerebrasApiService()