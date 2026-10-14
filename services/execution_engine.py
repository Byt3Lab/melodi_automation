import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import traceback

from ..models.automation_models import WorkflowModel, ExecutionStatus
from ..repositories.execution_repository import ExecutionRepository
from .condition_engine import ConditionEngine


class ExecutionEngine:
    """
    Moteur d'exécution des workflows (parcours du graphe de nœuds, évaluation, exécution et journalisation).
    """

    SENSITIVE_KEYS = {
        "password",
        "secret",
        "token",
        "access_token",
        "api_key",
        "authorization",
        "pin",
        "card_number",
        "cvv",
        "private_key",
    }

    @classmethod
    def sanitize(cls, data: Any) -> Any:
        """
        Nettoie récursivement les données sensibles pour éviter qu'elles n'apparaissent dans les logs.
        """
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if any(s in str(k).lower() for s in cls.SENSITIVE_KEYS):
                    clean[k] = "********"
                else:
                    clean[k] = cls.sanitize(v)
            return clean
        elif isinstance(data, list):
            return [cls.sanitize(item) for item in data]
        return data

    @classmethod
    def interpolate_value(cls, val: Any, context: Dict[str, Any]) -> Any:
        """
        Interpolation de chaînes contenant des variables ex: '{order.total}' ou '{customer.name}'.
        Si la chaîne est exactement '{champ}', retourne le type natif (int, float, dict, etc.).
        """
        if not isinstance(val, str):
            if isinstance(val, dict):
                return {k: cls.interpolate_value(v, context) for k, v in val.items()}
            if isinstance(val, list):
                return [cls.interpolate_value(item, context) for item in val]
            return val

        # Cas valeur exacte encapsulée "{chemin}" -> préserve le type d'origine
        trimmed = val.strip()
        if trimmed.startswith("{") and trimmed.endswith("}") and " " not in trimmed:
            path = trimmed[1:-1]
            resolved = ConditionEngine.resolve_path(context, path)
            return resolved if resolved is not None else val

        # Cas d'interpolation dans une chaîne de texte
        import re
        def _replace_var(match):
            path = match.group(1).strip()
            resolved = ConditionEngine.resolve_path(context, path)
            return str(resolved) if resolved is not None else match.group(0)

        return re.sub(r"\{([a-zA-Z0-9_\.]+)\}", _replace_var, val)

    @classmethod
    async def execute(cls, workflow: WorkflowModel, context: Dict[str, Any], app: Any) -> Dict[str, Any]:
        """
        Exécute de manière orchestrée et isolée un workflow complet.
        """
        start_time = time.time()
        trigger_event = f"{workflow.trigger_module}.{workflow.trigger_event}"

        # 1. Assainissement du contexte pour persistance
        sanitized_context = cls.sanitize(context)

        # 2. Création de l'enregistrement de l'exécution
        execution_id = None
        async with app.db.get_session() as session:
            execution = await ExecutionRepository.create_execution(
                session=session,
                workflow_id=workflow.id,
                workflow_version=workflow.version,
                trigger_event=trigger_event,
                context_data=sanitized_context,
            )
            await session.commit()
            execution_id = execution.id

        # 3. Initialisation des clés requises dans le contexte d'exécution
        context.setdefault("steps", {})
        context.setdefault("last_output", None)
        context.setdefault("variables", {})
        context.setdefault("custom_types", getattr(workflow, "custom_types", []) or [])

        # Suivi de la pile d'exécution (anti-boucle récursive)
        execution_stack = list(context.get("_execution_stack") or [])
        wf_id_str = str(workflow.id)
        if not execution_stack or execution_stack[-1] != wf_id_str:
            if wf_id_str not in execution_stack:
                execution_stack.append(wf_id_str)
        context["_execution_stack"] = execution_stack

        # 4. Préparation du graphe de nœuds et connexions
        nodes_list = workflow.nodes or []
        connections_list = workflow.connections or []

        nodes_by_id = {str(n.get("id")): n for n in nodes_list if n.get("id")}
        
        # Table des connexions sortantes : {source_node_id: [(source_output, target_node_id), ...]}
        adjacency: Dict[str, List[tuple]] = {}
        for conn in connections_list:
            src = str(conn.get("source_node"))
            tgt = str(conn.get("target_node"))
            out = str(conn.get("source_output", "default")).lower()
            if src not in adjacency:
                adjacency[src] = []
            adjacency[src].append((out, tgt))

        # Les workflows utilisent exclusivement les types de nœuds du registre.
        start_node = nodes_list[0] if nodes_list else None

        if not start_node:
            async with app.db.get_session() as session:
                await ExecutionRepository.update_execution_status(
                    session, execution_id, ExecutionStatus.SUCCESS,
                    error_message="Workflow vide sans aucun nœud.",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
                await session.commit()
            return {"status": "success", "execution_id": execution_id}

        # 4. Parcours séquentiel / DAG
        queue = [start_node]
        visited: Set[str] = set()
        execution_failed = False
        error_details = None

        while queue and not execution_failed:
            current_node = queue.pop(0)
            node_id = str(current_node.get("id"))
            node_type = str(current_node.get("type", "generic")).lower()
            node_name = current_node.get("name") or f"Node {node_id}"
            node_config = current_node.get("configuration") or {}

            if node_id in visited:
                continue
            visited.add(node_id)

            node_start_time = datetime.utcnow()
            node_status = ExecutionStatus.SUCCESS
            node_error = None
            node_input = cls.sanitize(context.get("steps", {}).get(node_id) or context.get("last_output") or context.get("payload") or {})
            node_output = {}
            active_ports = None

            try:
                # 1. Vérification dans le NodeRegistry (Nœuds avancés et tiers)
                from ..nodes.registry import NodeRegistry
                node_impl = NodeRegistry.get(node_type)

                if node_impl:
                    exec_res = await node_impl.execute(node_input, node_config, context, app)
                    node_output = cls.sanitize(exec_res.output_data)
                    active_ports = exec_res.active_ports
                    context["steps"][node_id] = node_output
                    context["last_output"] = node_output
                else:
                    raise ValueError(f"Type de nœud non enregistré : '{node_type}'.")

            except Exception as e:
                node_status = ExecutionStatus.FAILED
                node_error = str(e)
                execution_failed = True
                error_details = f"Erreur dans le nœud '{node_name}' ({node_id}) : {e}\n{traceback.format_exc()}"

            node_finish_time = datetime.utcnow()

            # Enregistrement du log de ce nœud
            async with app.db.get_session() as session:
                await ExecutionRepository.create_log(
                    session=session,
                    execution_id=execution_id,
                    workflow_id=workflow.id,
                    node_id=node_id,
                    node_type=node_type,
                    node_name=node_name,
                    status=node_status,
                    input_data=cls.sanitize(node_input),
                    output_data=cls.sanitize(node_output),
                    error=node_error,
                    started_at=node_start_time,
                    finished_at=node_finish_time,
                )
                await session.commit()

            if execution_failed:
                break

            # Détermination des nœuds suivants selon les connexions et les ports activés
            outgoing = adjacency.get(node_id, [])
            for out_port, next_node_id in outgoing:
                next_node = nodes_by_id.get(next_node_id)
                if not next_node:
                    continue

                out_lower = out_port.lower()
                # Routage multi-ports avancé
                if active_ports is not None:
                    active_lower = [p.lower() for p in active_ports]
                    if out_lower in active_lower or (out_lower in ("main", "default", "") and "main" in active_lower):
                        queue.append(next_node)

        # 5. Clôture de l'exécution
        duration_ms = int((time.time() - start_time) * 1000)
        final_status = ExecutionStatus.FAILED if execution_failed else ExecutionStatus.SUCCESS

        async with app.db.get_session() as session:
            await ExecutionRepository.update_execution_status(
                session=session,
                execution_id=execution_id,
                status=final_status,
                context_data=cls.sanitize(context),
                error_message=error_details,
                duration_ms=duration_ms,
                finished=True,
            )
            await session.commit()

        return {
            "status": final_status.value,
            "execution_id": execution_id,
            "duration_ms": duration_ms,
            "error": error_details,
            "steps": context.get("steps", {}),
            "context": context,
        }

    @classmethod
    async def simulate_graph(
        cls,
        nodes_list: List[Dict[str, Any]],
        connections_list: List[Dict[str, Any]],
        initial_payload: Optional[Dict[str, Any]] = None,
        custom_types: Optional[List[Dict[str, Any]]] = None,
        app: Any = None,
    ) -> Dict[str, Any]:
        """
        Simule l'exécution d'un graphe de nœuds et connexions en mémoire (dry-run).
        N'enregistre aucune donnée en base de données.
        Permet l'inspection temps réel des données d'entrée/sortie et l'extraction
        de l'ensemble des variables disponibles pour l'autocomplétion.
        """
        start_time = time.time()
        initial_payload = initial_payload if isinstance(initial_payload, dict) else {}

        # 1. Initialisation du contexte de simulation
        context: Dict[str, Any] = {
            "payload": dict(initial_payload),
            "steps": {},
            "variables": {},
            "custom_types": list(custom_types or []),
            "last_output": dict(initial_payload) if initial_payload else {},
            "_execution_stack": ["simulation"],
        }
        for k, v in initial_payload.items():
            if k not in context:
                context[k] = v

        nodes_by_id = {str(n.get("id")): n for n in nodes_list if n.get("id")}
        adjacency: Dict[str, List[tuple]] = {}
        incoming_by_target: Dict[str, List[tuple]] = {}
        in_degree: Dict[str, int] = {str(nid): 0 for nid in nodes_by_id.keys()}

        for conn in connections_list:
            src = str(conn.get("source_node") or conn.get("source_node_id") or conn.get("source") or "")
            tgt = str(conn.get("target_node") or conn.get("target_node_id") or conn.get("target") or "")
            src_port = str(conn.get("source_output") or conn.get("source_port") or "main")
            if src and tgt:
                adjacency.setdefault(src, []).append((src_port, tgt))
                incoming_by_target.setdefault(tgt, []).append((src, src_port))
                in_degree[tgt] = in_degree.get(tgt, 0) + 1

        # Nœuds initiaux (déclencheurs ou nœuds sans entrée)
        queue: List[Dict[str, Any]] = []
        for n in nodes_list:
            nid = str(n.get("id"))
            ntype = str(n.get("type", "")).lower()
            if "trigger" in ntype or in_degree.get(nid, 0) == 0:
                if n not in queue:
                    queue.append(n)

        if not queue and nodes_list:
            queue.append(nodes_list[0])

        nodes_trace: Dict[str, Dict[str, Any]] = {}
        timeline: List[Dict[str, Any]] = []
        visited = set()
        max_steps = 60
        steps_count = 0
        overall_status = "success"
        error_msg = None

        from ..nodes.registry import NodeRegistry

        # Fonction récursive d'extraction des variables
        def _extract_vars_list(
            data: Any,
            prefix: str,
            source_label: str,
            category: str,
            target_list: List[Dict[str, Any]],
            seen: Set[str],
            node_id: Optional[str] = None,
            node_name: Optional[str] = None,
        ):
            if data is None:
                return

            if isinstance(data, dict):
                if prefix and prefix not in seen:
                    seen.add(prefix)
                    target_list.append({
                        "path": prefix,
                        "name": prefix.split(".")[-1],
                        "type": "object",
                        "preview": f"Objet ({len(data)} clés)",
                        "source": source_label,
                        "category": category,
                        "node_id": node_id,
                        "node_name": node_name,
                    })
                for k, v in data.items():
                    p = f"{prefix}.{k}" if prefix else str(k)
                    if isinstance(v, (dict, list)):
                        _extract_vars_list(v, p, source_label, category, target_list, seen, node_id, node_name)
                    else:
                        if p not in seen:
                            seen.add(p)
                            t_name = type(v).__name__
                            if t_name == "str":
                                t_name = "string"
                            elif t_name in ("int", "float"):
                                t_name = "number"
                            elif t_name == "bool":
                                t_name = "boolean"
                            target_list.append({
                                "path": p,
                                "name": str(k),
                                "type": t_name,
                                "preview": str(v)[:60],
                                "source": source_label,
                                "category": category,
                                "node_id": node_id,
                                "node_name": node_name,
                            })
            elif isinstance(data, list):
                if prefix and prefix not in seen:
                    seen.add(prefix)
                    target_list.append({
                        "path": prefix,
                        "name": prefix.split(".")[-1],
                        "type": "array",
                        "preview": f"Liste ({len(data)} éléments)",
                        "source": source_label,
                        "category": category,
                        "node_id": node_id,
                        "node_name": node_name,
                    })
                if data and isinstance(data[0], dict):
                    _extract_vars_list(data[0], f"{prefix}[0]", source_label, category, target_list, seen, node_id, node_name)
            else:
                if prefix and prefix not in seen:
                    seen.add(prefix)
                    target_list.append({
                        "path": prefix,
                        "name": prefix.split(".")[-1],
                        "type": type(data).__name__,
                        "preview": str(data)[:60],
                        "source": source_label,
                        "category": category,
                        "node_id": node_id,
                        "node_name": node_name,
                    })

        while queue and steps_count < max_steps:
            steps_count += 1
            node = queue.pop(0)
            node_id = str(node.get("id"))
            if node_id in visited:
                continue
            visited.add(node_id)

            node_type = str(node.get("type") or "")
            node_name = str(node.get("name") or node_id)
            config = node.get("configuration") or {}

            # Données d'entrée pour ce nœud : routage depuis les prédécesseurs directs
            is_trigger = "trigger" in node_type.lower() or in_degree.get(node_id, 0) == 0
            if is_trigger:
                node_input = dict(initial_payload) if isinstance(initial_payload, dict) else initial_payload
            else:
                incoming_preds = incoming_by_target.get(node_id, [])
                predecessor_outputs = []
                for p_id, p_port in incoming_preds:
                    if p_id in context.get("steps", {}):
                        p_out = context["steps"][p_id]
                        predecessor_outputs.append(p_out)

                if len(predecessor_outputs) == 1:
                    node_input = predecessor_outputs[0]
                elif len(predecessor_outputs) > 1:
                    merged = {}
                    for p_out in predecessor_outputs:
                        if isinstance(p_out, dict):
                            merged.update(p_out)
                    node_input = merged if merged else predecessor_outputs[-1]
                else:
                    node_input = context.get("last_output") or initial_payload or {}

            # Contexte d'évaluation à ce pas
            context["input"] = node_input
            context["last_output"] = node_input

            node_start = time.time()
            node_status = "success"
            node_output = None
            active_ports = ["main"]
            node_err = None

            node_instance = NodeRegistry.get(node_type)
            if not node_instance:
                node_status = "error"
                node_err = f"Nœud de type inconnu : '{node_type}'"
                overall_status = "error"
                error_msg = node_err
            else:
                try:
                    res = await node_instance.execute(node_input, config, context, app)
                    node_output = res.output_data
                    active_ports = res.active_ports or ["main"]

                    # Mise à jour du contexte pour les nœuds suivants
                    context["steps"][node_id] = node_output
                    context["last_output"] = node_output
                    if isinstance(node_output, dict):
                        for ok, ov in node_output.items():
                            context["variables"][ok] = ov
                            context[ok] = ov
                except Exception as e:
                    node_status = "error"
                    node_err = str(e)
                    overall_status = "error"
                    error_msg = f"Erreur dans '{node_name}' ({node_id}) : {e}"

            node_dur = int((time.time() - node_start) * 1000)

            # Capture des étapes précédentes pour inspection détaillée
            preceding_steps_map = {}
            for s_id, s_data in context.get("steps", {}).items():
                s_node = nodes_by_id.get(s_id, {})
                preceding_steps_map[s_id] = {
                    "id": s_id,
                    "name": s_node.get("name") or s_id,
                    "type": s_node.get("type") or "",
                    "output": cls.sanitize(s_data),
                }

            # Variables d'entrée de ce nœud
            node_input_vars: List[Dict[str, Any]] = []
            _extract_vars_list(node_input, "input", f"Entrée de {node_name}", "node_io", node_input_vars, set(), node_id, node_name)
            _extract_vars_list(node_input, "", f"Entrée directe ({node_name})", "node_io", node_input_vars, set(), node_id, node_name)

            # Variables de sortie de ce nœud
            node_output_vars: List[Dict[str, Any]] = []
            if node_output is not None:
                _extract_vars_list(node_output, f"steps.{node_id}", f"Sortie: {node_name}", "steps", node_output_vars, set(), node_id, node_name)
                if isinstance(node_output, dict):
                    _extract_vars_list(node_output, "", f"Sortie directe ({node_name})", "node_io", node_output_vars, set(), node_id, node_name)

            trace_item = {
                "node_id": node_id,
                "node_name": node_name,
                "node_type": node_type,
                "status": node_status,
                "input_data": cls.sanitize(node_input),
                "output_data": cls.sanitize(node_output) if node_output is not None else None,
                "active_ports": active_ports,
                "duration_ms": node_dur,
                "error": node_err,
                "payload": cls.sanitize(initial_payload),
                "context_snapshot": {
                    "variables": cls.sanitize(context.get("variables", {})),
                    "execution_stack": list(context.get("_execution_stack", [])),
                },
                "preceding_steps": preceding_steps_map,
                "input_variables": node_input_vars,
                "output_variables": node_output_vars,
            }
            nodes_trace[node_id] = trace_item
            timeline.append(trace_item)

            if node_status == "error":
                break

            # Propagation le long des connexions actives
            outgoing = adjacency.get(node_id, [])
            for out_port, next_node_id in outgoing:
                next_node = nodes_by_id.get(next_node_id)
                if not next_node:
                    continue
                out_lower = out_port.lower()
                active_lower = [p.lower() for p in active_ports]
                if out_lower in active_lower or (out_lower in ("main", "default", "") and "main" in active_lower):
                    if next_node not in queue and str(next_node.get("id")) not in visited:
                        queue.append(next_node)

        # 3. Extraction de l'arbre aplati et catégorisé des variables disponibles
        available_variables: List[Dict[str, Any]] = []
        seen_paths: Set[str] = set()

        # A. Catégorie 'payload' : Déclencheur initial
        if initial_payload:
            _extract_vars_list(initial_payload, "payload", "Payload Déclencheur", "payload", available_variables, seen_paths)
            _extract_vars_list(initial_payload, "", "Déclencheur (Racine)", "payload", available_variables, seen_paths)

        # B. Catégorie 'steps' : Variables créées par chaque étape exécutée
        for step_id, step_out in context.get("steps", {}).items():
            s_node = nodes_by_id.get(step_id, {})
            s_name = s_node.get("name") or step_id
            _extract_vars_list(
                step_out,
                f"steps.{step_id}",
                f"Étape: {s_name}",
                "steps",
                available_variables,
                seen_paths,
                node_id=step_id,
                node_name=s_name,
            )

        # C. Catégorie 'context' : Métadonnées et variables d'environnement
        ctx_meta = {
            "timestamp": int(start_time * 1000),
            "execution_id": "sim_dry_run",
        }
        _extract_vars_list(ctx_meta, "context", "Contexte Global", "context", available_variables, seen_paths)
        if context.get("variables"):
            _extract_vars_list(context["variables"], "context.variables", "Variables Contextuelles", "context", available_variables, seen_paths)

        total_duration = int((time.time() - start_time) * 1000)

        # Identifier les nœuds non exécutés (bypassed / skipped)
        for nid, n in nodes_by_id.items():
            if nid not in nodes_trace:
                nodes_trace[nid] = {
                    "node_id": nid,
                    "node_name": n.get("name") or nid,
                    "node_type": n.get("type") or "",
                    "status": "skipped",
                    "input_data": None,
                    "output_data": None,
                    "active_ports": [],
                    "duration_ms": 0,
                    "error": None,
                    "payload": cls.sanitize(initial_payload),
                    "context_snapshot": {},
                    "preceding_steps": {},
                    "input_variables": [],
                    "output_variables": [],
                }

        return {
            "status": overall_status,
            "duration_ms": total_duration,
            "error": error_msg,
            "executed_count": len(timeline),
            "total_nodes": len(nodes_list),
            "timeline": timeline,
            "nodes_trace": nodes_trace,
            "available_variables": available_variables,
            "final_context": cls.sanitize(context),
            "payload": cls.sanitize(initial_payload),
            "steps": {
                nid: {
                    "id": nid,
                    "name": nodes_by_id.get(nid, {}).get("name") or nid,
                    "type": nodes_by_id.get(nid, {}).get("type") or "",
                    "output": cls.sanitize(trace.get("output_data")),
                }
                for nid, trace in nodes_trace.items()
                if trace.get("status") == "success"
            },
        }

    @classmethod
    async def execute_single_node(
        cls,
        node_id: str,
        node_type: str,
        node_config: Dict[str, Any],
        input_data: Any,
        context: Optional[Dict[str, Any]] = None,
        app: Any = None,
    ) -> Dict[str, Any]:
        """
        Exécute un nœud individuel pour le test et le débogage interactif (n8n-style 'Test Step').
        Calcule la durée, le statut, les ports activés et déduit les variables de sortie avec leurs types.
        """
        start_time = time.time()
        from ..nodes.registry import NodeRegistry

        eval_context = dict(context) if isinstance(context, dict) else {}
        eval_context.setdefault("steps", {})
        eval_context.setdefault("variables", {})
        eval_context.setdefault("last_output", input_data)
        eval_context["input"] = input_data

        node_instance = NodeRegistry.get(node_type)
        if not node_instance:
            return {
                "status": "error",
                "error": f"Nœud inconnu : '{node_type}'",
                "duration_ms": 0,
                "output_data": None,
                "output_variables": [],
            }

        try:
            res = await node_instance.execute(input_data, node_config, eval_context, app)
            duration_ms = int((time.time() - start_time) * 1000)
            clean_output = cls.sanitize(res.output_data)

            # Extraction des variables générées par ce nœud
            output_vars: List[Dict[str, Any]] = []
            seen: Set[str] = set()

            def _inspect_vars(data: Any, prefix: str):
                if data is None:
                    return
                if isinstance(data, dict):
                    if prefix and prefix not in seen:
                        seen.add(prefix)
                        output_vars.append({
                            "path": prefix,
                            "name": prefix.split(".")[-1],
                            "type": "object",
                            "preview": f"Objet ({len(data)} clés)",
                        })
                    for k, v in data.items():
                        p = f"{prefix}.{k}" if prefix else str(k)
                        _inspect_vars(v, p)
                elif isinstance(data, list):
                    if prefix and prefix not in seen:
                        seen.add(prefix)
                        output_vars.append({
                            "path": prefix,
                            "name": prefix.split(".")[-1],
                            "type": "array",
                            "preview": f"Liste ({len(data)} éléments)",
                        })
                    if data and isinstance(data[0], dict):
                        _inspect_vars(data[0], f"{prefix}[0]")
                else:
                    if prefix and prefix not in seen:
                        seen.add(prefix)
                        t_name = type(data).__name__
                        if t_name == "str":
                            t_name = "string"
                        elif t_name in ("int", "float"):
                            t_name = "number"
                        elif t_name == "bool":
                            t_name = "boolean"
                        output_vars.append({
                            "path": prefix,
                            "name": prefix.split(".")[-1],
                            "type": t_name,
                            "preview": str(data)[:80],
                        })

            _inspect_vars(clean_output, "")

            return {
                "status": "success",
                "node_id": node_id,
                "node_type": node_type,
                "duration_ms": duration_ms,
                "input_data": cls.sanitize(input_data),
                "output_data": clean_output,
                "active_ports": res.active_ports or ["main"],
                "stop_branch": res.stop_branch,
                "output_variables": output_vars,
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "error",
                "node_id": node_id,
                "node_type": node_type,
                "duration_ms": duration_ms,
                "error": str(e),
                "input_data": cls.sanitize(input_data),
                "output_data": None,
                "output_variables": [],
            }
