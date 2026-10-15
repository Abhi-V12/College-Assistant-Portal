"""
Thin client for a locally running LM Studio server (OpenAI-compatible API).

LM Studio (https://lmstudio.ai): load a small instruct model (e.g.
Qwen2.5-3B-Instruct, Llama-3.2-3B-Instruct), start its "Local Server" tab
(default http://localhost:1234/v1), and this module talks to it over plain
HTTP — no model-serving code lives in this backend at all.

Entirely optional and isolated: if LM Studio isn't running, every call here
raises LLMUnavailable quickly, and the caller (chatbot.py) falls back to the
existing "couldn't find an answer" behavior. The FAQ retrieval path never
depends on this module — a working Orbit AI FAQ bot doesn't require LM
Studio to be running at all.
"""

from typing import Optional

import requests

from .config import COLLEGE_NAME, COLLEGE_SHORT

LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LM_STUDIO_MODEL = "local-model"  # LM Studio ignores this field if only one model is loaded; it's required by the API shape regardless
REQUEST_TIMEOUT = 30  # seconds — small local models on CPU can genuinely take this long

SYSTEM_PROMPT = (
    f"You are {COLLEGE_SHORT} AI, a friendly assistant for {COLLEGE_NAME}. Keep answers "
    "concise (2-4 sentences unless the user asks for more detail). If asked "
    "for something that needs real student-specific data (grades, "
    "attendance, fees), tell the user to check the relevant dashboard page "
    "instead of guessing an answer."
)


class LLMUnavailable(Exception):
    """Raised whenever the local LM Studio server can't be reached or
    returns something unusable — callers should catch this and degrade
    gracefully rather than letting it 500 the whole chatbot endpoint."""


def chat_completion(user_message: str, context: Optional[str] = None) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"Relevant college FAQ info you can draw on:\n{context}"})
    messages.append({"role": "user", "content": user_message})

    try:
        resp = requests.post(
            f"{LM_STUDIO_BASE_URL}/chat/completions",
            json={
                "model": LM_STUDIO_MODEL,
                "messages": messages,
                "temperature": 0.6,
                "max_tokens": 300,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        raise LLMUnavailable(f"Could not reach LM Studio at {LM_STUDIO_BASE_URL}: {e}") from e
    except (KeyError, IndexError, ValueError) as e:
        raise LLMUnavailable(f"Unexpected response shape from LM Studio: {e}") from e
