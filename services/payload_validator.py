"""
MELODI Automation Engine - Validateur de Structure de Payload
Valide la conformité d'un payload reçu (événement ou webhook) par rapport
à une définition de schéma déclaratif (mode permissif vs strict).
"""

import copy
import json
from typing import Any, Dict, List, Tuple, Set, Optional


class PayloadValidator:
    """
    Service de validation de schéma pour les déclencheurs (triggers) de workflow.
    Supporte la vérification des types, la détection des champs requis et
    l'application des valeurs par défaut déclarées.
    """

    ALLOWED_TYPES = {"string", "number", "boolean", "array", "object", "any"}

    @classmethod
    def apply_defaults(
        cls,
        payload: Any,
        schema_definition: Any,
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Applique les valeurs par défaut définies dans le schéma sur le payload.
        Si une clé est manquante ou vaut None, et qu'une valeur par défaut est configurée,
        celle-ci est injectée (avec conversion au type cible si applicable).

        :param payload: Données reçues (dict, list, etc.)
        :param schema_definition: Liste de règles ou dictionnaire de schéma
        :return: (enriched_payload: Any, applied_defaults: Dict[str, Any])
        """
        if payload is None:
            enriched = {}
        elif isinstance(payload, dict):
            enriched = copy.deepcopy(payload)
        else:
            return payload, {}

        normalized_rules = cls._normalize_schema(schema_definition)
        applied_defaults: Dict[str, Any] = {}

        for rule in normalized_rules:
            field_path = rule.get("key", "").strip()
            if not field_path:
                continue

            default_val = rule.get("default")
            if default_val is None or (isinstance(default_val, str) and default_val == ""):
                continue

            exists, current_val = cls._resolve_path(enriched, field_path)
            if not exists or current_val is None:
                expected_type = str(rule.get("type", "string")).lower().strip()
                casted_val = cls._cast_value(default_val, expected_type)
                cls._set_path(enriched, field_path, casted_val)
                applied_defaults[field_path] = casted_val

        return enriched, applied_defaults

    @classmethod
    def apply_defaults_and_validate(
        cls,
        payload: Any,
        schema_definition: Any,
        validation_mode: str = "any",
        allow_extra_fields: bool = True,
    ) -> Tuple[bool, List[Dict[str, Any]], Any]:
        """
        Applique d'abord les valeurs par défaut déclarées dans le schéma,
        puis valide le payload enrichi selon le mode ('any' ou 'strict').

        :return: (is_valid: bool, errors: List[Dict], enriched_payload: Any)
        """
        enriched_payload, _ = cls.apply_defaults(payload, schema_definition)
        is_valid, errors = cls.validate(
            payload=enriched_payload,
            schema_definition=schema_definition,
            validation_mode=validation_mode,
            allow_extra_fields=allow_extra_fields,
        )
        return is_valid, errors, enriched_payload

    @classmethod
    def validate(
        cls,
        payload: Any,
        schema_definition: Any,
        validation_mode: str = "any",
        allow_extra_fields: bool = True,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Valide un payload selon le mode et le schéma configurés.

        :param payload: Données reçues (dict, list, etc.)
        :param schema_definition: Liste de règles ou dictionnaire de schéma
        :param validation_mode: 'any' (permissif) ou 'strict'
        :param allow_extra_fields: Tolérer ou rejeter les champs non déclarés en mode strict
        :return: (is_valid: bool, errors: List[Dict])
        """
        # 1. Mode permissif ou schéma non défini -> Toujours valide
        mode_str = str(validation_mode or "any").lower().strip()
        if mode_str != "strict":
            return True, []

        normalized_rules = cls._normalize_schema(schema_definition)
        if not normalized_rules:
            # En mode strict sans règles spécifiées, on accepte le payload
            return True, []

        errors: List[Dict[str, Any]] = []

        # 2. Vérification que le payload est présent et de type conteneur
        if payload is None:
            errors.append({
                "field": "$root",
                "message": "Le payload est absent ou null.",
                "code": "missing_payload",
            })
            return False, errors

        if not isinstance(payload, (dict, list)):
            errors.append({
                "field": "$root",
                "message": f"Le payload doit être un objet JSON ou une liste (reçu: {type(payload).__name__}).",
                "code": "invalid_root_type",
                "actual_type": type(payload).__name__,
            })
            return False, errors

        # 3. Vérification de chaque règle du schéma
        declared_root_keys: Set[str] = set()

        for rule in normalized_rules:
            field_path = rule.get("key", "").strip()
            if not field_path:
                continue

            root_key = field_path.split(".")[0]
            declared_root_keys.add(root_key)

            expected_type = str(rule.get("type", "string")).lower().strip()
            required = bool(rule.get("required", True))

            exists, val = cls._resolve_path(payload, field_path)

            if not exists:
                if required:
                    errors.append({
                        "field": field_path,
                        "message": f"Le champ obligatoire '{field_path}' est manquant.",
                        "code": "missing_field",
                        "expected_type": expected_type,
                    })
                continue

            if val is None:
                if required and expected_type != "any":
                    errors.append({
                        "field": field_path,
                        "message": f"Le champ obligatoire '{field_path}' ne peut pas être null.",
                        "code": "null_value",
                        "expected_type": expected_type,
                    })
                continue

            # Vérification du type de données
            if not cls._check_type(val, expected_type):
                actual_type = cls._get_type_name(val)
                errors.append({
                    "field": field_path,
                    "message": (
                        f"Le champ '{field_path}' doit être de type '{expected_type}' "
                        f"(reçu: '{actual_type}' avec valeur: {repr(val)[:40]})."
                    ),
                    "code": "invalid_type",
                    "expected_type": expected_type,
                    "actual_type": actual_type,
                    "value": val,
                })

        # 4. Vérification des champs imprévus (si allow_extra_fields == False)
        if not allow_extra_fields and isinstance(payload, dict):
            for k in payload.keys():
                str_k = str(k)
                if str_k not in declared_root_keys:
                    errors.append({
                        "field": str_k,
                        "message": f"Le champ non déclaré '{str_k}' n'est pas autorisé dans ce schéma strict.",
                        "code": "unexpected_field",
                    })

        return len(errors) == 0, errors

    @classmethod
    def _normalize_schema(cls, schema_definition: Any) -> List[Dict[str, Any]]:
        """
        Normalise la définition de schéma (liste, dictionnaire ou chaîne JSON)
        en une liste d'objets standardisés { key, type, required, default, description }.
        """
        rules: List[Dict[str, Any]] = []

        if isinstance(schema_definition, list):
            for item in schema_definition:
                if isinstance(item, dict):
                    k = str(item.get("key") or item.get("name") or "").strip()
                    if k:
                        rules.append({
                            "key": k,
                            "type": str(item.get("type", "string")).lower().strip(),
                            "required": bool(item.get("required", True)),
                            "default": item.get("default") if "default" in item else None,
                            "description": str(item.get("description", "")),
                        })
        elif isinstance(schema_definition, dict):
            for k, v in schema_definition.items():
                str_k = str(k).strip()
                if not str_k:
                    continue
                if isinstance(v, dict):
                    rules.append({
                        "key": str_k,
                        "type": str(v.get("type", "string")).lower().strip(),
                        "required": bool(v.get("required", True)),
                        "default": v.get("default") if "default" in v else None,
                        "description": str(v.get("description", "")),
                    })
                elif isinstance(v, str):
                    rules.append({
                        "key": str_k,
                        "type": v.lower().strip(),
                        "required": True,
                        "default": None,
                        "description": "",
                    })

        return rules

    @classmethod
    def _cast_value(cls, value: Any, expected_type: str) -> Any:
        """
        Convertit une valeur brute vers le type attendu si pertinent.
        """
        if value is None:
            return None

        t = expected_type.lower().strip()
        if t == "number":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
            if isinstance(value, str):
                s = value.strip()
                try:
                    return int(s) if (s.isdigit() or (s.startswith("-") and s[1:].isdigit())) else float(s)
                except (ValueError, TypeError):
                    return value
        elif t == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                s = value.strip().lower()
                if s in ("true", "1", "yes", "oui"):
                    return True
                if s in ("false", "0", "no", "non"):
                    return False
            if isinstance(value, (int, float)):
                return bool(value)
        elif t == "string":
            if isinstance(value, str):
                return value
            return str(value)
        elif t in ("array", "object") and isinstance(value, str):
            s = value.strip()
            if (t == "array" and s.startswith("[")) or (t == "object" and s.startswith("{")):
                try:
                    parsed = json.loads(s)
                    if (t == "array" and isinstance(parsed, list)) or (t == "object" and isinstance(parsed, dict)):
                        return parsed
                except Exception:
                    pass

        return value

    @classmethod
    def _set_path(cls, data: Dict[str, Any], path: str, value: Any) -> None:
        """
        Injecte une valeur dans un dictionnaire selon un chemin simple ou imbriqué (ex: 'order.currency').
        """
        parts = path.strip().split(".")
        current = data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    @classmethod
    def _resolve_path(cls, data: Any, path: str) -> Tuple[bool, Any]:
        """
        Recherche une clé simple ou un chemin imbriqué (ex: 'customer.email') dans data.
        Retourne (exists: bool, value: Any).
        """
        parts = path.strip().split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return False, None
            elif isinstance(current, (list, tuple)) and part.isdigit():
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return False, None
            else:
                return False, None
        return True, current

    @classmethod
    def _check_type(cls, value: Any, expected_type: str) -> bool:
        """
        Vérifie si une valeur concrète correspond au type attendu.
        Types supportés: string, number, boolean, array, object, any.
        """
        t = expected_type.lower().strip()
        if t == "any" or not t:
            return True

        if t == "string":
            return isinstance(value, str)

        if t == "number":
            # Note: en Python bool est une sous-classe de int, donc 'not isinstance(value, bool)' est obligatoire
            return isinstance(value, (int, float)) and not isinstance(value, bool)

        if t == "boolean":
            return isinstance(value, bool)

        if t == "array":
            return isinstance(value, (list, tuple))

        if t == "object":
            return isinstance(value, dict)

        return True

    @classmethod
    def _get_type_name(cls, value: Any) -> str:
        """Retourne le libellé standard du type de la valeur."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, (list, tuple)):
            return "array"
        if isinstance(value, dict):
            return "object"
        return type(value).__name__
