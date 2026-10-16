from typing import Any, Dict, Optional
from ..base_node import BaseNode, NodeCategory, NodePort, NodeExecutionResult


class ModuleActionNode(BaseNode):
    """
    Nœud universel permettant d'exécuter une action métier exposée par un module MELODI
    (ex: commerce, wallet, notification, base, crm, stock).
    """

    id = "core.module_action"
    name = "Action Module MELODI"
    name_t = "nodes.module_action.name"
    category = NodeCategory.MODULE
    icon = "extension"
    color = "#4f46e5"
    description = "Exécute une action métier enregistrée auprès du Hook System de MELODI."
    description_t = "nodes.module_action.description"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        module_name: Optional[str] = None,
        action_name: Optional[str] = None,
        description: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        icon: Optional[str] = None,
    ):
        if node_id:
            self.id = node_id
        if name:
            self.name = name
        if description:
            self.description = description
        if icon:
            self.icon = icon

        self.module_name = module_name
        self.action_name = action_name
        self._schema = schema or {}

        self.inputs = [NodePort(id="main", label="Entrée", label_t="ports.input", port_type="main")]
        self.outputs = [NodePort(id="main", label="Résultat", label_t="nodes.module_action.ports.output", port_type="main", color="#4f46e5")]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        if self.module_name and self.action_name:
            return self._schema

        base_schema = {
            "module": {
                "type": "string",
                "label": "Module MELODI",
                "label_t": "nodes.module_action.fields.module.label",
                "required": True,
                "default": self.module_name or "",
            },
            "action": {
                "type": "string",
                "label": "Action à exécuter",
                "label_t": "nodes.module_action.fields.action.label",
                "required": True,
                "default": self.action_name or "",
            },
            "parameters": {
                "type": "json",
                "label": "Paramètres de l'action",
                "label_t": "nodes.module_action.fields.parameters.label",
                "description": "Dictionnaire des paramètres passés à l'action. Supporte les variables {payload.id}",
                "description_t": "nodes.module_action.fields.parameters.description",
                "default": {},
            },
        }
        if self._schema:
            base_schema["parameters_schema"] = self._schema
        return base_schema

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        from ...services.execution_engine import ExecutionEngine

        fixed_action = bool(self.module_name and self.action_name)
        mod = self.module_name if fixed_action else (config.get("module") or self.module_name)
        act = self.action_name if fixed_action else (config.get("action") or self.action_name)

        if not mod or not act:
            raise ValueError("Module et Action sont requis pour exécuter ce nœud.")

        eval_context = dict(context)
        eval_context["context"] = context
        if isinstance(input_data, dict):
            eval_context.setdefault("input", input_data)
            for k, v in input_data.items():
                if k not in eval_context:
                    eval_context[k] = v

        if fixed_action:
            raw_params = config or (input_data if isinstance(input_data, dict) else {})
            resolved_payload = ExecutionEngine.interpolate_value(raw_params, eval_context)
        else:
            raw_params = config.get("parameters") or {}
            if not raw_params and isinstance(input_data, dict):
                resolved_payload = input_data
            else:
                resolved_payload = ExecutionEngine.interpolate_value(raw_params, eval_context)

        # Exécution sans couplage via app.hook_manager.action.execute
        result = await app.hook_manager.action.execute(mod, act, resolved_payload)
        output = result if isinstance(result, dict) else {"result": result}
        active_ports = output.pop("_active_ports", ["main"])

        return NodeExecutionResult(output_data=output, active_ports=active_ports)
