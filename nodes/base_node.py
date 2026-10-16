import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from core.utils.translation import Translation, t as core_t

_automation_translation: Optional[Translation] = None

def _get_translation_engine() -> Optional[Translation]:
    global _automation_translation
    if _automation_translation is None:
        module_dir = os.path.dirname(os.path.dirname(__file__))
        lang_dir = os.path.join(module_dir, "langs")
        if os.path.exists(lang_dir):
            _automation_translation = Translation(path_dir=lang_dir, default_lang="fr")
    return _automation_translation

def translate_text(key: Optional[str], default: Any, lang: Optional[str] = None) -> Any:
    """
    Traduit une clé en utilisant le moteur de traduction du module melodi_automation,
    avec fallback transparent sur le moteur global du core (core/utils).
    """
    if not key or not lang:
        return default
    engine = _get_translation_engine()
    if engine:
        res = engine.t(key, default=default, lang=lang)
        if res != key:
            return res
    return core_t(key, default=default, lang=lang)


class NodeCategory(str, Enum):
    TRIGGER = "trigger"
    FLOW = "flow"
    DATA = "data"
    INTEGRATION = "integration"
    MODULE = "module"
    AI = "ai"



class NodePort:
    def __init__(
        self,
        id: str,
        label: str,
        port_type: str = "main",
        color: Optional[str] = None,
        description: Optional[str] = None,
        label_t: Optional[str] = None,
        description_t: Optional[str] = None,
    ):
        self.id = id
        self.label = label
        self.label_t = label_t
        self.port_type = port_type  # 'main', 'condition_true', 'condition_false', 'case', 'item'
        self.color = color or "#4f46e5"
        self.description = description or ""
        self.description_t = description_t

    def to_dict(self, lang: Optional[str] = None) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": translate_text(self.label_t, self.label, lang),
            "label_t": self.label_t,
            "type": self.port_type,
            "color": self.color,
            "description": translate_text(self.description_t, self.description, lang),
            "description_t": self.description_t,
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
    name_t: Optional[str] = None
    category: NodeCategory = NodeCategory.FLOW
    icon: str = "data_object"
    description: str = ""
    description_t: Optional[str] = None
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

    def get_sections(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste ordonnée des sections / groupes d'options pour l'inspecteur.
        Chaque section définit: id, label, icon (optionnel), description (optionnel), label_t (optionnel).
        """
        return []

    def get_schema(self) -> Dict[str, Any]:
        """
        Retourne le schéma déclaratif des paramètres configurables dans le Builder.
        Chaque champ définit: type, label, label_t, default, description, description_t, options, required, display_if, section, etc.
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

    def to_dict(self, lang: Optional[str] = None) -> Dict[str, Any]:
        """Exporte les métadonnées pour le catalogue et le constructeur visuel."""
        # 1. Traduction des sections
        translated_sections = []
        for sec in self.get_sections():
            sec_copy = dict(sec)
            sec_copy["label"] = translate_text(sec.get("label_t"), sec.get("label", sec.get("id")), lang)
            if "description" in sec_copy or "description_t" in sec_copy:
                sec_copy["description"] = translate_text(sec.get("description_t"), sec.get("description", ""), lang)
            translated_sections.append(sec_copy)

        # 2. Traduction récursive des champs du schéma
        def _translate_field_dict(field_def: Any, f_key: str = "") -> Any:
            if not isinstance(field_def, dict):
                return field_def
            field_copy = dict(field_def)
            # Traduction du label du champ
            if "label" in field_copy or "label_t" in field_copy:
                field_copy["label"] = translate_text(field_copy.get("label_t"), field_copy.get("label", f_key), lang)
            # Traduction de la description du champ
            if "description" in field_copy or "description_t" in field_copy:
                field_copy["description"] = translate_text(field_copy.get("description_t"), field_copy.get("description", ""), lang)
            # Traduction des options si présentes
            if "options" in field_copy and isinstance(field_copy["options"], list):
                translated_opts = []
                for opt in field_copy["options"]:
                    if isinstance(opt, dict):
                        opt_copy = dict(opt)
                        opt_copy["label"] = translate_text(opt.get("label_t"), opt.get("label", str(opt.get("value"))), lang)
                        translated_opts.append(opt_copy)
                    else:
                        translated_opts.append(opt)
                field_copy["options"] = translated_opts

            # Traduction récursive des sous-schémas (ex: item_schema d'un tableau)
            if "item_schema" in field_copy and isinstance(field_copy["item_schema"], dict):
                field_copy["item_schema"] = {
                    sub_k: _translate_field_dict(sub_v, sub_k) for sub_k, sub_v in field_copy["item_schema"].items()
                }

            return field_copy

        raw_schema = self.get_schema()
        translated_schema = {
            f_key: _translate_field_dict(f_val, f_key) for f_key, f_val in raw_schema.items()
        }

        return {
            "id": self.id,
            "name": translate_text(self.name_t, self.name, lang),
            "name_t": self.name_t,
            "category": self.category.value if isinstance(self.category, NodeCategory) else str(self.category),
            "icon": self.icon,
            "description": translate_text(self.description_t, self.description, lang),
            "description_t": self.description_t,
            "color": self.color,
            "inputs": [p.to_dict(lang=lang) for p in self.inputs],
            "outputs": [p.to_dict(lang=lang) for p in self.outputs],
            "sections": translated_sections,
            "schema": translated_schema,
        }

