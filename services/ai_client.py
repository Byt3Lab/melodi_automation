import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("melodi.automation.ai_client")


class AIClientError(Exception):
    """Exception levée en cas d'erreur de communication avec le fournisseur d'IA."""
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.message,
            "provider": self.provider,
            "status_code": self.status_code,
            "details": self.details,
        }


class AIClient:
    """
    Client unifié et asynchrone pour les modèles d'IA (LLMs), inspiré de l'architecture n8n.
    Prend en charge nativement :
      - Google Gemini (via son endpoint officiel OpenAI-compatible /v1beta/openai)
      - OpenAI (GPT-4o, GPT-4o-mini, etc.)
      - Anthropic Claude (Claude 3.5 Sonnet, Claude 3 Haiku, etc.)
      - Mistral AI (Mistral Large, Mistral Small, etc.)
      - Ollama (LLMs locaux open-source : Llama, Mistral, DeepSeek, etc.)
      - Custom (Tout endpoint compatible OpenAI : vLLM, LocalAI, Groq, OpenRouter)
    """

    DEFAULT_BASE_URLS = {
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "mistral": "https://api.mistral.ai/v1",
        "ollama": "http://localhost:11434/v1",
    }

    DEFAULT_MODELS = {
        "gemini": "gemini-1.5-flash",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-sonnet-20241022",
        "mistral": "mistral-small-latest",
        "ollama": "llama3.2",
        "custom": "default",
    }

    ENV_API_KEYS = {
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
    }

    @classmethod
    def resolve_api_key(cls, provider: str, explicit_key: Optional[str] = None) -> Optional[str]:
        if explicit_key and str(explicit_key).strip():
            return str(explicit_key).strip()

        env_keys = cls.ENV_API_KEYS.get(provider.lower(), [])
        for k in env_keys:
            val = os.getenv(k)
            if val and val.strip():
                return val.strip()

        return None

    @classmethod
    def resolve_base_url(cls, provider: str, explicit_base_url: Optional[str] = None) -> str:
        if explicit_base_url and str(explicit_base_url).strip():
            url = str(explicit_base_url).strip().rstrip("/")
            return url
        return cls.DEFAULT_BASE_URLS.get(provider.lower(), "https://api.openai.com/v1")

    @classmethod
    def resolve_model(cls, provider: str, explicit_model: Optional[str] = None) -> str:
        if explicit_model and str(explicit_model).strip():
            return str(explicit_model).strip()
        return cls.DEFAULT_MODELS.get(provider.lower(), "default")

    @classmethod
    async def chat_completion(
        cls,
        provider: str,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 2048,
        response_format: Optional[str] = None,  # "text" ou "json_object"
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Envoie une requête de complétion de chat au fournisseur sélectionné et renvoie une réponse unifiée :
        {
            "content": "...",
            "role": "assistant",
            "tool_calls": [...],
            "finish_reason": "stop" | "tool_calls" | "length",
            "usage": {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...},
            "model": "...",
            "provider": "..."
        }
        """
        provider = (provider or "gemini").lower()
        resolved_key = cls.resolve_api_key(provider, api_key)
        resolved_url = cls.resolve_base_url(provider, base_url)
        resolved_model = cls.resolve_model(provider, model)

        # Validation de la clé pour les fournisseurs distants
        if provider in ("gemini", "openai", "anthropic", "mistral") and not resolved_key:
            raise AIClientError(
                f"Clé d'API manquante pour le fournisseur '{provider}'. "
                f"Veuillez renseigner le champ 'api_key' ou définir la variable d'environnement appropriée "
                f"({', '.join(cls.ENV_API_KEYS.get(provider, []))}).",
                provider=provider,
            )

        if provider == "anthropic":
            return await cls._call_anthropic(
                base_url=resolved_url,
                api_key=resolved_key or "",
                model=resolved_model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens or 2048,
                timeout=timeout,
            )
        else:
            # Gemini, OpenAI, Mistral, Ollama et Custom utilisent tous le format OpenAI
            return await cls._call_openai_compatible(
                provider=provider,
                base_url=resolved_url,
                api_key=resolved_key,
                model=resolved_model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                timeout=timeout,
            )

    @classmethod
    async def _call_openai_compatible(
        cls,
        provider: str,
        base_url: str,
        api_key: Optional[str],
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Effectue un appel API vers un endpoint OpenAI-compatible (Gemini, OpenAI, Mistral, Ollama, etc.)."""
        endpoint = f"{base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
        }

        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

        if response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(endpoint, headers=headers, json=payload)
            except httpx.TimeoutException as e:
                raise AIClientError(f"Délai d'attente dépassé ({timeout}s) vers {provider} : {str(e)}", provider=provider)
            except httpx.RequestError as e:
                raise AIClientError(f"Erreur réseau lors de l'appel à {provider} : {str(e)}", provider=provider)

        if resp.status_code >= 400:
            err_details = None
            err_msg = f"Erreur HTTP {resp.status_code} de {provider}"
            try:
                err_data = resp.json()
                err_details = err_data
                if "error" in err_data:
                    err_info = err_data["error"]
                    if isinstance(err_info, dict):
                        err_msg += f": {err_info.get('message', str(err_info))}"
                    else:
                        err_msg += f": {err_info}"
            except Exception:
                err_msg += f": {resp.text}"

            raise AIClientError(err_msg, provider=provider, status_code=resp.status_code, details=err_details)

        try:
            data = resp.json()
        except Exception as e:
            raise AIClientError(f"Réponse JSON invalide reçue de {provider} : {str(e)}", provider=provider)

        choices = data.get("choices") or []
        if not choices:
            raise AIClientError(f"Aucun choix retourné par {provider}", provider=provider, details=data)

        first_choice = choices[0]
        msg = first_choice.get("message") or {}
        content = msg.get("content") or ""
        finish_reason = first_choice.get("finish_reason", "stop")

        raw_tool_calls = msg.get("tool_calls") or []
        normalized_tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function") or {}
            fn_name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except Exception:
                    parsed_args = {"raw": raw_args}
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
            else:
                parsed_args = {}

            normalized_tool_calls.append({
                "id": tc.get("id") or f"call_{len(normalized_tool_calls)}",
                "name": fn_name,
                "arguments": parsed_args,
            })

        usage_raw = data.get("usage") or {}
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens", 0),
            "completion_tokens": usage_raw.get("completion_tokens", 0),
            "total_tokens": usage_raw.get("total_tokens", 0),
        }

        return {
            "content": content,
            "role": "assistant",
            "tool_calls": normalized_tool_calls,
            "finish_reason": "tool_calls" if normalized_tool_calls else finish_reason,
            "usage": usage,
            "model": data.get("model", model),
            "provider": provider,
            "raw": data,
        }

    @classmethod
    async def _call_anthropic(
        cls,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Effectue un appel API vers Anthropic Messages API."""
        endpoint = f"{base_url}/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        # Séparation du message système des messages utilisateur/assistant
        system_prompt = ""
        filtered_messages = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                system_prompt = str(m.get("content", ""))
            elif role == "tool":
                # Convertir le format tool de retour en format tool_result Anthropic
                filtered_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id") or "tool_use_id",
                            "content": str(m.get("content", "")),
                        }
                    ],
                })
            else:
                filtered_messages.append({
                    "role": role,
                    "content": m.get("content", ""),
                })

        payload: Dict[str, Any] = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": max_tokens,
            "temperature": float(temperature),
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            # Conversion du format de tools OpenAI ({type: function, function: {...}}) au format Anthropic
            anthropic_tools = []
            for t in tools:
                if t.get("type") == "function" and "function" in t:
                    fn = t["function"]
                    anthropic_tools.append({
                        "name": fn.get("name"),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                    })
                else:
                    anthropic_tools.append(t)
            payload["tools"] = anthropic_tools

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(endpoint, headers=headers, json=payload)
            except httpx.TimeoutException as e:
                raise AIClientError(f"Délai d'attente dépassé ({timeout}s) vers Anthropic : {str(e)}", provider="anthropic")
            except httpx.RequestError as e:
                raise AIClientError(f"Erreur réseau lors de l'appel à Anthropic : {str(e)}", provider="anthropic")

        if resp.status_code >= 400:
            err_details = None
            err_msg = f"Erreur HTTP {resp.status_code} d'Anthropic"
            try:
                err_data = resp.json()
                err_details = err_data
                if "error" in err_data:
                    err_msg += f": {err_data['error'].get('message', str(err_data['error']))}"
            except Exception:
                err_msg += f": {resp.text}"

            raise AIClientError(err_msg, provider="anthropic", status_code=resp.status_code, details=err_details)

        try:
            data = resp.json()
        except Exception as e:
            raise AIClientError(f"Réponse JSON invalide reçue d'Anthropic : {str(e)}", provider="anthropic")

        content_blocks = data.get("content") or []
        text_parts = []
        normalized_tool_calls = []

        for block in content_blocks:
            b_type = block.get("type")
            if b_type == "text":
                text_parts.append(block.get("text", ""))
            elif b_type == "tool_use":
                normalized_tool_calls.append({
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "arguments": block.get("input", {}),
                })

        stop_reason = data.get("stop_reason")
        finish_reason = "tool_calls" if normalized_tool_calls else ("stop" if stop_reason == "end_turn" else stop_reason)

        usage_raw = data.get("usage") or {}
        usage = {
            "prompt_tokens": usage_raw.get("input_tokens", 0),
            "completion_tokens": usage_raw.get("output_tokens", 0),
            "total_tokens": usage_raw.get("input_tokens", 0) + usage_raw.get("output_tokens", 0),
        }

        return {
            "content": "".join(text_parts),
            "role": "assistant",
            "tool_calls": normalized_tool_calls,
            "finish_reason": finish_reason,
            "usage": usage,
            "model": data.get("model", model),
            "provider": "anthropic",
            "raw": data,
        }
