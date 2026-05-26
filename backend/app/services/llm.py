import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ["LLM_API_KEY"])

_MODEL = "gemini-flash-lite-latest"


def chat(system: str, messages: list[dict], max_tokens: int = 200) -> str:
    """Multi-turn conversation with a system prompt."""
    model = genai.GenerativeModel(model_name=_MODEL, system_instruction=system)
    # Gemini uses "model" instead of "assistant"
    history = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [m["content"]]}
        for m in messages[:-1]
    ]
    last = messages[-1]["content"]
    session = model.start_chat(history=history)
    response = session.send_message(
        last,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
    )
    return response.text.strip()


def complete(prompt: str, max_tokens: int = 100) -> str:
    """Single-turn completion."""
    model = genai.GenerativeModel(model_name=_MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
    )
    return response.text.strip()
