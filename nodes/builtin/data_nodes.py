import json
import re
from typing import Any, Dict, List
from ..base_node import BaseNode, NodeCategory, NodePort, NodeExecutionResult
from ...services.condition_engine import ConditionEngine


class SetFieldsNode(BaseNode):
    id = "core.set_fields"
    name = "Définir des Variables (Set Fields)"
    name_t = "nodes.set_fields.name"
    category = NodeCategory.DATA
    icon = "edit_note"
    color = "#10b981"
    description = "Crée, modifie ou enrichit des variables dans le flux de données pour les nœuds suivants."
    description_t = "nodes.set_fields.description"

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", label_t="ports.input", port_type="main")]
        self.outputs = [NodePort(id="main", label="Données enrichies", label_t="nodes.set_fields.ports.output", port_type="main", color="#10b981")]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "mode": {
                "type": "select",
                "label": "Mode d'assignation",
                "label_t": "nodes.set_fields.fields.mode.label",
                "options": [
                    {"label": "Ajouter / Fusionner avec les données existantes", "label_t": "nodes.set_fields.fields.mode.options.merge", "value": "merge"},
                    {"label": "Remplacer complètement (Nouveau payload)", "label_t": "nodes.set_fields.fields.mode.options.replace", "value": "replace"},
                ],
                "default": "merge",
            },
            "fields": {
                "type": "custom",
                "label": "Variables & Champs personnalisés",
                "label_t": "nodes.set_fields.fields.fields.label",
                "description": "Créez et configurez des variables de façon visuelle ou en mode code JSON.",
                "description_t": "nodes.set_fields.fields.fields.description",
                "default": [
                    {"key": "statut", "value": "traité", "type": "string"},
                ],
            },
        }

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        mode = config.get("mode", "merge")
        raw_fields = config.get("fields") or []
        if isinstance(raw_fields, str):
            try:
                raw_fields = json.loads(raw_fields)
            except json.JSONDecodeError:
                raw_fields = []

        fields: List[Dict[str, Any]] = []
        if isinstance(raw_fields, dict):
            # Si c'est un dictionnaire d'un seul élément au format {key, value}
            if "key" in raw_fields and "value" in raw_fields:
                fields = [raw_fields]
            else:
                # Dictionnaire plat clé-valeur saisi en mode code : {"montant": 100, "devise": "EUR"}
                for k, v in raw_fields.items():
                    fields.append({
                        "key": str(k),
                        "value": v,
                        "type": "number" if isinstance(v, (int, float)) and not isinstance(v, bool)
                                else ("boolean" if isinstance(v, bool)
                                else ("json" if isinstance(v, (dict, list))
                                else "string"))
                    })
        elif isinstance(raw_fields, list):
            for item in raw_fields:
                if isinstance(item, str):
                    try:
                        item = json.loads(item)
                    except json.JSONDecodeError:
                        continue
                if isinstance(item, dict):
                    if "key" in item:
                        fields.append(item)
                    else:
                        # Liste d'objets clé-valeur plats
                        for k, v in item.items():
                            fields.append({"key": str(k), "value": v, "type": "string"})

        # Construction du contexte de résolution
        eval_context = dict(context)
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)
            for k, v in input_data.items():
                if k not in eval_context:
                    eval_context[k] = v

        output = dict(input_data) if (mode == "merge" and isinstance(input_data, dict)) else {}

        from ...services.execution_engine import ExecutionEngine

        for item in fields:
            k = item.get("key")
            if not k:
                continue
            raw_v = item.get("value", "")
            field_type = item.get("type", "string")

            # Interpolation
            val = ExecutionEngine.interpolate_value(raw_v, eval_context)

            # Cast de type si nécessaire
            if field_type in ("number", "expression"):
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    pass
                else:
                    str_val = str(val).strip()
                    try:
                        val = float(str_val) if "." in str_val else int(str_val)
                    except Exception:
                        # Tentative d'évaluation arithmétique ou d'expression sécurisée
                        try:
                            safe_eval_globals = {
                                "__builtins__": {
                                    "round": round, "abs": abs, "min": min, "max": max,
                                    "int": int, "float": float, "len": len, "str": str,
                                },
                            }
                            res_calc = eval(str_val, safe_eval_globals, {})
                            if field_type == "number":
                                if isinstance(res_calc, (int, float)):
                                    val = res_calc
                            else:
                                val = res_calc
                        except Exception:
                            pass
            elif field_type == "boolean":
                val = str(val).lower() in ("true", "1", "yes")
            elif field_type in ("json", "object", "array") and isinstance(val, str):
                try:
                    val = json.loads(val)
                except Exception:
                    pass

            output[k] = val
            eval_context[k] = val

        return NodeExecutionResult(output_data=output, active_ports=["main"])


class CodeTransformNode(BaseNode):
    id = "core.code_transform"
    name = "Transformation de Données (Code / Formule)"
    name_t = "nodes.code_transform.name"
    category = NodeCategory.DATA
    icon = "code"
    color = "#f59e0b"
    description = "Exécute une transformation ou un calcul sécurisé sur le payload (mapping, calcul, agrégation)."
    description_t = "nodes.code_transform.description"

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", label_t="ports.input", port_type="main")]
        self.outputs = [NodePort(id="main", label="Résultat", label_t="nodes.code_transform.ports.output", port_type="main", color="#f59e0b")]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "expression": {
                "type": "textarea",
                "label": "Formule ou expression (Python sécurisé)",
                "label_t": "nodes.code_transform.fields.expression.label",
                "description": "Ex: {'total_ttc': input.get('total', 0) * 1.20, 'items_count': len(input.get('items', []))}",
                "description_t": "nodes.code_transform.fields.expression.description",
                "required": True,
                "default": "input",
            },
        }

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        expr = config.get("expression") or "input"

        # Environnement d'évaluation restreint et sécurisé (sans __import__, sans os, sans sys)
        safe_globals = {
            "__builtins__": {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "min": min,
                "max": max,
                "sum": sum,
                "round": round,
                "abs": abs,
            },
            "json": json,
            "input": input_data,
            "context": context,
            "payload": context.get("payload", {}),
            "webhook": context.get("webhook", {}),
        }

        try:
            # Évaluation en lecture seule dans un sandbox sécurisé
            result = eval(expr, safe_globals, {})
        except Exception as e:
            raise RuntimeError(f"Erreur d'évaluation dans le nœud Code/Transform: {e}")

        return NodeExecutionResult(output_data=result, active_ports=["main"])


class LoggerNode(BaseNode):
    id = "core.logger"
    name = "Journalisation / Log"
    name_t = "nodes.logger.name"
    category = NodeCategory.DATA
    icon = "description"
    color = "#64748b"
    description = "Consigne des messages ou l'état des données dans le journal d'exécution pour le débogage."
    description_t = "nodes.logger.description"

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", label_t="ports.input", port_type="main")]
        self.outputs = [NodePort(id="main", label="Passerelle", label_t="nodes.logger.ports.output", port_type="main", color="#64748b")]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "message": {
                "type": "string",
                "label": "Message de log",
                "label_t": "nodes.logger.fields.message.label",
                "default": "Trace d'étape: {payload}",
            },
            "level": {
                "type": "select",
                "label": "Niveau",
                "label_t": "nodes.logger.fields.level.label",
                "options": [
                    {"label": "INFO", "value": "info"},
                    {"label": "WARNING", "value": "warning"},
                    {"label": "ERROR", "value": "error"},
                ],
                "default": "info",
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
        raw_msg = config.get("message") or ""
        eval_context = dict(context)
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)
        
        resolved_msg = ExecutionEngine.interpolate_value(raw_msg, eval_context)
        output = {
            "log": resolved_msg,
            "level": config.get("level", "info"),
            "data": input_data,
        }
        return NodeExecutionResult(output_data=output, active_ports=["main"])
