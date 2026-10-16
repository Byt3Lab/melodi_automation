import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeCategory, NodeExecutionResult, NodePort
from ...services.ai_client import AIClient, AIClientError

logger = logging.getLogger("melodi.automation.nodes.ai")


class AIChatNode(BaseNode):
    """
    Nœud de complétion et de génération IA (LLM).
    Permet d'envoyer des prompts avec contexte dynamique vers Gemini, OpenAI, Claude, Mistral, Ollama, etc.
    Supporte les formats texte brut et JSON structuré.
    """

    id = "core.ai_chat"
    name = "Chat IA"
    name_t = "nodes.ai_chat.name"
    category = NodeCategory.AI
    icon = "chat"
    color = "#06b6d4"
    description = "Génère du texte, des analyses, des résumés ou du JSON structuré via un modèle d'IA (Gemini, OpenAI, Claude, etc.)."
    description_t = "nodes.ai_chat.description"

    def __init__(self):
        self.inputs = [
            NodePort(id="main", label="Entrée", label_t="ports.input", port_type="main")
        ]
        self.outputs = [
            NodePort(
                id="main",
                label="Réponse IA",
                label_t="nodes.ai_chat.ports.success",
                port_type="main",
                color="#06b6d4",
                description="Réponse générée par le modèle d'IA",
                description_t="nodes.ai_chat.ports.success_desc",
            ),
            NodePort(
                id="error",
                label="Erreur IA",
                label_t="nodes.ai_chat.ports.error",
                port_type="error",
                color="#ef4444",
                description="Emprunté en cas d'erreur de quota, clé invalide ou indisponibilité",
                description_t="nodes.ai_chat.ports.error_desc",
            ),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "provider": {
                "type": "select",
                "label": "Fournisseur d'IA",
                "label_t": "nodes.ai_chat.fields.provider.label",
                "options": [
                    {"label": "Google Gemini (Recommandé)", "label_t": "nodes.ai_chat.fields.provider.gemini", "value": "gemini"},
                    {"label": "OpenAI (GPT-4o, GPT-4o-mini)", "label_t": "nodes.ai_chat.fields.provider.openai", "value": "openai"},
                    {"label": "Anthropic Claude (3.5 Sonnet, 3 Haiku)", "label_t": "nodes.ai_chat.fields.provider.anthropic", "value": "anthropic"},
                    {"label": "Mistral AI", "label_t": "nodes.ai_chat.fields.provider.mistral", "value": "mistral"},
                    {"label": "Ollama (Modèles Locaux Open-Source)", "label_t": "nodes.ai_chat.fields.provider.ollama", "value": "ollama"},
                    {"label": "Endpoint Personnalisé (Compatible OpenAI)", "label_t": "nodes.ai_chat.fields.provider.custom", "value": "custom"},
                ],
                "default": "gemini",
                "required": True,
            },
            "model": {
                "type": "string",
                "label": "Modèle",
                "label_t": "nodes.ai_chat.fields.model.label",
                "default": "gemini-1.5-flash",
                "description": "Nom du modèle (ex: gemini-1.5-flash, gpt-4o-mini, claude-3-5-sonnet-20241022, mistral-small-latest, llama3.2).",
                "description_t": "nodes.ai_chat.fields.model.description",
            },
            "api_key": {
                "type": "string",
                "label": "Clé d'API",
                "label_t": "nodes.ai_chat.fields.api_key.label",
                "description": "Laissez vide pour utiliser la variable d'environnement (ex: GEMINI_API_KEY, OPENAI_API_KEY). Supporte {env.KEY}.",
                "description_t": "nodes.ai_chat.fields.api_key.description",
            },
            "base_url": {
                "type": "string",
                "label": "URL de base (Optionnel)",
                "label_t": "nodes.ai_chat.fields.base_url.label",
                "description": "Utile pour Ollama (ex: http://localhost:11434/v1) ou passerelles IA d'entreprise.",
                "description_t": "nodes.ai_chat.fields.base_url.description",
            },
            "system_prompt": {
                "type": "string",
                "label": "Message Système (Instructions)",
                "label_t": "nodes.ai_chat.fields.system_prompt.label",
                "default": "Tu es un assistant IA précis, courtois et expert.",
                "description": "Définit le rôle et les contraintes du modèle. Supporte les variables {payload.foo}.",
                "description_t": "nodes.ai_chat.fields.system_prompt.description",
            },
            "prompt": {
                "type": "string",
                "label": "Prompt Utilisateur (Question / Requête)",
                "label_t": "nodes.ai_chat.fields.prompt.label",
                "required": True,
                "description": "Contenu envoyé au modèle. Supporte {payload.texte}, {steps.http_1.data}, etc.",
                "description_t": "nodes.ai_chat.fields.prompt.description",
            },
            "response_format": {
                "type": "select",
                "label": "Format de la réponse",
                "label_t": "nodes.ai_chat.fields.response_format.label",
                "options": [
                    {"label": "Texte brut (Standard)", "label_t": "nodes.ai_chat.fields.response_format.text", "value": "text"},
                    {"label": "JSON structuré (json_object)", "label_t": "nodes.ai_chat.fields.response_format.json_object", "value": "json_object"},
                ],
                "default": "text",
            },
            "temperature": {
                "type": "number",
                "label": "Température (Créativité)",
                "label_t": "nodes.ai_chat.fields.temperature.label",
                "default": 0.7,
                "description": "Entre 0.0 (déterministe et précis) et 1.0 (créatif).",
                "description_t": "nodes.ai_chat.fields.temperature.description",
            },
            "max_tokens": {
                "type": "number",
                "label": "Jetons Maximum (Max Tokens)",
                "label_t": "nodes.ai_chat.fields.max_tokens.label",
                "default": 2048,
            },
            "pass_through_input": {
                "type": "boolean",
                "label": "Relayer les données d'entrée reçues",
                "label_t": "nodes.ai_chat.fields.pass_through_input.label",
                "default": False,
            },
        }

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        from ...services.execution_engine import ExecutionEngine

        eval_context = dict(context)
        eval_context["context"] = context
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)
            for k, v in input_data.items():
                if k not in eval_context:
                    eval_context[k] = v

        provider = str(config.get("provider") or "gemini").lower()
        model = ExecutionEngine.interpolate_value(config.get("model") or "", eval_context) or None
        api_key_raw = config.get("api_key") or ""
        api_key = str(ExecutionEngine.interpolate_value(api_key_raw, eval_context)).strip() or None
        base_url_raw = config.get("base_url") or ""
        base_url = str(ExecutionEngine.interpolate_value(base_url_raw, eval_context)).strip() or None

        raw_system = config.get("system_prompt") or "Tu es un assistant IA précis, courtois et expert."
        system_prompt = str(ExecutionEngine.interpolate_value(raw_system, eval_context))

        raw_prompt = config.get("prompt") or ""
        prompt = str(ExecutionEngine.interpolate_value(raw_prompt, eval_context))

        if not prompt:
            return NodeExecutionResult(
                output_data={"error": "Le champ 'prompt' est obligatoire.", "provider": provider},
                active_ports=["error"],
            )

        temperature = float(config.get("temperature") if config.get("temperature") is not None else 0.7)
        max_tokens = int(config.get("max_tokens") or 2048)
        response_format = config.get("response_format") or "text"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            res = await AIClient.chat_completion(
                provider=provider,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                api_key=api_key,
                base_url=base_url,
            )
        except AIClientError as e:
            logger.warning("Erreur AIClient (%s): %s", provider, e.message)
            return NodeExecutionResult(
                output_data=e.to_dict(),
                active_ports=["error"],
            )
        except Exception as e:
            logger.exception("Erreur inattendue dans AIChatNode (%s)", provider)
            return NodeExecutionResult(
                output_data={"error": str(e), "provider": provider},
                active_ports=["error"],
            )

        output_data: Dict[str, Any] = {
            "content": res.get("content", ""),
            "role": res.get("role", "assistant"),
            "model": res.get("model"),
            "provider": res.get("provider"),
            "usage": res.get("usage", {}),
        }

        # Si le mode json_object est demandé, tenter de parser le JSON
        if response_format == "json_object" and output_data["content"]:
            try:
                output_data["json"] = json.loads(output_data["content"])
            except Exception:
                # Recherche d'un bloc ```json ... ```
                m = re.search(r"```json\s*(\{.*?\})\s*```", output_data["content"], re.DOTALL)
                if m:
                    try:
                        output_data["json"] = json.loads(m.group(1))
                    except Exception:
                        output_data["json"] = None
                else:
                    output_data["json"] = None

        if config.get("pass_through_input") and isinstance(input_data, dict):
            output_data["input"] = input_data

        return NodeExecutionResult(output_data=output_data, active_ports=["main"])


class AIAgentNode(BaseNode):
    """
    Agent IA autonome capable d'exécuter des outils en boucle (ReAct / Tool Calling) :
      - Appels d'actions métier des modules MELODI (commerce, notification, etc.)
      - Appels de sous-workflows existants
      - Appels d'autres nœuds d'automatisation (requête HTTP, etc.)
    Supporte Google Gemini, OpenAI, Claude, Mistral, Ollama.
    """

    id = "core.ai_agent"
    name = "Agent IA Autonome"
    name_t = "nodes.ai_agent.name"
    category = NodeCategory.AI
    icon = "smart_toy"
    color = "#8b5cf6"
    description = "Agent intelligent autonome avec boucle de réflexion (Tool Calling) capable d'exécuter des actions ERP, des sous-workflows ou d'autres nœuds."
    description_t = "nodes.ai_agent.description"

    def __init__(self):
        self.inputs = [
            NodePort(id="main", label="Entrée", label_t="ports.input", port_type="main")
        ]
        self.outputs = [
            NodePort(
                id="main",
                label="Résultat Agent",
                label_t="nodes.ai_agent.ports.success",
                port_type="main",
                color="#8b5cf6",
                description="Réponse finale et étapes d'exécution de l'agent",
                description_t="nodes.ai_agent.ports.success_desc",
            ),
            NodePort(
                id="error",
                label="Erreur Agent",
                label_t="nodes.ai_agent.ports.error",
                port_type="error",
                color="#ef4444",
                description="Emprunté en cas d'erreur de modèle ou d'interruption",
                description_t="nodes.ai_agent.ports.error_desc",
            ),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "provider": {
                "type": "select",
                "label": "Fournisseur d'IA",
                "label_t": "nodes.ai_agent.fields.provider.label",
                "options": [
                    {"label": "Google Gemini (Recommandé)", "label_t": "nodes.ai_agent.fields.provider.gemini", "value": "gemini"},
                    {"label": "OpenAI (GPT-4o, GPT-4o-mini)", "label_t": "nodes.ai_agent.fields.provider.openai", "value": "openai"},
                    {"label": "Anthropic Claude (3.5 Sonnet)", "label_t": "nodes.ai_agent.fields.provider.anthropic", "value": "anthropic"},
                    {"label": "Mistral AI", "label_t": "nodes.ai_agent.fields.provider.mistral", "value": "mistral"},
                    {"label": "Ollama (Local)", "label_t": "nodes.ai_agent.fields.provider.ollama", "value": "ollama"},
                    {"label": "Endpoint Personnalisé", "label_t": "nodes.ai_agent.fields.provider.custom", "value": "custom"},
                ],
                "default": "gemini",
                "required": True,
            },
            "model": {
                "type": "string",
                "label": "Modèle",
                "label_t": "nodes.ai_agent.fields.model.label",
                "default": "gemini-1.5-flash",
                "description": "Nom du modèle compatible function calling (ex: gemini-1.5-flash, gpt-4o-mini, claude-3-5-sonnet-20241022).",
                "description_t": "nodes.ai_agent.fields.model.description",
            },
            "api_key": {
                "type": "string",
                "label": "Clé d'API",
                "label_t": "nodes.ai_agent.fields.api_key.label",
                "description": "Laissez vide pour utiliser les variables d'environnement (GEMINI_API_KEY, etc.).",
                "description_t": "nodes.ai_agent.fields.api_key.description",
            },
            "base_url": {
                "type": "string",
                "label": "URL de base (Optionnel)",
                "label_t": "nodes.ai_agent.fields.base_url.label",
            },
            "system_prompt": {
                "type": "string",
                "label": "Instructions de l'Agent (System)",
                "label_t": "nodes.ai_agent.fields.system_prompt.label",
                "default": "Tu es un agent intelligent et autonome dans le système ERP MELODI. Tu as accès à plusieurs outils (actions ERP, sous-workflows, requêtes). Analyse la demande, choisis les outils adéquats et fournis une synthèse complète.",
                "description_t": "nodes.ai_agent.fields.system_prompt.description",
            },
            "prompt": {
                "type": "string",
                "label": "Objectif / Tâche de l'Agent",
                "label_t": "nodes.ai_agent.fields.prompt.label",
                "required": True,
                "description": "Ce que l'agent doit accomplir. Supporte {payload.demande}, etc.",
                "description_t": "nodes.ai_agent.fields.prompt.description",
            },
            "tools": {
                "type": "json",
                "label": "Outils autorisés (Tools)",
                "label_t": "nodes.ai_agent.fields.tools.label",
                "default": ["all_actions"],
                "description": "Liste d'outils autorisés. Exemples: ['all_actions'], ['action:notification.send_email'], [{'type': 'workflow', 'workflow_id': '...'}] ou [{'type': 'node', 'node_type': 'core.http_request'}].",
                "description_t": "nodes.ai_agent.fields.tools.description",
            },
            "max_iterations": {
                "type": "number",
                "label": "Nombre max d'itérations",
                "label_t": "nodes.ai_agent.fields.max_iterations.label",
                "default": 5,
                "description": "Limite le nombre de boucles de réflexion / appels d'outils consécutifs (1 à 10).",
                "description_t": "nodes.ai_agent.fields.max_iterations.description",
            },
            "temperature": {
                "type": "number",
                "label": "Température",
                "label_t": "nodes.ai_agent.fields.temperature.label",
                "default": 0.2,
                "description": "Une valeur basse (0.1 - 0.3) garantit une exécution rigoureuse des outils.",
                "description_t": "nodes.ai_agent.fields.temperature.description",
            },
        }

    @classmethod
    def _sanitize_tool_name(cls, name: str) -> str:
        """Garantit un nom d'outil valide pour Gemini et OpenAI (alphanumériques et underscores)."""
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        return clean[:64]

    @classmethod
    async def _build_tool_catalog(
        cls,
        tools_config: List[Any],
        app: Any,
        context: Dict[str, Any],
    ) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        Construit la liste des schémas de tools au format OpenAI Function Calling
        ainsi que la table de routage d'exécution.
        """
        from ...services.action_registry_service import ActionRegistryService
        from ..registry import NodeRegistry

        tool_schemas: List[Dict[str, Any]] = []
        tool_dispatch: Dict[str, Dict[str, Any]] = {}

        if not tools_config:
            return tool_schemas, tool_dispatch

        # 1. Vérification de la présence de "all_actions" ou "*"
        wants_all_actions = False
        explicit_actions = set()
        sub_workflows = []
        nodes_list = []

        for item in tools_config:
            if isinstance(item, str):
                item_str = item.strip()
                if item_str in ("all_actions", "*"):
                    wants_all_actions = True
                elif item_str.startswith("action:"):
                    explicit_actions.add(item_str.split(":", 1)[1])
                elif item_str.startswith("workflow:"):
                    sub_workflows.append({"workflow_id": item_str.split(":", 1)[1]})
                elif item_str.startswith("node:"):
                    nodes_list.append({"node_type": item_str.split(":", 1)[1]})
                else:
                    explicit_actions.add(item_str)
            elif isinstance(item, dict):
                t_type = item.get("type")
                if t_type == "action":
                    act = item.get("action_id") or f"{item.get('module')}.{item.get('action')}"
                    explicit_actions.add(act)
                elif t_type == "workflow":
                    sub_workflows.append(item)
                elif t_type == "node":
                    nodes_list.append(item)

        # 2. Ajout des actions ERP
        if wants_all_actions or explicit_actions:
            available = ActionRegistryService.get_available_actions(app)
            for act_meta in available:
                act_id = act_meta["id"]
                if wants_all_actions or act_id in explicit_actions:
                    mod = act_meta["module"]
                    act = act_meta["action"]
                    tool_fn_name = cls._sanitize_tool_name(f"action__{mod}__{act}")

                    # Paramètres
                    properties = {}
                    required = []
                    for p_name, p_info in act_meta.get("parameters", {}).items():
                        p_type = p_info.get("type", "string")
                        json_type = "string"
                        if p_type in ("int", "number", "float"):
                            json_type = "number"
                        elif p_type in ("bool", "boolean"):
                            json_type = "boolean"
                        elif p_type in ("dict", "object", "json"):
                            json_type = "object"
                        elif p_type in ("list", "array"):
                            json_type = "array"

                        properties[p_name] = {
                            "type": json_type,
                            "description": p_info.get("description", f"Paramètre {p_name}"),
                        }
                        if p_info.get("required"):
                            required.append(p_name)

                    tool_schemas.append({
                        "type": "function",
                        "function": {
                            "name": tool_fn_name,
                            "description": f"[Action ERP MELODI: {mod}.{act}] {act_meta.get('description', '')}",
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required,
                            },
                        },
                    })
                    tool_dispatch[tool_fn_name] = {
                        "type": "action",
                        "module": mod,
                        "action": act,
                    }

        # 3. Ajout des sous-workflows
        for wf_item in sub_workflows:
            wf_id = wf_item.get("workflow_id")
            if not wf_id:
                continue
            wf_name = wf_item.get("name") or f"wf_{wf_id.replace('-', '_')}"
            tool_fn_name = cls._sanitize_tool_name(f"workflow__{wf_name}")
            wf_desc = wf_item.get("description") or f"Exécute le sous-workflow MELODI '{wf_id}'."

            tool_schemas.append({
                "type": "function",
                "function": {
                    "name": tool_fn_name,
                    "description": f"[Sous-Workflow MELODI] {wf_desc}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "payload": {
                                "type": "object",
                                "description": "Données d'entrée (payload JSON) à transmettre au sous-workflow",
                            }
                        },
                        "required": ["payload"],
                    },
                },
            })
            tool_dispatch[tool_fn_name] = {
                "type": "workflow",
                "workflow_id": wf_id,
            }

        # 4. Ajout des nœuds d'automatisation (ex: core.http_request)
        for n_item in nodes_list:
            node_id = n_item.get("node_type")
            if not node_id:
                continue
            node_inst = NodeRegistry.get(node_id)
            if not node_inst:
                continue

            node_alias = n_item.get("name") or node_id.replace(".", "_")
            tool_fn_name = cls._sanitize_tool_name(f"node__{node_alias}")
            node_desc = n_item.get("description") or node_inst.description or f"Nœud {node_inst.name}"

            # Construction des paramètres à partir du schéma du nœud
            node_schema = node_inst.get_schema()
            properties = {}
            for f_name, f_conf in node_schema.items():
                f_type = f_conf.get("type", "string")
                json_type = "string"
                if f_type in ("number", "integer"):
                    json_type = "number"
                elif f_type == "boolean":
                    json_type = "boolean"
                elif f_type in ("json", "object"):
                    json_type = "object"
                elif f_type == "array":
                    json_type = "array"

                properties[f_name] = {
                    "type": json_type,
                    "description": f_conf.get("description") or f_conf.get("label") or f"Paramètre {f_name}",
                }

            tool_schemas.append({
                "type": "function",
                "function": {
                    "name": tool_fn_name,
                    "description": f"[Nœud Automatisation: {node_inst.name}] {node_desc}",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                    },
                },
            })
            tool_dispatch[tool_fn_name] = {
                "type": "node",
                "node_id": node_id,
                "node_instance": node_inst,
                "default_config": n_item.get("config", {}),
            }

        return tool_schemas, tool_dispatch

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        from ...services.execution_engine import ExecutionEngine
        from ...repositories.workflow_repository import WorkflowRepository

        eval_context = dict(context)
        eval_context["context"] = context
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)
            for k, v in input_data.items():
                if k not in eval_context:
                    eval_context[k] = v

        provider = str(config.get("provider") or "gemini").lower()
        model = ExecutionEngine.interpolate_value(config.get("model") or "", eval_context) or None
        api_key_raw = config.get("api_key") or ""
        api_key = str(ExecutionEngine.interpolate_value(api_key_raw, eval_context)).strip() or None
        base_url_raw = config.get("base_url") or ""
        base_url = str(ExecutionEngine.interpolate_value(base_url_raw, eval_context)).strip() or None

        raw_system = config.get("system_prompt") or "Tu es un agent autonome MELODI."
        system_prompt = str(ExecutionEngine.interpolate_value(raw_system, eval_context))

        raw_prompt = config.get("prompt") or ""
        prompt = str(ExecutionEngine.interpolate_value(raw_prompt, eval_context))

        if not prompt:
            return NodeExecutionResult(
                output_data={"error": "Le champ 'prompt' (objectif de l'agent) est obligatoire.", "provider": provider},
                active_ports=["error"],
            )

        temperature = float(config.get("temperature") if config.get("temperature") is not None else 0.2)
        max_iterations = min(max(int(config.get("max_iterations") or 5), 1), 10)
        tools_cfg = config.get("tools") or ["all_actions"]

        # Construction du catalogue d'outils
        tool_schemas, tool_dispatch = await self._build_tool_catalog(tools_cfg, app, context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        steps_log: List[Dict[str, Any]] = []
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_tool_calls_count = 0
        final_content = ""

        current_stack = list(context.get("_execution_stack") or [])

        # Boucle d'exécution agentique (ReAct)
        for iteration in range(1, max_iterations + 1):
            try:
                completion = await AIClient.chat_completion(
                    provider=provider,
                    model=model,
                    messages=messages,
                    tools=tool_schemas if tool_schemas else None,
                    temperature=temperature,
                    api_key=api_key,
                    base_url=base_url,
                )
            except AIClientError as e:
                logger.warning("Erreur AIClient dans l'agent (%s): %s", provider, e.message)
                return NodeExecutionResult(
                    output_data={
                        "error": e.message,
                        "provider": provider,
                        "steps": steps_log,
                        "iteration": iteration,
                    },
                    active_ports=["error"],
                )
            except Exception as e:
                logger.exception("Erreur inattendue dans AIAgentNode")
                return NodeExecutionResult(
                    output_data={
                        "error": str(e),
                        "provider": provider,
                        "steps": steps_log,
                        "iteration": iteration,
                    },
                    active_ports=["error"],
                )

            # Accumulation des usages
            u = completion.get("usage", {})
            total_usage["prompt_tokens"] += u.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += u.get("completion_tokens", 0)
            total_usage["total_tokens"] += u.get("total_tokens", 0)

            assistant_content = completion.get("content") or ""
            tool_calls = completion.get("tool_calls") or []

            # Enregistrement de l'étape
            step_record = {
                "iteration": iteration,
                "assistant_message": assistant_content,
                "tool_calls": tool_calls,
            }

            if not tool_calls:
                # L'agent a terminé et donne sa réponse finale
                final_content = assistant_content
                steps_log.append(step_record)
                break

            # S'il y a des tool calls, enregistrer le message de l'assistant dans l'historique
            messages.append({
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": completion.get("raw", {}).get("choices", [{}])[0].get("message", {}).get("tool_calls") or [],
            })

            tool_results_for_step = []

            for tc in tool_calls:
                total_tool_calls_count += 1
                tc_id = tc["id"]
                fn_name = tc["name"]
                args = tc.get("arguments", {})

                handler = tool_dispatch.get(fn_name)
                tool_output: Any = None

                if not handler:
                    tool_output = {"error": f"Outil '{fn_name}' introuvable ou non autorisé."}
                else:
                    h_type = handler["type"]
                    try:
                        if h_type == "action":
                            mod = handler["module"]
                            act = handler["action"]
                            # Exécution de l'action MELODI sans couplage SQL
                            if hasattr(app, "hook_manager") and hasattr(app.hook_manager, "action"):
                                tool_output = await app.hook_manager.action.execute(mod, act, args)
                            else:
                                tool_output = {"error": "Gestionnaire de hooks non disponible dans l'application."}

                        elif h_type == "workflow":
                            target_wf_id = handler["workflow_id"]
                            # Vérification anti-boucle de récursion
                            if target_wf_id in current_stack:
                                tool_output = {"error": f"Boucle récursive détectée pour le sous-workflow '{target_wf_id}'."}
                            else:
                                async with app.db.get_session() as session:
                                    target_wf = await WorkflowRepository.get_workflow_by_id(session, target_wf_id)
                                if not target_wf or not target_wf.active:
                                    tool_output = {"error": f"Sous-workflow '{target_wf_id}' introuvable ou inactif."}
                                else:
                                    sub_ctx = {
                                        "payload": args.get("payload", args),
                                        "_execution_stack": current_stack + [target_wf_id],
                                    }
                                    res = await ExecutionEngine.execute(target_wf, sub_ctx, app)
                                    tool_output = {
                                        "status": res.get("status"),
                                        "output": res.get("context", {}).get("last_output"),
                                        "error": res.get("error"),
                                    }

                        elif h_type == "node":
                            node_instance = handler["node_instance"]
                            node_conf = dict(handler.get("default_config") or {})
                            node_conf.update(args)
                            res_node = await node_instance.execute(
                                input_data=args,
                                config=node_conf,
                                context=eval_context,
                                app=app,
                            )
                            tool_output = res_node.output_data

                    except Exception as ex:
                        logger.exception("Erreur lors de l'exécution de l'outil %s", fn_name)
                        tool_output = {"error": str(ex)}

                tool_results_for_step.append({
                    "tool": fn_name,
                    "arguments": args,
                    "output": tool_output,
                })

                # Ajout du message de résultat d'outil dans l'historique
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": fn_name,
                    "content": json.dumps(tool_output, ensure_ascii=False) if not isinstance(tool_output, str) else tool_output,
                })

            step_record["tool_results"] = tool_results_for_step
            steps_log.append(step_record)

        # Si l'agent a atteint max_iterations sans réponse finale explicite
        if not final_content and steps_log:
            last_step = steps_log[-1]
            final_content = last_step.get("assistant_message") or "Limite d'itérations atteinte pour l'agent."

        return NodeExecutionResult(
            output_data={
                "content": final_content,
                "role": "assistant",
                "steps": steps_log,
                "tool_calls_count": total_tool_calls_count,
                "iterations": len(steps_log),
                "model": model or AIClient.DEFAULT_MODELS.get(provider, "default"),
                "provider": provider,
                "usage": total_usage,
            },
            active_ports=["main"],
        )
