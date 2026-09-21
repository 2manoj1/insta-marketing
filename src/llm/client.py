"""
Universal LLM client for OpenAI-compatible gateways.
Targets:
- https://api.manojmukherjee.co.in/v1 (Ollama-backed model gateway)
- http://localhost:11434/v1 (Local Ollama)
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional
from openai import OpenAI, APIConnectionError, APIStatusError
from src.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 35.0,
    ):
        self.api_base = api_base or settings.llm_api_base
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model

        self.client = OpenAI(
            base_url=self.api_base,
            api_key=self.api_key,
            timeout=timeout,
        )

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        json_output: bool = False,
    ) -> str:
        """
        Sends chat completion request to the OpenAI-compatible gateway.
        """
        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if json_output:
                # Some Ollama gateways support response_format={"type": "json_object"}
                try:
                    return self._call_with_response_format(kwargs)
                except Exception:
                    # Fallback without response_format if gateway doesn't support parameter
                    pass

            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            return content.strip()

        except Exception as e:
            # Automatic fallback to local Ollama if remote gateway fails
            if self.api_base != "http://localhost:11434/v1":
                logger.warning(f"Primary LLM gateway ({self.api_base}) error: {e}. Falling back to local Ollama (http://localhost:11434/v1)...")
                try:
                    fallback_client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=15.0)
                    kwargs["model"] = "llama3.2:latest"
                    res = fallback_client.chat.completions.create(**kwargs)
                    return (res.choices[0].message.content or "").strip()
                except Exception as fb_err:
                    logger.error(f"Local Ollama fallback also failed: {fb_err}")
            logger.error(f"Error in LLM call: {e}")
            raise e

    def _call_with_response_format(self, kwargs: Dict[str, Any]) -> str:
        payload = dict(kwargs)
        payload["response_format"] = {"type": "json_object"}
        res = self.client.chat.completions.create(**payload)
        return (res.choices[0].message.content or "").strip()

    def generate_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
    ) -> Any:
        """
        Requests JSON response and safely extracts valid JSON dictionary or array.
        """
        # Ensure system prompt reminds the model to return valid JSON
        found_system = False
        enhanced_messages = []
        for m in messages:
            if m["role"] == "system":
                found_system = True
                enhanced_messages.append({
                    "role": "system",
                    "content": m["content"] + "\n\nCRITICAL: Respond ONLY with a valid, parseable JSON object or JSON array. Do not include introductory text or Markdown backticks."
                })
            else:
                enhanced_messages.append(m)

        if not found_system:
            enhanced_messages.insert(0, {
                "role": "system",
                "content": "You are a precise JSON extraction and synthesis engine. Output ONLY valid JSON."
            })

        raw_text = self.chat_completion(enhanced_messages, temperature=temperature, json_output=False)
        return self._clean_and_parse_json(raw_text)

    def _clean_and_parse_json(self, text: str) -> Any:
        """
        Cleans Markdown fences and extracts JSON dict or list.
        """
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting either [ ... ] or { ... }
        b_start = text.find("[")
        b_end = text.rfind("]")
        c_start = text.find("{")
        c_end = text.rfind("}")

        if b_start != -1 and (c_start == -1 or b_start < c_start) and b_end > b_start:
            try:
                return json.loads(text[b_start : b_end + 1])
            except json.JSONDecodeError:
                pass

        if c_start != -1 and c_end > c_start:
            try:
                return json.loads(text[c_start : c_end + 1])
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse JSON directly. Raw output: {text[:200]}")
        return {"raw_text": text}


# Default singleton instance
llm_client = LLMClient()
