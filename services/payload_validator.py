"""
MELODI Automation Engine - Validateur de Structure de Payload
Valide la conformité d'un payload reçu (événement ou webhook) par rapport
à une définition de schéma déclaratif (mode permissif vs strict).
Supporte les types primitifs étendus et les types personnalisés réutilisables/imbriqués.
"""

import copy
import json
import re
from typing import Any, Dict, List, Tuple, Set, Optional, Union


class PayloadValidator:
    """
    Service de validation de schéma pour les déclencheurs (triggers) de workflow.
    Supporte la vérification des types primitifs et personnalisés (nested),
    la détection des champs requis et l'application des valeurs par défaut déclarées.
    """

    PRIMITIVE_TYPES = {
        "string", "number", "integer", "int", "boolean", "bool",
        "array", "object", "any", "date", "datetime", "email", "url", "uuid"
    }

    EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    UUID_REGEX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?:\:\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$")

    @classmethod
    def _build_custom_types_map(cls, custom_types: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """
        Convertit une liste ou un dictionnaire de types personnalisés en un dictionnaire indexé par nom de type (case-insensitive et case-sensitive).
        """
        types_map: Dict[str, Dict[str, Any]] = {}
        if not custom_types:
            return types_map

        if isinstance(custom_types, list):
            for t in custom_types:
                if isinstance(t, dict):
                    name = str(t.get("name") or t.get("id") or "").strip()
                    if name:
                        types_map[name] = t
                        types_map[name.lower()] = t
        elif isinstance(custom_types, dict):
            for k, v in custom_types.items():
                str_k = str(k).strip()
                if isinstance(v, dict):
                    types_map[str_k] = v
                    types_map[str_k.lower()] = v
                elif isinstance(v, list):
                    # Format { "Address": [ { "key": "street", ... } ] }
                    t_def = {"name": str_k, "fields": v}
                    types_map[str_k] = t_def
                    types_map[str_k.lower()] = t_def

        return types_map

    @classmethod
    def apply_defaults(
        cls,
        payload: Any,
        schema_definition: Any,
        custom_types: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Applique les valeurs par défaut définies dans le schéma sur le payload.
        Si une clé est manquante ou vaut None, et qu'une valeur par défaut est configurée,
        celle-ci est injectée (avec conversion au type cible si applicable).
        Gère également récursivement les types personnalisés imbriqués.

        :param payload: Données reçues (dict, list, etc.)
        :param schema_definition: Liste de règles ou dictionnaire de schéma
        :param custom_types: Dictionnaire ou liste des types personnalisés
        :return: (enriched_payload: Any, applied_defaults: Dict[str, Any])
        """
        if payload is None:
            enriched = {}
        elif isinstance(payload, dict):
            enriched = copy.deepcopy(payload)
        else:
            return payload, {}

        types_map = cls._build_custom_types_map(custom_types)
        normalized_rules = cls._normalize_schema(schema_definition)
        applied_defaults: Dict[str, Any] = {}

        for rule in normalized_rules:
            field_path = rule.get("key", "").strip()
            if not field_path:
                continue

            expected_type = str(rule.get("type", "string")).strip()
            custom_type_name = str(rule.get("custom_type") or rule.get("custom_type_ref") or "").strip()
            default_val = rule.get("default")

            exists, current_val = cls._resolve_path(enriched, field_path)

            # Résolution de type personnalisé
            target_custom_type = None
            if custom_type_name and custom_type_name in types_map:
                target_custom_type = types_map[custom_type_name]
            elif expected_type in types_map:
                target_custom_type = types_map[expected_type]

            if not exists or current_val is None:
                if default_val is not None and not (isinstance(default_val, str) and default_val == ""):
                    casted_val = cls._cast_value(default_val, expected_type)
                    cls._set_path(enriched, field_path, casted_val)
                    applied_defaults[field_path] = casted_val
                    current_val = casted_val
                elif target_custom_type and rule.get("required"):
                    # Si c'est un objet personnalisé requis sans valeur par défaut explicite, initialiser un dict vide pour pouvoir appliquer les défauts de ses sous-champs
                    new_obj: Dict[str, Any] = {}
                    cls._set_path(enriched, field_path, new_obj)
                    current_val = new_obj

            # Application récursive des défauts si c'est un type personnalisé instancié
            if target_custom_type and isinstance(current_val, dict):
                sub_fields = target_custom_type.get("fields") or []
                sub_enriched, sub_defaults = cls.apply_defaults(current_val, sub_fields, types_map)
                cls._set_path(enriched, field_path, sub_enriched)
                for sub_k, sub_v in sub_defaults.items():
                    applied_defaults[f"{field_path}.{sub_k}"] = sub_v

            # Si c'est une liste d'un type personnalisé
            if expected_type == "array" and isinstance(current_val, list):
                item_custom_type = rule.get("item_type") or rule.get("item_custom_type") or custom_type_name
                if item_custom_type and item_custom_type in types_map:
                    sub_fields = types_map[item_custom_type].get("fields") or []
                    for idx, item in enumerate(current_val):
                        if isinstance(item, dict):
                            item_enriched, item_defaults = cls.apply_defaults(item, sub_fields, types_map)
                            current_val[idx] = item_enriched
                            for sub_k, sub_v in item_defaults.items():
                                applied_defaults[f"{field_path}[{idx}].{sub_k}"] = sub_v

        return enriched, applied_defaults

    @classmethod
    def apply_defaults_and_validate(
        cls,
        payload: Any,
        schema_definition: Any,
        validation_mode: str = "any",
        allow_extra_fields: bool = True,
        custom_types: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Tuple[bool, List[Dict[str, Any]], Any]:
        """
        Applique d'abord les valeurs par défaut déclarées dans le schéma,
        puis valide le payload enrichi selon le mode ('any' ou 'strict').

        :return: (is_valid: bool, errors: List[Dict], enriched_payload: Any)
        """
        enriched_payload, _ = cls.apply_defaults(payload, schema_definition, custom_types=custom_types)
        is_valid, errors = cls.validate(
            payload=enriched_payload,
            schema_definition=schema_definition,
            validation_mode=validation_mode,
            allow_extra_fields=allow_extra_fields,
            custom_types=custom_types,
        )
        return is_valid, errors, enriched_payload

    @classmethod
    def validate(
        cls,
        payload: Any,
        schema_definition: Any,
        validation_mode: str = "any",
        allow_extra_fields: bool = True,
        custom_types: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
        visited_types: Optional[Set[str]] = None,
        path_prefix: str = "",
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Valide un payload selon le mode, le schéma configuré et les types personnalisés (récursif).

        :param payload: Données reçues (dict, list, etc.)
        :param schema_definition: Liste de règles ou dictionnaire de schéma
        :param validation_mode: 'any' (permissif) ou 'strict'
        :param allow_extra_fields: Tolérer ou rejeter les champs non déclarés en mode strict
        :param custom_types: Définition des types personnalisés utilisables
        :param visited_types: Ensemble des types visités (protection contre les cycles récursifs)
        :param path_prefix: Préfixe de chemin pour les sous-objets (ex: 'customer.')
        :return: (is_valid: bool, errors: List[Dict])
        """
        mode_str = str(validation_mode or "any").lower().strip()
        if mode_str != "strict":
            return True, []

        normalized_rules = cls._normalize_schema(schema_definition)
        if not normalized_rules:
            return True, []

        types_map = cls._build_custom_types_map(custom_types)
        visited = set(visited_types or set())

        errors: List[Dict[str, Any]] = []

        if payload is None:
            field_name = path_prefix.rstrip(".") if path_prefix else "$root"
            errors.append({
                "field": field_name,
                "message": f"Le champ '{field_name}' est absent ou null.",
                "code": "missing_payload",
            })
            return False, errors

        if not isinstance(payload, (dict, list)):
            field_name = path_prefix.rstrip(".") if path_prefix else "$root"
            errors.append({
                "field": field_name,
                "message": f"Le payload doit être un objet JSON ou une liste (reçu: {type(payload).__name__}).",
                "code": "invalid_root_type",
                "actual_type": type(payload).__name__,
            })
            return False, errors

        declared_root_keys: Set[str] = set()

        for rule in normalized_rules:
            field_key = rule.get("key", "").strip()
            if not field_key:
                continue

            full_field_path = f"{path_prefix}{field_key}" if path_prefix else field_key
            root_key = field_key.split(".")[0]
            declared_root_keys.add(root_key)

            expected_type = str(rule.get("type", "string")).strip()
            custom_type_name = str(rule.get("custom_type") or rule.get("custom_type_ref") or "").strip()
            required = bool(rule.get("required", True))

            # Résolution de type personnalisé
            target_custom_type = None
            if custom_type_name and custom_type_name in types_map:
                target_custom_type = types_map[custom_type_name]
            elif expected_type in types_map:
                target_custom_type = types_map[expected_type]

            exists, val = cls._resolve_path(payload, field_key)

            if not exists:
                if required:
                    errors.append({
                        "field": full_field_path,
                        "message": f"Le champ obligatoire '{full_field_path}' est manquant.",
                        "code": "missing_field",
                        "expected_type": target_custom_type.get("name", expected_type) if target_custom_type else expected_type,
                    })
                continue

            if val is None:
                if required and expected_type != "any":
                    errors.append({
                        "field": full_field_path,
                        "message": f"Le champ obligatoire '{full_field_path}' ne peut pas être null.",
                        "code": "null_value",
                        "expected_type": target_custom_type.get("name", expected_type) if target_custom_type else expected_type,
                    })
                continue

            # Cas 1 : Type personnalisé résolu (Objet structuré)
            if target_custom_type:
                t_name = target_custom_type.get("name", custom_type_name or expected_type)
                if not isinstance(val, dict):
                    actual_type = cls._get_type_name(val)
                    errors.append({
                        "field": full_field_path,
                        "message": (
                            f"Le champ '{full_field_path}' doit être un objet conforme au type personnalisé '{t_name}' "
                            f"(reçu: '{actual_type}' avec valeur: {repr(val)[:40]})."
                        ),
                        "code": "invalid_custom_type",
                        "expected_type": t_name,
                        "actual_type": actual_type,
                        "value": val,
                    })
                    continue

                if t_name in visited:
                    # Évite la récursion infinie en cas de cycle
                    continue

                sub_visited = set(visited)
                sub_visited.add(t_name)
                sub_fields = target_custom_type.get("fields") or []

                sub_valid, sub_errors = cls.validate(
                    payload=val,
                    schema_definition=sub_fields,
                    validation_mode=validation_mode,
                    allow_extra_fields=allow_extra_fields,
                    custom_types=types_map,
                    visited_types=sub_visited,
                    path_prefix=f"{full_field_path}.",
                )
                if not sub_valid:
                    errors.extend(sub_errors)
                continue

            # Cas 2 : Tableau avec élément typé (ex: array of CustomType ou array of string)
            if expected_type.lower() == "array":
                if not isinstance(val, (list, tuple)):
                    actual_type = cls._get_type_name(val)
                    errors.append({
                        "field": full_field_path,
                        "message": f"Le champ '{full_field_path}' doit être une liste/tableau (reçu: '{actual_type}').",
                        "code": "invalid_type",
                        "expected_type": "array",
                        "actual_type": actual_type,
                        "value": val,
                    })
                    continue

                item_type = str(rule.get("item_type") or rule.get("item_custom_type") or "").strip()
                item_custom_type = types_map.get(item_type) if item_type else None

                if item_custom_type:
                    t_item_name = item_custom_type.get("name", item_type)
                    sub_fields = item_custom_type.get("fields") or []
                    for idx, item in enumerate(val):
                        if not isinstance(item, dict):
                            errors.append({
                                "field": f"{full_field_path}[{idx}]",
                                "message": f"L'élément à l'index {idx} du tableau '{full_field_path}' doit être un objet de type '{t_item_name}'.",
                                "code": "invalid_item_type",
                                "expected_type": t_item_name,
                                "actual_type": cls._get_type_name(item),
                            })
                            continue
                        sub_valid, sub_errors = cls.validate(
                            payload=item,
                            schema_definition=sub_fields,
                            validation_mode=validation_mode,
                            allow_extra_fields=allow_extra_fields,
                            custom_types=types_map,
                            visited_types=visited,
                            path_prefix=f"{full_field_path}[{idx}].",
                        )
                        if not sub_valid:
                            errors.extend(sub_errors)
                elif item_type and item_type in cls.PRIMITIVE_TYPES:
                    for idx, item in enumerate(val):
                        if not cls._check_type(item, item_type):
                            errors.append({
                                "field": f"{full_field_path}[{idx}]",
                                "message": f"L'élément à l'index {idx} du tableau '{full_field_path}' doit être de type '{item_type}'.",
                                "code": "invalid_item_type",
                                "expected_type": item_type,
                                "actual_type": cls._get_type_name(item),
                            })
                continue

            # Cas 3 : Type primitif ou standard
            if not cls._check_type(val, expected_type):
                actual_type = cls._get_type_name(val)
                errors.append({
                    "field": full_field_path,
                    "message": (
                        f"Le champ '{full_field_path}' doit être de type '{expected_type}' "
                        f"(reçu: '{actual_type}' avec valeur: {repr(val)[:40]})."
                    ),
                    "code": "invalid_type",
                    "expected_type": expected_type,
                    "actual_type": actual_type,
                    "value": val,
                })

        # 4. Vérification des champs non déclarés (si allow_extra_fields == False)
        if not allow_extra_fields and isinstance(payload, dict):
            for k in payload.keys():
                str_k = str(k)
                if str_k not in declared_root_keys:
                    err_field = f"{path_prefix}{str_k}" if path_prefix else str_k
                    errors.append({
                        "field": err_field,
                        "message": f"Le champ non déclaré '{err_field}' n'est pas autorisé dans ce schéma strict.",
                        "code": "unexpected_field",
                    })

        return len(errors) == 0, errors

    @classmethod
    def _normalize_schema(cls, schema_definition: Any) -> List[Dict[str, Any]]:
        """
        Normalise la définition de schéma (liste, dictionnaire ou chaîne JSON)
        en une liste d'objets standardisés { key, type, required, default, description, custom_type, item_type }.
        """
        rules: List[Dict[str, Any]] = []

        if isinstance(schema_definition, list):
            for item in schema_definition:
                if isinstance(item, dict):
                    k = str(item.get("key") or item.get("name") or "").strip()
                    if k:
                        rules.append({
                            "key": k,
                            "type": str(item.get("type", "string")).strip(),
                            "required": bool(item.get("required", True)),
                            "default": item.get("default") if "default" in item else None,
                            "description": str(item.get("description", "")),
                            "custom_type": item.get("custom_type") or item.get("custom_type_ref"),
                            "item_type": item.get("item_type") or item.get("item_custom_type"),
                        })
        elif isinstance(schema_definition, dict):
            for k, v in schema_definition.items():
                str_k = str(k).strip()
                if not str_k:
                    continue
                if isinstance(v, dict):
                    rules.append({
                        "key": str_k,
                        "type": str(v.get("type", "string")).strip(),
                        "required": bool(v.get("required", True)),
                        "default": v.get("default") if "default" in v else None,
                        "description": str(v.get("description", "")),
                        "custom_type": v.get("custom_type") or v.get("custom_type_ref"),
                        "item_type": v.get("item_type") or v.get("item_custom_type"),
                    })
                elif isinstance(v, str):
                    rules.append({
                        "key": str_k,
                        "type": v.strip(),
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
        if t in ("number", "float"):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
            if isinstance(value, str):
                s = value.strip()
                try:
                    return int(s) if (s.isdigit() or (s.startswith("-") and s[1:].isdigit())) else float(s)
                except (ValueError, TypeError):
                    return value
        elif t in ("integer", "int"):
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            if isinstance(value, str):
                try:
                    return int(value.strip())
                except (ValueError, TypeError):
                    return value
            if isinstance(value, float):
                return int(value)
        elif t in ("boolean", "bool"):
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
        Primitifs supportés: string, number, integer, boolean, array, object, any, email, date, uuid.
        """
        t = expected_type.lower().strip()
        if t in ("any", "custom") or not t:
            return True

        if t == "string":
            return isinstance(value, str)

        if t in ("number", "float"):
            return isinstance(value, (int, float)) and not isinstance(value, bool)

        if t in ("integer", "int"):
            return isinstance(value, int) and not isinstance(value, bool)

        if t in ("boolean", "bool"):
            return isinstance(value, bool)

        if t == "array":
            return isinstance(value, (list, tuple))

        if t == "object":
            return isinstance(value, dict)

        if t == "email":
            return isinstance(value, str) and bool(cls.EMAIL_REGEX.match(value.strip()))

        if t in ("date", "datetime"):
            return isinstance(value, str) and bool(cls.DATE_REGEX.match(value.strip()))

        if t == "uuid":
            return isinstance(value, str) and bool(cls.UUID_REGEX.match(value.strip()))

        return True

    @classmethod
    def _get_type_name(cls, value: Any) -> str:
        """Retourne le libellé standard du type de la valeur."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, (list, tuple)):
            return "array"
        if isinstance(value, dict):
            return "object"
        return type(value).__name__
