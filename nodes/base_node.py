from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeCategory(str, Enum):
    TRIGGER = "trigger"
    FLOW = "flow"
    DATA = "data"
    INTEGRATION = "integration"
    MODULE = "module"


class NodePort:
    def __init__(
        self,
        id: str,
        label: str,
        port_type: str = "main",
        color: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.id = id
        self.label = label
        self.port_type = port_type  # 'main', 'condition_true', 'condition_false', 'case', 'item'
        self.color = color or "#4f46e5"
        self.description = description or ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.port_type,
            "color": self.color,
            "description": self.description,
        }


class NodeExecutionResult:
    """
    Résultat renvoyé par l'exécution d'un nœud.
    Contient les données produites et la liste des ports sortants actifs à emprunter.
    """

    def __init__(
        self,
        output_data: Any,
        active_ports: Optional[List[str]] = None,
        stop_branch: bool = False,
        error: Optional[str] = None,
    ):
        self.output_data = output_data
        # Si active_ports est None ou vide et qu'on ne stoppe pas la branche, on active 'main' par défaut
        self.active_ports = active_ports if active_ports is not None else (["main"] if not stop_branch else [])
        self.stop_branch = stop_branch
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_data": self.output_data,
            "active_ports": self.active_ports,
            "stop_branch": self.stop_branch,
            "error": self.error,
        }


class BaseNode(ABC):
    """
    Classe de base abstraite pour tous les nœuds du MELODI Automation Engine.
    Permet la composition de graphes de nœuds avancés (n8n-style) et l'exposition
    de nœuds personnalisés par les modules tiers.
    """

    id: str = "base.node"
    name: str = "Nœud de Base"
    category: NodeCategory = NodeCategory.FLOW
    icon: str = "data_object"
    description: str = ""
    color: str = "#4f46e5"

    inputs: List[NodePort] = []
    outputs: List[NodePort] = []

    def __init__(self):
        if not self.inputs:
            # Par défaut, 1 port d'entrée principal 'main' (sauf pour les triggers)
            if self.category != NodeCategory.TRIGGER:
                self.inputs = [NodePort(id="main", label="Entrée", port_type="main")]
            else:
                self.inputs = []

        if not self.outputs:
            # Par défaut, 1 port de sortie principal 'main'
            self.outputs = [NodePort(id="main", label="Sortie", port_type="main")]

    def get_schema(self) -> Dict[str, Any]:
        """
        Retourne le schéma déclaratif des paramètres configurables dans le Builder.
        Chaque champ définit: type, label, default, description, options, required, etc.
        """
        return {}

    @abstractmethod
    async def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Dict[str, Any],
        app: Any,
    ) -> NodeExecutionResult:
        """
        Exécute la logique métier du nœud de manière asynchrone et isolée.

        :param input_data: Données transmises par le(s) nœud(s) parent(s).
        :param config: Configuration personnalisée de ce nœud dans le workflow.
        :param context: Contexte d'exécution global ($workflow, $execution, $steps, $env).
        :param app: Instance de l'application MELODI (accès aux hooks, DB, services).
        :return: NodeExecutionResult avec output_data et active_ports.
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Exporte les métadonnées pour le catalogue et le constructeur visuel."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value if isinstance(self.category, NodeCategory) else str(self.category),
            "icon": self.icon,
            "description": self.description,
            "color": self.color,
            "inputs": [p.to_dict() for p in self.inputs],
            "outputs": [p.to_dict() for p in self.outputs],
            "schema": self.get_schema(),
        }
