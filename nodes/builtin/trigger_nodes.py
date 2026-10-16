from typing import Any, Dict, List
from ..base_node import BaseNode, NodeCategory, NodePort, NodeExecutionResult
from ...services.payload_validator import PayloadValidator


class EventTriggerNode(BaseNode):
    id = "core.trigger_event"
    name = "Déclencheur d'Événement"
    name_t = "triggers.event_name"
    category = NodeCategory.TRIGGER
    icon = "bolt"
    color = "#eab308"
    description = "Déclenche le workflow lorsqu'un événement métier MELODI survient (ex: commande créée, contact ajouté)."
    description_t = "triggers.event_desc"

    def __init__(self):
        self.inputs = []
        self.outputs = [
            NodePort(id="main", label="Valide", label_t="triggers.port_valid", port_type="main", color="#10b981", description="Payload conforme au schéma"),
            NodePort(id="error", label="Erreur", label_t="triggers.port_error", port_type="error", color="#ef4444", description="Payload non conforme"),
        ]
        super().__init__()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "trigger_module": {
                "type": "string",
                "label": "Module source",
                "label_t": "triggers.field_trigger_module",
                "required": True,
                "description": "Nom du module émetteur (ex: commerce, contact, base)",
                "description_t": "triggers.desc_trigger_module",
            },
            "trigger_event": {
                "type": "string",
                "label": "Nom de l'événement",
                "label_t": "triggers.field_trigger_event",
                "required": True,
                "description": "Événement écouté (ex: order.created, contact.created)",
                "description_t": "triggers.desc_trigger_event",
            },
            "validation_mode": {
                "type": "select",
                "label": "Mode de validation du Payload",
                "label_t": "triggers.validation_mode_label",
                "options": [
                    {"label": "Structure stricte (Validation de schéma)", "label_t": "triggers.validation_mode_strict", "value": "strict"},
                    {"label": "Accepter n'importe quelles données (Permissif)", "label_t": "triggers.validation_mode_any", "value": "any"},
                ],
                "default": "strict",
                "description": "En mode strict, tout payload non conforme sera redirigé vers le port de sortie 'error'.",
                "description_t": "triggers.validation_mode_desc",
            },
            "payload_schema": {
                "type": "payload_schema",
                "label": "Structure attendue du Payload",
                "label_t": "triggers.payload_schema_label",
                "description": "Définissez les champs requis et types attendus (ex: order_id en number, customer en object).",
                "description_t": "triggers.payload_schema_desc",
                "default": [],
            },
            "allow_extra_fields": {
                "type": "boolean",
                "label": "Tolérer les champs supplémentaires",
                "label_t": "triggers.allow_extra_fields_label",
                "default": True,
                "description": "Si désactivé en mode strict, les champs non déclarés provoqueront une erreur de validation.",
                "description_t": "triggers.allow_extra_fields_desc",
            },
            "test_payload": {
                "type": "test_payload",
                "label": "Payload de test (Simulation uniquement)",
                "label_t": "triggers.test_payload_label",
                "description": "Données simulées utilisées exclusivement pour tester le workflow dans le Builder. Jamais exécutées en production.",
                "description_t": "triggers.test_payload_desc",
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

        expected_schema = config.get("payload_schema", [])
        validation_mode = config.get("validation_mode") or ("strict" if expected_schema else "any")
        allow_extra = config.get("allow_extra_fields", True)
        custom_types = context.get("custom_types") or []
        lang = context.get("lang") or getattr(app, "default_lang", None) or "fr"

        is_valid, errors, enriched_payload = PayloadValidator.apply_defaults_and_validate(
            payload=payload,
            schema_definition=expected_schema,
            validation_mode=validation_mode,
            allow_extra_fields=allow_extra,
            custom_types=custom_types,
            lang=lang,
        )

        if not is_valid:
            from ...services.payload_validator import _tv
            err_title = _tv(
                "validator.validation_failed",
                default=f"Validation du payload échouée ({len(errors)} erreur(s))",
                context={"count": len(errors)},
                lang=lang,
            )
            error_output = {
                "error": err_title,
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
    name_t = "triggers.webhook_name"
    category = NodeCategory.TRIGGER
    icon = "webhook"
    color = "#06b6d4"
    description = "Déclenche le workflow à la réception d'une requête HTTP externe sur une URL dédiée avec options de sécurisation et méthodes flexibles."
    description_t = "triggers.webhook_desc"

    def __init__(self):
        self.inputs = []
        self.outputs = [
            NodePort(id="main", label="Valide", label_t="triggers.port_valid", port_type="main", color="#10b981", description="Payload conforme au schéma"),
            NodePort(id="error", label="Erreur", label_t="triggers.port_error", port_type="error", color="#ef4444", description="Payload non conforme ou non autorisé"),
        ]
        super().__init__()

    def get_sections(self) -> List[Dict[str, Any]]:
        return [
            {"id": "endpoint", "label": "Point d'Entrée (Endpoint)", "label_t": "triggers.sec_endpoint", "icon": "webhook"},
            {"id": "security", "label": "Sécurité & Authentification", "label_t": "triggers.sec_security", "icon": "shield"},
            {"id": "validation", "label": "Contrat & Validation du Payload", "label_t": "triggers.sec_validation", "icon": "verified"},
            {"id": "test", "label": "Payload de Simulation", "label_t": "triggers.sec_test", "icon": "science"},
        ]

    def get_schema(self) -> Dict[str, Any]:
        return {
            "webhook_token": {
                "type": "string",
                "label": "Jeton d'authentification (URL)",
                "label_t": "triggers.field_webhook_token",
                "section": "endpoint",
                "readonly": True,
                "description": "Token sécurisé unique identifiant ce webhook dans l'URL",
                "description_t": "triggers.desc_webhook_token",
            },
            "method": {
                "type": "select",
                "label": "Méthode HTTP acceptée",
                "label_t": "triggers.field_method",
                "section": "endpoint",
                "options": [
                    {"label": "Toutes (GET, POST, PUT, DELETE, PATCH)", "label_t": "triggers.opt_method_any", "value": "ANY"},
                    {"label": "GET uniquement", "label_t": "triggers.opt_method_get", "value": "GET"},
                    {"label": "POST uniquement", "label_t": "triggers.opt_method_post", "value": "POST"},
                    {"label": "PUT uniquement", "label_t": "triggers.opt_method_put", "value": "PUT"},
                    {"label": "DELETE uniquement", "label_t": "triggers.opt_method_delete", "value": "DELETE"},
                    {"label": "PATCH uniquement", "label_t": "triggers.opt_method_patch", "value": "PATCH"},
                ],
                "default": "ANY",
                "description": "Restreint les méthodes HTTP qui peuvent déclencher ce webhook.",
                "description_t": "triggers.desc_method",
            },
            "security_mode": {
                "type": "select",
                "label": "Protection / Authentification du Webhook",
                "label_t": "triggers.field_security_mode",
                "section": "security",
                "options": [
                    {"label": "Aucune protection additionnelle (Ouvert avec Token URL)", "label_t": "triggers.opt_sec_none", "value": "none"},
                    {"label": "Secret d'En-tête (Header Secret / API Key)", "label_t": "triggers.opt_sec_header", "value": "header_secret"},
                    {"label": "Jeton Paramètre d'URL (Query Secret)", "label_t": "triggers.opt_sec_query", "value": "query_secret"},
                    {"label": "Basic Authentication (Identifiant & Mot de passe)", "label_t": "triggers.opt_sec_basic", "value": "basic_auth"},
                ],
                "default": "none",
                "description": "Ajoute une couche de protection pour empêcher l'exposition publique ou des appels non autorisés.",
                "description_t": "triggers.desc_security_mode",
            },
            "security_header_name": {
                "type": "string",
                "label": "Nom de l'en-tête secret",
                "label_t": "triggers.field_sec_header_name",
                "section": "security",
                "default": "X-Webhook-Secret",
                "description": "Nom de l'en-tête HTTP attendu (ex: X-Webhook-Secret ou X-API-Key)",
                "description_t": "triggers.desc_sec_header_name",
                "display_if": {"field": "security_mode", "operator": "==", "value": "header_secret"},
            },
            "security_header_value": {
                "type": "string",
                "label": "Valeur secrète attendue",
                "label_t": "triggers.field_sec_header_value",
                "section": "security",
                "placeholder": "mon_secret_ultra_securise",
                "description": "Valeur exacte que l'appelant doit fournir dans l'en-tête",
                "description_t": "triggers.desc_sec_header_value",
                "display_if": {"field": "security_mode", "operator": "==", "value": "header_secret"},
            },
            "security_query_name": {
                "type": "string",
                "label": "Nom du paramètre d'URL",
                "label_t": "triggers.field_sec_query_name",
                "section": "security",
                "default": "secret",
                "description": "Nom du paramètre d'URL attendu (ex: ?secret=xxx ou ?api_key=xxx)",
                "description_t": "triggers.desc_sec_query_name",
                "display_if": {"field": "security_mode", "operator": "==", "value": "query_secret"},
            },
            "security_query_value": {
                "type": "string",
                "label": "Valeur du paramètre d'URL",
                "label_t": "triggers.field_sec_query_value",
                "section": "security",
                "placeholder": "mon_secret_url",
                "display_if": {"field": "security_mode", "operator": "==", "value": "query_secret"},
            },
            "security_username": {
                "type": "string",
                "label": "Nom d'utilisateur (Basic Auth)",
                "label_t": "triggers.field_sec_username",
                "section": "security",
                "display_if": {"field": "security_mode", "operator": "==", "value": "basic_auth"},
            },
            "security_password": {
                "type": "string",
                "label": "Mot de passe (Basic Auth)",
                "label_t": "triggers.field_sec_password",
                "section": "security",
                "display_if": {"field": "security_mode", "operator": "==", "value": "basic_auth"},
            },
            "validation_mode": {
                "type": "select",
                "label": "Mode de validation du Payload",
                "label_t": "triggers.validation_mode_label",
                "section": "validation",
                "options": [
                    {"label": "Structure stricte (Validation de schéma)", "label_t": "triggers.validation_mode_strict", "value": "strict"},
                    {"label": "Accepter n'importe quelles données (Permissif)", "label_t": "triggers.validation_mode_any", "value": "any"},
                ],
                "default": "strict",
                "description": "En mode strict, tout payload non conforme sera redirigé vers le port de sortie 'error'.",
                "description_t": "triggers.validation_mode_desc",
            },
            "payload_schema": {
                "type": "payload_schema",
                "label": "Structure attendue du Payload",
                "label_t": "triggers.payload_schema_label",
                "section": "validation",
                "display_if": {"field": "validation_mode", "operator": "==", "value": "strict"},
                "description": "Définissez les champs requis et types attendus (ex: order_id en number, customer en object).",
                "description_t": "triggers.payload_schema_desc",
                "default": [],
            },
            "allow_extra_fields": {
                "type": "boolean",
                "label": "Tolérer les champs supplémentaires",
                "label_t": "triggers.allow_extra_fields_label",
                "section": "validation",
                "default": True,
                "description": "Si désactivé en mode strict, les champs non déclarés provoqueront une erreur de validation.",
                "description_t": "triggers.allow_extra_fields_desc",
            },
            "test_payload": {
                "type": "test_payload",
                "label": "Payload de test (Simulation uniquement)",
                "label_t": "triggers.test_payload_label",
                "section": "test",
                "description": "Données simulées utilisées exclusivement pour tester le workflow dans le Builder. Jamais exécutées en production.",
                "description_t": "triggers.test_payload_desc",
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
        # Vérification de la méthode HTTP si précisée
        webhook_req = context.get("webhook") or {}
        req_method = str(webhook_req.get("method") or "").upper()
        allowed_method = str(config.get("method") or "ANY").upper()
        if allowed_method and allowed_method != "ANY" and req_method and req_method != allowed_method:
            error_output = {
                "error": f"Méthode HTTP non autorisée : '{req_method}'. Méthode requise : '{allowed_method}'.",
                "method_received": req_method,
                "method_expected": allowed_method,
            }
            return NodeExecutionResult(
                output_data=error_output,
                active_ports=["error"],
            )

        # Vérification de la sécurité / protection configurée
        security_mode = str(config.get("security_mode") or "none").lower()
        if security_mode == "header_secret":
            header_name = str(config.get("security_header_name") or "X-Webhook-Secret").lower()
            expected_secret = str(config.get("security_header_value") or "")
            req_headers = {str(k).lower(): str(v) for k, v in (webhook_req.get("headers") or {}).items()}
            received_secret = req_headers.get(header_name, "")
            if not expected_secret or received_secret != expected_secret:
                return NodeExecutionResult(
                    output_data={"error": "Accès refusé : secret d'en-tête invalide ou manquant.", "header": header_name},
                    active_ports=["error"],
                )

        elif security_mode == "query_secret":
            query_name = str(config.get("security_query_name") or "secret")
            expected_val = str(config.get("security_query_value") or "")
            req_query = webhook_req.get("query") or {}
            received_val = str(req_query.get(query_name) or "")
            if not expected_val or received_val != expected_val:
                return NodeExecutionResult(
                    output_data={"error": "Accès refusé : paramètre d'URL de protection invalide ou manquant.", "param": query_name},
                    active_ports=["error"],
                )

        elif security_mode == "basic_auth":
            exp_user = str(config.get("security_username") or "")
            exp_pass = str(config.get("security_password") or "")
            req_headers = {str(k).lower(): str(v) for k, v in (webhook_req.get("headers") or {}).items()}
            auth_header = req_headers.get("authorization", "")
            authorized = False
            if auth_header.startswith("Basic "):
                import base64
                try:
                    decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
                    u, p = decoded.split(":", 1)
                    if u == exp_user and p == exp_pass:
                        authorized = True
                except Exception:
                    authorized = False
            if not authorized:
                return NodeExecutionResult(
                    output_data={"error": "Accès refusé : Authentification Basic invalide."},
                    active_ports=["error"],
                )

        payload = context.get("payload")
        if payload is None:
            payload = input_data if input_data is not None else {}

        expected_schema = config.get("payload_schema", [])
        validation_mode = config.get("validation_mode") or ("strict" if expected_schema else "any")
        allow_extra = config.get("allow_extra_fields", True)
        custom_types = context.get("custom_types") or []
        lang = context.get("lang") or getattr(app, "default_lang", None) or "fr"

        is_valid, errors, enriched_payload = PayloadValidator.apply_defaults_and_validate(
            payload=payload,
            schema_definition=expected_schema,
            validation_mode=validation_mode,
            allow_extra_fields=allow_extra,
            custom_types=custom_types,
            lang=lang,
        )

        if not is_valid:
            from ...services.payload_validator import _tv
            err_title = _tv(
                "validator.validation_failed",
                default=f"Validation du payload échouée ({len(errors)} erreur(s))",
                context={"count": len(errors)},
                lang=lang,
            )
            error_output = {
                "error": err_title,
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

        # Enrichissement du contexte n8n-style avec métadonnées de la requête HTTP
        if isinstance(webhook_req, dict) and webhook_req:
            context["$request"] = {
                "query": webhook_req.get("query") or {},
                "headers": webhook_req.get("headers") or {},
                "method": webhook_req.get("method") or "POST",
                "body": webhook_req.get("body") or {},
            }
            context["$json"] = enriched_payload

        return NodeExecutionResult(
            output_data=enriched_payload,
            active_ports=["main"],
        )
