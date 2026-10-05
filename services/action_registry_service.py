import inspect
from typing import Any, Dict, List, Optional


class ActionRegistryService:
    """
    Service de découverte et d'introspection des Actions et Événements disponibles dans MELODI.
    """

    # Schémas connus ou enrichis pour des actions standards de l'ERP
    KNOWN_ACTION_SCHEMAS: Dict[str, Dict[str, Any]] = {
        "notification.create": {
            "name": "Créer une Notification",
            "description": "Envoie ou enregistre une notification système / utilisateur",
            "parameters": {
                "title": {"type": "string", "required": True, "description": "Titre du message"},
                "message": {"type": "string", "required": True, "description": "Corps de la notification"},
                "recipient": {"type": "string", "required": False, "description": "Destinataire ou rôle"},
                "level": {"type": "string", "required": False, "default": "info", "description": "Niveau (info, warning, error)"},
            },
        },
        "notification.send_email": {
            "name": "Envoyer un Email",
            "description": "Envoie un email via le service de messagerie MELODI",
            "parameters": {
                "to": {"type": "string", "required": True, "description": "Adresse destinataire"},
                "subject": {"type": "string", "required": True, "description": "Objet de l'email"},
                "body": {"type": "string", "required": True, "description": "Corps HTML ou texte"},
            },
        },
    }

    @classmethod
    def get_available_actions(cls, app: Any) -> List[Dict[str, Any]]:
        """
        Découvre dynamiquement toutes les actions enregistrées auprès de app.hook_manager.action.
        """
        actions_list = []
        if not app or not hasattr(app, "hook_manager") or not hasattr(app.hook_manager, "action"):
            return actions_list

        raw_actions = getattr(app.hook_manager.action, "_actions", {})

        for module_name, mod_actions in raw_actions.items():
            for action_name, func in mod_actions.items():
                action_id = f"{module_name}.{action_name}"

                # Détermination du schéma si déjà connu
                schema = cls.KNOWN_ACTION_SCHEMAS.get(action_id, {})

                # Introspection Python de la fonction
                doc = inspect.getdoc(func) or schema.get("description") or f"Action {action_name} de {module_name}"
                params_info = {}

                if "parameters" in schema:
                    params_info = schema["parameters"]
                else:
                    # Introspection générique
                    try:
                        sig = inspect.signature(func)
                        for param_name, param in sig.parameters.items():
                            if param_name in ("self", "cls"):
                                continue
                            param_type = "string"
                            if param.annotation != inspect.Parameter.empty:
                                if hasattr(param.annotation, "__name__"):
                                    param_type = param.annotation.__name__
                                else:
                                    param_type = str(param.annotation)

                            is_required = param.default == inspect.Parameter.empty
                            default_val = None if is_required else param.default

                            params_info[param_name] = {
                                "type": param_type,
                                "required": is_required,
                                "default": default_val,
                            }
                    except Exception:
                        params_info = {"payload": {"type": "object", "required": True}}

                actions_list.append({
                    "id": action_id,
                    "module": module_name,
                    "action": action_name,
                    "name": schema.get("name") or f"{module_name}: {action_name.replace('_', ' ').title()}",
                    "description": doc,
                    "parameters": params_info,
                })

        return sorted(actions_list, key=lambda x: x["id"])

    @classmethod
    def get_available_events(cls, app: Any) -> List[Dict[str, Any]]:
        """
        Découvre les événements enregistrés ou configurables dans MELODI.
        """
        events_list = []
        if not app:
            return events_list

        # 1. Événements issus des listeners actifs
        if hasattr(app, "hook_manager") and hasattr(app.hook_manager, "event_listener"):
            raw_events = getattr(app.hook_manager.event_listener, "_events", {})
            for mod, events in raw_events.items():
                for ev_name in events.keys():
                    events_list.append({
                        "id": f"{mod}.{ev_name}",
                        "module": mod,
                        "event": ev_name,
                        "label": f"{mod}.{ev_name}",
                    })

        # 2. Ajout des événements standards connus de l'ERP s'ils ne sont pas déjà présents
        standard_events = [
            ("commerce", "order.created", "Nouvelle commande créée"),
            ("commerce", "order.paid", "Commande réglée"),
            ("melodi_retail", "sale_completed", "Vente POS terminée"),
            ("melodi_invoicing", "invoice_posted", "Facture validée"),
            ("melodi_wallet", "WalletFunded", "Portefeuille approvisionné"),
            ("melodi_wallet", "WalletWithdrawn", "Retrait de portefeuille"),
            ("melodi_product", "on_product_created", "Nouveau produit créé"),
            ("melodi_product", "on_product_updated", "Fiche produit modifiée"),
        ]

        existing_ids = {e["id"] for e in events_list}
        for mod, ev, label in standard_events:
            full_id = f"{mod}.{ev}"
            if full_id not in existing_ids:
                events_list.append({
                    "id": full_id,
                    "module": mod,
                    "event": ev,
                    "label": f"{full_id} ({label})",
                })

        return sorted(events_list, key=lambda x: x["id"])

    @classmethod
    async def get_available_nodes(cls, app: Any) -> List[Dict[str, Any]]:
        """
        Découvre et retourne tous les nœuds disponibles (intégrés + exposés par les modules tiers).
        """
        from ..nodes.registry import NodeRegistry
        await NodeRegistry.discover_module_nodes(app)
        return NodeRegistry.list_nodes()
