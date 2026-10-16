import logging
from typing import Any, Dict, List, Optional, Type
from .base_node import BaseNode, NodeCategory, NodePort


logger = logging.getLogger("melodi.automation.nodes")


class NodeRegistry:
    """
    Catalogue central et registre des nœuds de MELODI Automation Engine.
    Supporte les nœuds intégrés (Trigger, If, Switch, Set, Code, HTTP) et
    les nœuds personnalisés enregistrés par les modules tiers MELODI sans couplage SQL.
    """

    _nodes: Dict[str, BaseNode] = {}
    _initialized: bool = False

    CATEGORIES = [
        {"id": "trigger", "name": "Déclencheurs", "name_t": "categories.trigger", "icon": "bolt", "color": "#eab308"},
        {"id": "flow", "name": "Contrôle de Flux", "name_t": "categories.flow", "icon": "alt_route", "color": "#8b5cf6"},
        {"id": "data", "name": "Données & Code", "name_t": "categories.data", "icon": "data_object", "color": "#10b981"},
        {"id": "integration", "name": "Intégrations & Webhooks", "name_t": "categories.integration", "icon": "hub", "color": "#3b82f6"},
        {"id": "module", "name": "Modules MELODI", "name_t": "categories.module", "icon": "extension", "color": "#4f46e5"},
        {"id": "ai", "name": "Intelligence Artificielle", "name_t": "categories.ai", "icon": "psychology", "color": "#8b5cf6"},
    ]


    @classmethod
    def register(cls, node: BaseNode) -> None:
        """Enregistre une instance de BaseNode."""
        if not isinstance(node, BaseNode):
            raise TypeError(f"Le nœud doit être une instance de BaseNode (reçu: {type(node)})")
        cls._nodes[node.id] = node

    @classmethod
    def unregister(cls, node_id: str) -> bool:
        """Désenregistre un nœud."""
        return cls._nodes.pop(node_id, None) is not None

    @classmethod
    def get(cls, node_id: str) -> Optional[BaseNode]:
        """Récupère un nœud par son identifiant unique."""
        cls.ensure_initialized()
        return cls._nodes.get(node_id)

    @classmethod
    def list_nodes(cls, lang: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retourne la liste complète des métadonnées de tous les nœuds disponibles."""
        cls.ensure_initialized()
        return [node.to_dict(lang=lang) for node in cls._nodes.values()]

    @classmethod
    def get_categories(cls, lang: Optional[str] = None) -> List[Dict[str, Any]]:
        from .base_node import translate_text
        categories = []
        for cat in cls.CATEGORIES:
            cat_copy = dict(cat)
            if lang and cat.get("name_t"):
                cat_copy["name"] = translate_text(cat["name_t"], cat["name"], lang)
            categories.append(cat_copy)
        return categories

    @classmethod
    def ensure_initialized(cls) -> None:
        """Initialise les nœuds natifs de base si non fait."""
        if not cls._initialized:
            cls.register_default_nodes()
            cls._initialized = True

    @classmethod
    def register_default_nodes(cls) -> None:
        """Enregistre tous les nœuds natifs du système d'automatisation."""
        from .builtin.trigger_nodes import EventTriggerNode, WebhookTriggerNode
        from .builtin.flow_nodes import IfElseNode, SwitchNode, IteratorNode, CallWorkflowNode
        from .builtin.data_nodes import SetFieldsNode, CodeTransformNode, LoggerNode
        from .builtin.integration_nodes import HttpRequestNode
        from .builtin.module_action_node import ModuleActionNode
        from .builtin.ai_nodes import AIChatNode, AIAgentNode

        defaults = [
            EventTriggerNode(),
            WebhookTriggerNode(),
            IfElseNode(),
            SwitchNode(),
            IteratorNode(),
            CallWorkflowNode(),
            SetFieldsNode(),
            CodeTransformNode(),
            LoggerNode(),
            HttpRequestNode(),
            ModuleActionNode(),
            AIChatNode(),
            AIAgentNode(),
        ]
        for n in defaults:
            cls.register(n)

    @classmethod
    async def discover_module_nodes(cls, app: Any) -> None:
        """
        Découvre dynamiquement les nœuds personnalisés exposés par les modules tiers
        via le hook MELODI 'automation.expose_nodes'.

        Chaque module qui veut apparaître dans la bibliothèque de nœuds doit enregistrer
        une action 'automation.expose_nodes' retournant une liste de descripteurs de nœuds.

        Le nœud universel 'core.module_action' reste disponible pour tout module
        qui ne déclare pas explicitement ses nœuds.
        """
        cls.ensure_initialized()
        if not app or not hasattr(app, "hook_manager") or not hasattr(app.hook_manager, "action"):
            return

        raw_actions = getattr(app.hook_manager.action, "_actions", {})

        for module_name, mod_actions in list(raw_actions.items()):
            act_name = None
            if "automation.expose_nodes" in mod_actions:
                act_name = "automation.expose_nodes"
            elif "automation.register_nodes" in mod_actions:
                act_name = "automation.register_nodes"
            elif "expose_nodes" in mod_actions:
                act_name = "expose_nodes"

            if not act_name:
                continue

            try:
                custom_nodes_data = await app.hook_manager.action.execute(
                    module_name, act_name, {}
                )
                if isinstance(custom_nodes_data, list):
                    from .base_node import BaseNode
                    for node_data in custom_nodes_data:
                        if isinstance(node_data, BaseNode):
                            cls.register(node_data)
                        elif isinstance(node_data, dict):
                            cls._register_custom_node_dict(node_data, module_name)
                        logger.debug(
                            f"[NodeRegistry] Nœud enregistré depuis {module_name}"
                        )
            except Exception as e:
                logger.warning(f"[NodeRegistry] Erreur découverte nœuds du module {module_name}: {e}")

    @classmethod
    def register_custom_node(cls, data: Dict[str, Any], module_name: Optional[str] = None) -> BaseNode:
        """
        Enregistre publiquement un nœud personnalisé fourni sous forme de dictionnaire
        par un module tiers via le hook 'melodi_automation.register_node'.
        """
        cls.ensure_initialized()
        from .builtin.module_action_node import ModuleActionNode

        mod = module_name or data.get("module") or "custom"
        node_id = data.get("id") or f"{mod}.{data.get('action') or 'action'}"
        node = ModuleActionNode(
            node_id=node_id,
            name=data.get("name") or node_id,
            module_name=mod,
            action_name=data.get("action") or data.get("id"),
            description=data.get("description") or f"Nœud personnalisé du module {mod}",
            schema=data.get("schema") or {},
            icon=data.get("icon") or "extension",
        )
        if "name_t" in data:
            node.name_t = data["name_t"]
        if "description_t" in data:
            node.description_t = data["description_t"]
        if "inputs" in data and isinstance(data["inputs"], list):
            node.inputs = [NodePort(**p) for p in data["inputs"]]
        if "outputs" in data and isinstance(data["outputs"], list):
            node.outputs = [NodePort(**p) for p in data["outputs"]]
        if "color" in data:
            node.color = data["color"]
        if "category" in data:
            cat_val = data["category"]
            if isinstance(cat_val, NodeCategory):
                node.category = cat_val
            elif isinstance(cat_val, str):
                cat_lower = cat_val.lower()
                if cat_lower in ("business", "module", "action"):
                    node.category = NodeCategory.MODULE
                else:
                    try:
                        node.category = NodeCategory(cat_lower)
                    except ValueError:
                        pass

        cls.register(node)
        return node

    @classmethod
    def _register_custom_node_dict(cls, data: Dict[str, Any], module_name: str) -> None:
        """Alias interne pour la découverte de nœuds."""
        cls.register_custom_node(data, module_name)

    @classmethod
    def clear(cls) -> None:
        """Réinitialise le registre (utile pour les tests unitaires)."""
        cls._nodes.clear()
        cls._initialized = False
