# File: openai_engine.py

import base64
import os
from mimetypes import guess_type
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Reads OPENAI_API_KEY from environment (recommended)
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Choose a default OpenAI model (swap to gpt-4.1 or gpt-4.1-mini if you prefer)
DEFAULT_MODEL = "gpt-4.1-mini"

# Instantiate a single shared client
_client = OpenAI(api_key=OPENAI_API_KEY)


def call_llm(
    user_prompt: str,
    system_message: str = "You are a helpful assistant to atomic physicist.",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """
    Calls OpenAI's Responses API with system instructions + a user prompt.

    Args:
      user_prompt: The text from the user.
      system_message: System/instruction message for behavior control.
      model: OpenAI model to use (e.g., 'gpt-4o', 'gpt-4.1-mini').
      max_tokens: Maximum tokens to generate (OpenAI param is 'max_output_tokens').
      temperature: Sampling temperature.

    Returns:
      The model's text output.
    """
    resp = _client.responses.create(
        model=model,
        instructions=system_message,
        input=user_prompt,
        max_output_tokens=max_tokens,
        temperature=temperature,
    )
    # Convenient helper provided by the SDK
    return resp.output_text


def call_vision(
    image_path: str,
    additional_context: str = "Describe this image.",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """
    Loads an image from disk, encodes as base64, and calls a vision-capable model.

    The Responses API accepts images via a data URL string:
      content[{type:'input_image', image_url:'data:<mime>;base64,<...>'}]

    Args:
      image_path: Local path to an image (png/jpg/jpeg/webp, etc.).
      additional_context: Extra user text to accompany the image.
      model: Vision-capable model (e.g., 'gpt-4o', 'gpt-4.1-mini').
      max_tokens: Maximum tokens to generate.
      temperature: Sampling temperature.

    Returns:
      The model's text output describing/analysing the image.
    """
    # Read & encode the image
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    # Best-effort MIME type
    media_type, _ = guess_type(image_path)
    if not media_type:
        media_type = "image/jpeg"

    data_url = f"data:{media_type};base64,{encoded}"

    resp = _client.responses.create(
        model=model,
        temperature=temperature,
        max_output_tokens=max_tokens,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": additional_context},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
    )
    return resp.output_text
