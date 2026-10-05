from typing import Any, Dict
from ..base_node import BaseNode, NodeCategory, NodePort, NodeExecutionResult
from ...services.payload_validator import PayloadValidator


class EventTriggerNode(BaseNode):
    id = "core.trigger_event"
    name = "Déclencheur d'Événement"
    category = NodeCategory.TRIGGER
    icon = "bolt"
    color = "#eab308"
    description = "Déclenche le workflow lorsqu'un événement métier MELODI survient (ex: commande créée, contact ajouté)."

    def __init__(self):
        self.inputs = []
        self.outputs = [
            NodePort(id="main", label="Valide", port_type="main", color="#10b981", description="Payload conforme au schéma"),
            NodePort(id="error", label="Erreur", port_type="error", color="#ef4444", description="Payload non conforme"),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "trigger_module": {
                "type": "string",
                "label": "Module source",
                "required": True,
                "description": "Nom du module émetteur (ex: commerce, contact, base)",
            },
            "trigger_event": {
                "type": "string",
                "label": "Nom de l'événement",
                "required": True,
                "description": "Événement écouté (ex: order.created, contact.created)",
            },
            "validation_mode": {
                "type": "select",
                "label": "Mode de validation du Payload",
                "options": [
                    {"label": "Accepter n'importe quelles données (Permissif)", "value": "any"},
                    {"label": "Structure stricte (Validation de schéma)", "value": "strict"},
                ],
                "default": "any",
                "description": "En mode strict, tout payload non conforme sera redirigé vers le port de sortie 'error'.",
            },
            "payload_schema": {
                "type": "payload_schema",
                "label": "Structure attendue du Payload",
                "description": "Définissez les champs requis et types attendus (ex: order_id en number, customer en object).",
                "default": [],
            },
            "allow_extra_fields": {
                "type": "boolean",
                "label": "Tolérer les champs supplémentaires",
                "default": True,
                "description": "Si désactivé en mode strict, les champs non déclarés provoqueront une erreur de validation.",
            },
            "test_payload": {
                "type": "test_payload",
                "label": "Payload de test (Simulation uniquement)",
                "description": "Données simulées utilisées exclusivement pour tester le workflow dans le Builder. Jamais exécutées en production.",
                "default": {},
            },
        }

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        payload = context.get("payload")
        if payload is None:
            payload = input_data if input_data is not None else {}

        validation_mode = config.get("validation_mode", "any")
        expected_schema = config.get("payload_schema", [])
        allow_extra = config.get("allow_extra_fields", True)

        is_valid, errors, enriched_payload = PayloadValidator.apply_defaults_and_validate(
            payload=payload,
            schema_definition=expected_schema,
            validation_mode=validation_mode,
            allow_extra_fields=allow_extra,
        )

        if not is_valid:
            error_output = {
                "error": f"Validation du payload échouée ({len(errors)} erreur(s))",
                "validation_errors": errors,
                "raw_payload": payload,
            }
            return NodeExecutionResult(
                output_data=error_output,
                active_ports=["error"],
            )

        context["payload"] = enriched_payload
        if isinstance(enriched_payload, dict):
            for k, v in enriched_payload.items():
                if k not in context:
                    context[k] = v

        return NodeExecutionResult(
            output_data=enriched_payload,
            active_ports=["main"],
        )


class WebhookTriggerNode(BaseNode):
    id = "core.trigger_webhook"
    name = "Déclencheur Webhook"
    category = NodeCategory.TRIGGER
    icon = "webhook"
    color = "#06b6d4"
    description = "Déclenche le workflow à la réception d'une requête HTTP externe sur une URL dédiée."

    def __init__(self):
        self.inputs = []
        self.outputs = [
            NodePort(id="main", label="Valide", port_type="main", color="#10b981", description="Payload conforme au schéma"),
            NodePort(id="error", label="Erreur", port_type="error", color="#ef4444", description="Payload non conforme"),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "webhook_token": {
                "type": "string",
                "label": "Jeton d'authentification",
                "readonly": True,
                "description": "Token sécurisé unique identifiant ce webhook",
            },
            "method": {
                "type": "select",
                "label": "Méthode HTTP acceptée",
                "options": [
                    {"label": "Toutes (GET, POST, PUT, DELETE)", "value": "ANY"},
                    {"label": "POST uniquement", "value": "POST"},
                    {"label": "GET uniquement", "value": "GET"},
                ],
                "default": "ANY",
            },
            "validation_mode": {
                "type": "select",
                "label": "Mode de validation du Payload",
                "options": [
                    {"label": "Accepter n'importe quelles données (Permissif)", "value": "any"},
                    {"label": "Structure stricte (Validation de schéma)", "value": "strict"},
                ],
                "default": "any",
                "description": "En mode strict, tout payload non conforme sera redirigé vers le port de sortie 'error'.",
            },
            "payload_schema": {
                "type": "payload_schema",
                "label": "Structure attendue du Payload",
                "description": "Définissez les champs requis et types attendus (ex: order_id en number, customer en object).",
                "default": [],
            },
            "allow_extra_fields": {
                "type": "boolean",
                "label": "Tolérer les champs supplémentaires",
                "default": True,
                "description": "Si désactivé en mode strict, les champs non déclarés provoqueront une erreur de validation.",
            },
            "test_payload": {
                "type": "test_payload",
                "label": "Payload de test (Simulation uniquement)",
                "description": "Données simulées utilisées exclusivement pour tester le workflow dans le Builder. Jamais exécutées en production.",
                "default": {},
            },
        }

    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        payload = context.get("payload")
        if payload is None:
            payload = input_data if input_data is not None else {}

        validation_mode = config.get("validation_mode", "any")
        expected_schema = config.get("payload_schema", [])
        allow_extra = config.get("allow_extra_fields", True)

        is_valid, errors, enriched_payload = PayloadValidator.apply_defaults_and_validate(
            payload=payload,
            schema_definition=expected_schema,
            validation_mode=validation_mode,
            allow_extra_fields=allow_extra,
        )

        if not is_valid:
            error_output = {
                "error": f"Validation du payload échouée ({len(errors)} erreur(s))",
                "validation_errors": errors,
                "raw_payload": payload,
            }
            return NodeExecutionResult(
                output_data=error_output,
                active_ports=["error"],
            )

        context["payload"] = enriched_payload
        if isinstance(enriched_payload, dict):
            for k, v in enriched_payload.items():
                if k not in context:
                    context[k] = v

        return NodeExecutionResult(
            output_data=enriched_payload,
            active_ports=["main"],
        )
