import sys

import openai

from companion.provider import ChatMessage, ProviderError

BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider:
    def __init__(self, api_key: str | None, model: str, log_usage: bool = False):
        self.api_key = api_key
        self.model = model
        self.log_usage = log_usage
        self._client: openai.OpenAI | None = None

    def complete(self, persona: str, messages: list[ChatMessage]) -> str:
        if not self.api_key:
            raise ProviderError(
                "No DeepSeek API key found. Set DEEPSEEK_API_KEY in the environment or in a .env file."
            )
        if self._client is None:
            self._client = openai.OpenAI(api_key=self.api_key, base_url=BASE_URL)
        payload = [{"role": "system", "content": persona}]
        payload += [{"role": m.role, "content": m.content} for m in messages]
        try:
            response = self._client.chat.completions.create(model=self.model, messages=payload)
        except openai.APIConnectionError as e:
            raise ProviderError(f"Could not reach DeepSeek (network problem): {e}") from e
        except openai.RateLimitError as e:
            raise ProviderError(f"DeepSeek quota or rate limit reached: {e}") from e
        except openai.NotFoundError as e:
            raise ProviderError(f"Model '{self.model}' is not available on DeepSeek: {e}") from e
        except openai.AuthenticationError as e:
            raise ProviderError(f"DeepSeek rejected the API key: {e}") from e
        except openai.APIStatusError as e:
            raise ProviderError(f"DeepSeek returned an error ({e.status_code}): {e}") from e
        if self.log_usage:
            _print_usage(response)
        try:
            content = response.choices[0].message.content
        except (IndexError, AttributeError) as e:
            raise ProviderError("DeepSeek returned a malformed reply.") from e
        if not content:
            raise ProviderError("DeepSeek returned an empty reply.")
        return content.strip()


def _print_usage(response) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    cached = getattr(usage, "prompt_cache_hit_tokens", None) or 0
    print(
        f"[usage] prompt={usage.prompt_tokens} (cached={cached}) completion={usage.completion_tokens}",
        file=sys.stderr,
    )
