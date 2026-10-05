import re
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal


class ConditionEngine:
    """
    Moteur d'évaluation d'expressions conditionnelles hautement sécurisé.
    N'utilise JAMAIS eval() ou exec().
    """

    OPERATORS = {
        "==",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "contains",
        "not_contains",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
        "startswith",
        "endswith",
    }

    @classmethod
    def resolve_path(cls, context: Dict[str, Any], path: str) -> Any:
        """
        Résout une valeur dans le contexte via une notation par points.
        Supporte les chemins absolus (ex: 'event.payload.order.total') et relatifs (ex: 'order.total').
        """
        if not path or not isinstance(path, str):
            return None

        clean_path = path.strip()

        # 1. Tentative directe
        val = cls._lookup_path(context, clean_path)
        if val is not None:
            return val

        # 2. Tentatives avec préfixes standards si non trouvé
        prefixes = [
            "event.payload.",
            "payload.",
            "input.",
            "context.",
            "webhook.body.",
            "webhook.",
            "payload.webhook.body.",
            "payload.webhook.",
            "variables.",
            "steps.",
        ]
        for prefix in prefixes:
            val = cls._lookup_path(context, prefix + clean_path)
            if val is not None:
                return val

        # 3. Si le chemin commence par un préfixe explicite comme 'context.', chercher à la racine du contexte
        if clean_path.startswith("context."):
            sub = clean_path[len("context."):]
            val = cls._lookup_path(context, sub)
            if val is not None:
                return val

        # 4. Si le chemin commence par 'input.', tester dans context['last_output'] en fallback
        if clean_path.startswith("input."):
            sub = clean_path[len("input."):]
            if "last_output" in context and isinstance(context["last_output"], dict):
                val = cls._lookup_path(context["last_output"], sub)
                if val is not None:
                    return val

        return None

    @classmethod
    def _lookup_path(cls, data: Any, path: str) -> Any:
        parts = path.split(".")
        current = data
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, (list, tuple)) and part.isdigit():
                idx = int(part)
                current = current[idx] if 0 <= idx < len(current) else None
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    @classmethod
    def evaluate(cls, rule_or_group: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Évalue une règle unique ou un groupe logique de règles (AND, OR, NOT).
        Structure d'une règle :
            {"field": "order.total", "operator": ">=", "value": 500000}
        Structure d'un groupe :
            {"logic": "AND", "rules": [ ... ]}
            {"logic": "OR", "rules": [ ... ]}
            {"logic": "NOT", "rule": { ... }}
        """
        if not rule_or_group:
            return True

        logic = rule_or_group.get("logic")
        if logic:
            logic_upper = str(logic).strip().upper()
            if logic_upper == "AND":
                rules = rule_or_group.get("rules", [])
                return all(cls.evaluate(r, context) for r in rules) if rules else True
            elif logic_upper == "OR":
                rules = rule_or_group.get("rules", [])
                return any(cls.evaluate(r, context) for r in rules) if rules else True
            elif logic_upper == "NOT":
                sub_rule = rule_or_group.get("rule") or (rule_or_group.get("rules") or [{}])[0]
                return not cls.evaluate(sub_rule, context)
            else:
                raise ValueError(f"Opérateur logique non supporté : {logic}")

        # Cas d'un groupe implicite 'rules' sans 'logic' -> défaut AND
        if "rules" in rule_or_group and isinstance(rule_or_group["rules"], list):
            return all(cls.evaluate(r, context) for r in rule_or_group["rules"])

        # Cas d'une règle unitaire
        field = rule_or_group.get("field")
        operator = rule_or_group.get("operator", "==")
        expected_value = rule_or_group.get("value")

        actual_value = cls.resolve_path(context, field) if field else None
        return cls._compare(actual_value, operator, expected_value)

    @classmethod
    def compare(cls, actual: Any, operator: str, expected: Any) -> bool:
        return cls._compare(actual, operator, expected)

    @classmethod
    def _compare(cls, actual: Any, operator: str, expected: Any) -> bool:
        op = operator.strip().lower()

        # Opérateurs d'existence
        if op == "is_empty":
            return actual is None or actual == "" or actual == [] or actual == {}
        if op == "is_not_empty":
            return not (actual is None or actual == "" or actual == [] or actual == {})

        # Gestion des comparaisons numériques sécurisées
        actual_num, expected_num = cls._try_numeric_conversion(actual, expected)
        if actual_num is not None and expected_num is not None:
            if op in ("==", "eq"):
                return actual_num == expected_num
            if op in ("!=", "neq"):
                return actual_num != expected_num
            if op in (">", "gt"):
                return actual_num > expected_num
            if op in (">=", "gte"):
                return actual_num >= expected_num
            if op in ("<", "lt"):
                return actual_num < expected_num
            if op in ("<=", "lte"):
                return actual_num <= expected_num

        # Comparaisons non-numériques ou mixtes
        if op in ("==", "eq"):
            return str(actual) == str(expected) if (actual is not None and expected is not None) else actual == expected
        if op in ("!=", "neq"):
            return str(actual) != str(expected) if (actual is not None and expected is not None) else actual != expected
        if op in (">", "gt"):
            return str(actual or "") > str(expected or "")
        if op in (">=", "gte"):
            return str(actual or "") >= str(expected or "")
        if op in ("<", "lt"):
            return str(actual or "") < str(expected or "")
        if op in ("<=", "lte"):
            return str(actual or "") <= str(expected or "")

        # Opérateurs de collections et chaînes
        if op == "contains":
            if actual is None:
                return False
            if isinstance(actual, (list, tuple, set)):
                return expected in actual
            return str(expected) in str(actual)

        if op == "not_contains":
            if actual is None:
                return True
            if isinstance(actual, (list, tuple, set)):
                return expected not in actual
            return str(expected) not in str(actual)

        if op == "in":
            if expected is None:
                return False
            if isinstance(expected, (list, tuple, set)):
                return actual in expected
            return str(actual) in str(expected)

        if op == "not_in":
            if expected is None:
                return True
            if isinstance(expected, (list, tuple, set)):
                return actual not in expected
            return str(actual) not in str(expected)

        if op == "startswith":
            if actual is None or expected is None:
                return False
            return str(actual).startswith(str(expected))

        if op == "endswith":
            if actual is None or expected is None:
                return False
            return str(actual).endswith(str(expected))

        raise ValueError(f"Opérateur inconnu : {operator}")

    @classmethod
    def _try_numeric_conversion(cls, v1: Any, v2: Any):
        try:
            if v1 is None or v2 is None:
                return None, None
            if isinstance(v1, (int, float, Decimal)) and isinstance(v2, (int, float, Decimal)):
                return float(v1), float(v2)
            n1 = float(str(v1).strip())
            n2 = float(str(v2).strip())
            return n1, n2
        except (ValueError, TypeError):
            return None, None
