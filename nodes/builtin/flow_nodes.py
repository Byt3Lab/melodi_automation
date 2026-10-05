from typing import Any, Dict, List
from ..base_node import BaseNode, NodeCategory, NodePort, NodeExecutionResult
from ...services.condition_engine import ConditionEngine


class IfElseNode(BaseNode):
    id = "core.if_else"
    name = "Branchement Si / Sinon (If / Else)"
    category = NodeCategory.FLOW
    icon = "alt_route"
    color = "#8b5cf6"
    description = "Évalue une ou plusieurs conditions et sépare le flux vers la branche Vrai ou Faux."

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", port_type="main")]
        self.outputs = [
            NodePort(id="true", label="Vrai (True)", port_type="condition_true", color="#10b981", description="Condition remplie"),
            NodePort(id="false", label="Faux (False)", port_type="condition_false", color="#ef4444", description="Condition non remplie"),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "logic": {
                "type": "select",
                "label": "Combinateur logique",
                "options": [
                    {"label": "Toutes les règles (ET / AND)", "value": "AND"},
                    {"label": "Au moins une règle (OU / OR)", "value": "OR"},
                ],
                "default": "AND",
            },
            "rules": {
                "type": "array",
                "label": "Règles d'évaluation",
                "item_schema": {
                    "field": {"type": "string", "label": "Champ (ex: payload.total)", "required": True},
                    "operator": {"type": "select", "label": "Opérateur", "options": [
                        {"label": "Égal à (==)", "value": "=="},
                        {"label": "Différent de (!=)", "value": "!="},
                        {"label": "Supérieur à (>)", "value": ">"},
                        {"label": "Supérieur ou égal (>=)", "value": ">="},
                        {"label": "Inférieur à (<)", "value": "<"},
                        {"label": "Inférieur ou égal (<=)", "value": "<="},
                        {"label": "Contient (contains)", "value": "contains"},
                        {"label": "Commence par (starts_with)", "value": "starts_with"},
                        {"label": "Se termine par (ends_with)", "value": "ends_with"},
                        {"label": "Est vide ou nul (is_empty)", "value": "is_empty"},
                        {"label": "N'est pas vide (is_not_empty)", "value": "is_not_empty"},
                    ]},
                    "value": {"type": "string", "label": "Valeur attendue"},
                },
                "default": [],
            },
        }

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        # Fusion du contexte avec la donnée du nœud prédécesseur
        eval_context = dict(context)
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)
            # Permet également d'accéder directement aux champs de input_data si non préfixés
            for k, v in input_data.items():
                if k not in eval_context:
                    eval_context[k] = v

        result_bool = ConditionEngine.evaluate(config, eval_context)
        active_port = "true" if result_bool else "false"

        output = {
            "condition_met": result_bool,
            "data": input_data,
        }
        return NodeExecutionResult(output_data=output, active_ports=[active_port])


class SwitchNode(BaseNode):
    id = "core.switch"
    name = "Aiguillage Multiple (Switch)"
    category = NodeCategory.FLOW
    icon = "shuffle"
    color = "#a855f7"
    description = "Achemine les données vers différentes branches selon la valeur d'un champ ou expression."

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", port_type="main")]
        self.outputs = [
            NodePort(id="case_1", label="Cas 1", port_type="case", color="#3b82f6"),
            NodePort(id="case_2", label="Cas 2", port_type="case", color="#ec4899"),
            NodePort(id="default", label="Par défaut", port_type="case", color="#64748b"),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "field": {
                "type": "string",
                "label": "Champ à tester",
                "required": True,
                "description": "Variable à évaluer (ex: payload.status ou input.type)",
            },
            "cases": {
                "type": "array",
                "label": "Cas possibles",
                "item_schema": {
                    "id": {"type": "string", "label": "Identifiant de branche (ex: case_1)", "required": True},
                    "label": {"type": "string", "label": "Libellé"},
                    "operator": {"type": "select", "label": "Opérateur", "options": [
                        {"label": "Égal à (==)", "value": "=="},
                        {"label": "Contient (contains)", "value": "contains"},
                        {"label": "Commence par", "value": "starts_with"},
                    ]},
                    "value": {"type": "string", "label": "Valeur attendue"},
                },
                "default": [
                    {"id": "case_1", "label": "Payé", "operator": "==", "value": "paid"},
                    {"id": "case_2", "label": "Annulé", "operator": "==", "value": "cancelled"},
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
        field_path = config.get("field", "")
        cases = config.get("cases") or []

        eval_context = dict(context)
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)
            for k, v in input_data.items():
                if k not in eval_context:
                    eval_context[k] = v

        val = ConditionEngine.resolve_path(eval_context, field_path)
        matched_port = "default"

        for case in cases:
            case_id = case.get("id") or "default"
            op = case.get("operator", "==")
            exp_val = case.get("value")
            
            rule = {"field": field_path, "operator": op, "value": exp_val}
            if ConditionEngine.compare(val, op, exp_val):
                matched_port = case_id
                break

        output = {
            "matched_case": matched_port,
            "evaluated_value": val,
            "data": input_data,
        }
        return NodeExecutionResult(output_data=output, active_ports=[matched_port])


class IteratorNode(BaseNode):
    id = "core.iterator"
    name = "Boucle / Itérateur (Loop)"
    category = NodeCategory.FLOW
    icon = "loop"
    color = "#3b82f6"
    description = "Parcourt une liste d'éléments et exécute les nœuds suivants pour chaque élément."

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", port_type="main")]
        self.outputs = [
            NodePort(id="item", label="Élément courant", port_type="item", color="#3b82f6", description="Émis pour chaque item"),
            NodePort(id="done", label="Terminé", port_type="main", color="#10b981", description="Émis à la fin de la boucle"),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "field": {
                "type": "string",
                "label": "Champ de la liste",
                "required": True,
                "description": "Chemin vers le tableau à parcourir (ex: payload.items ou input.records)",
            },
        }

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        field_path = config.get("field", "")
        eval_context = dict(context)
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)

        items_list = ConditionEngine.resolve_path(eval_context, field_path)
        if not isinstance(items_list, list):
            items_list = [items_list] if items_list is not None else []

        output = {
            "items": items_list,
            "count": len(items_list),
        }
        # Par défaut, active les deux ports item et done pour permettre le parcours
        return NodeExecutionResult(output_data=output, active_ports=["item", "done"])


class CallWorkflowNode(BaseNode):
    id = "core.call_workflow"
    name = "Appeler un Sub-Workflow"
    category = NodeCategory.FLOW
    icon = "account_tree"
    color = "#8b5cf6"
    description = "Exécute un autre workflow de façon synchrone ou asynchrone avec protection contre les boucles récursives."

    def __init__(self):
        self.inputs = [NodePort(id="main", label="Entrée", port_type="main")]
        self.outputs = [
            NodePort(id="main", label="Succès", port_type="main", color="#10b981", description="Emprunté si le sub-workflow réussit"),
            NodePort(id="error", label="Erreur / Boucle", port_type="error", color="#ef4444", description="Emprunté en cas d'erreur ou de récursion bloquée"),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "workflow_id": {
                "type": "string",
                "label": "ID du Workflow Cible",
                "required": True,
                "description": "Identifiant UUID du workflow à sous-traiter (ex: 89ead3b2-... ou {payload.target_wf_id})",
            },
            "payload_mode": {
                "type": "select",
                "label": "Mode de transmission du Payload",
                "options": [
                    {"label": "Hériter du payload courant (inherit)", "value": "inherit"},
                    {"label": "Payload personnalisé JSON (custom)", "value": "custom"},
                ],
                "default": "inherit",
            },
            "custom_payload": {
                "type": "json",
                "label": "Payload Personnalisé (si mode custom)",
                "description": "JSON envoyé comme données d'entrée au sub-workflow.",
                "default": {},
            },
            "wait_for_completion": {
                "type": "boolean",
                "label": "Attendre la fin de l'exécution (Synchrone)",
                "description": "Si activé, attend le résultat du sous-workflow avant de continuer.",
                "default": True,
            },
            "max_depth": {
                "type": "number",
                "label": "Profondeur d'appels maximale",
                "description": "Nombre maximum d'appels imbriqués autorisés (défaut: 5, max: 10).",
                "default": 5,
            },
        }

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        from ...repositories.workflow_repository import WorkflowRepository
        from ...services.execution_engine import ExecutionEngine

        wf_id_raw = config.get("workflow_id", "")
        if not wf_id_raw:
            return NodeExecutionResult(
                output_data={"error": "ID du workflow cible non spécifié.", "data": input_data},
                active_ports=["error"],
            )

        # Interpolation de l'ID du workflow
        target_wf_id = str(ExecutionEngine.interpolate_value(wf_id_raw, context)).strip()

        # Récupération de la pile d'exécution courante
        current_stack = list(context.get("_execution_stack") or [])

        # 1. Vérification anti-boucle (récursion directe ou circulaire)
        if target_wf_id in current_stack:
            err_msg = (
                f"Boucle récursive détectée ! Le workflow '{target_wf_id}' "
                f"est déjà présent dans la pile d'exécution ({current_stack}). Appel interrompu."
            )
            return NodeExecutionResult(
                output_data={"error": err_msg, "recursion_detected": True, "target_workflow_id": target_wf_id},
                active_ports=["error"],
            )

        # 2. Vérification de la limite de profondeur d'appels
        max_depth = int(config.get("max_depth") or 5)
        if len(current_stack) >= max_depth:
            err_msg = (
                f"Profondeur maximale d'appels atteinte ({len(current_stack)}/{max_depth}). "
                f"L'appel du workflow '{target_wf_id}' est interrompu."
            )
            return NodeExecutionResult(
                output_data={"error": err_msg, "max_depth_exceeded": True, "current_depth": len(current_stack)},
                active_ports=["error"],
            )

        # 3. Chargement du sub-workflow depuis la BDD
        async with app.db.get_session() as session:
            target_workflow = await WorkflowRepository.get_workflow_by_id(session, target_wf_id)

        if not target_workflow:
            return NodeExecutionResult(
                output_data={"error": f"Workflow cible '{target_wf_id}' introuvable.", "target_workflow_id": target_wf_id},
                active_ports=["error"],
            )

        if not target_workflow.active:
            return NodeExecutionResult(
                output_data={"error": f"Le workflow cible '{target_wf_id}' est inactif.", "target_workflow_id": target_wf_id},
                active_ports=["error"],
            )

        # 4. Préparation du payload
        payload_mode = config.get("payload_mode", "inherit")
        if payload_mode == "custom":
            raw_custom = config.get("custom_payload") or {}
            target_payload = ExecutionEngine.interpolate_value(raw_custom, context)
        else:
            target_payload = dict(input_data) if isinstance(input_data, dict) else input_data

        # 5. Construction du sous-contexte avec propagation de _execution_stack
        new_stack = current_stack + [target_wf_id]
        sub_context = {
            "payload": target_payload,
            "_execution_stack": new_stack,
        }

        # 6. Exécution du sub-workflow
        wait_for_completion = config.get("wait_for_completion", True)
        if wait_for_completion:
            res = await ExecutionEngine.execute(target_workflow, sub_context, app)
            if res.get("status") == "success":
                output = {
                    "sub_workflow_id": target_wf_id,
                    "execution_id": res.get("execution_id"),
                    "duration_ms": res.get("duration_ms"),
                    "output": res.get("context", {}).get("last_output"),
                    "steps": res.get("steps", {}),
                }
                return NodeExecutionResult(output_data=output, active_ports=["main"])
            else:
                output = {
                    "sub_workflow_id": target_wf_id,
                    "execution_id": res.get("execution_id"),
                    "error": res.get("error"),
                }
                return NodeExecutionResult(output_data=output, active_ports=["error"])
        else:
            import asyncio
            asyncio.create_task(ExecutionEngine.execute(target_workflow, sub_context, app))
            output = {
                "sub_workflow_id": target_wf_id,
                "status": "triggered_async",
            }
            return NodeExecutionResult(output_data=output, active_ports=["main"])

