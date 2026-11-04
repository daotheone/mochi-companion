import groq

from companion.provider import ChatMessage, ProviderError


class GroqProvider:
    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model
        self._client: groq.Groq | None = None

    def complete(self, persona: str, messages: list[ChatMessage]) -> str:
        if not self.api_key:
            raise ProviderError(
                "No Groq API key found. Set GROQ_API_KEY in the environment or in a .env file."
            )
        if self._client is None:
            self._client = groq.Groq(api_key=self.api_key)
        payload = [{"role": "system", "content": persona}]
        payload += [{"role": m.role, "content": m.content} for m in messages]
        try:
            response = self._client.chat.completions.create(model=self.model, messages=payload)
        except groq.APIConnectionError as e:
            raise ProviderError(f"Could not reach Groq (network problem): {e}") from e
        except groq.RateLimitError as e:
            raise ProviderError(f"Groq quota or rate limit reached: {e}") from e
        except groq.NotFoundError as e:
            raise ProviderError(f"Model '{self.model}' is not available on Groq: {e}") from e
        except groq.AuthenticationError as e:
            raise ProviderError(f"Groq rejected the API key: {e}") from e
        except groq.APIStatusError as e:
            raise ProviderError(f"Groq returned an error ({e.status_code}): {e}") from e
        content = response.choices[0].message.content
        if not content:
            raise ProviderError("Groq returned an empty reply.")
        return content.strip()
