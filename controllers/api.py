import json
from typing import Any
from core.routing import Request, Response
from ..services.automation_service import AutomationService
from ..services.action_registry_service import ActionRegistryService
from ..repositories.workflow_repository import WorkflowRepository
from ..repositories.execution_repository import ExecutionRepository


class AutomationAPIController:
    """
    Contrôleur API REST d'administration pour l'Automation Engine.
    Endpoints accessibles via /api/admin/automation/... ou /api/admin/melodi_automation/...
    """

    @staticmethod
    async def list_workflows(request: Request, response: Response):
        search = request.query.get("q")
        active_only = request.query.get("active_only") in ("true", "1")
        limit = int(request.query.get("limit") or 50)
        offset = int(request.query.get("offset") or 0)

        async with request.module.app.db.get_session() as session:
            workflows = await WorkflowRepository.list_workflows(
                session=session,
                search=search,
                active_only=active_only,
                limit=limit,
                offset=offset,
            )
            total = await WorkflowRepository.count_workflows(
                session=session,
                search=search,
                active_only=active_only,
            )

        return response.render_json({
            "status": "success",
            "total": total,
            "count": len(workflows),
            "data": [w.to_dict() for w in workflows],
        })

    @staticmethod
    async def create_workflow(request: Request, response: Response):
        data = request.json or {}
        name = data.get("name")
        if not name:
            return response.render_json({"status": "error", "message": "Le nom du workflow est requis."}, status_code=400)

        trigger_module = data.get("trigger_module", "")
        trigger_event = data.get("trigger_event", "")
        # Si un champ combiné 'trigger' est fourni (ex: 'commerce.order.created')
        if not trigger_module and not trigger_event and data.get("trigger"):
            parts = str(data.get("trigger")).split(".", 1)
            trigger_module = parts[0]
            trigger_event = parts[1] if len(parts) > 1 else ""

        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        try:
            wf = await service.create_workflow(
                name=name,
                description=data.get("description"),
                trigger_module=trigger_module,
                trigger_event=trigger_event,
                nodes=data.get("nodes", []),
                connections=data.get("connections", []),
                active=bool(data.get("active", False)),
                created_by=data.get("created_by") or "admin",
                trigger_type=data.get("trigger_type", "event"),
                webhook_token=data.get("webhook_token"),
            )
            return response.render_json({"status": "success", "data": wf.to_dict()}, status_code=201)
        except Exception as e:
            return response.render_json({"status": "error", "message": str(e)}, status_code=400)

    @staticmethod
    async def get_workflow(request: Request, response: Response):
        workflow_id = request.query.get("id") or request.params.get("id") or ""
        async with request.module.app.db.get_session() as session:
            wf = await WorkflowRepository.get_workflow_by_id(session, workflow_id)

        if not wf:
            return response.render_json({"status": "error", "message": "Workflow introuvable."}, status_code=404)

        return response.render_json({"status": "success", "data": wf.to_dict()})

    @staticmethod
    async def get_workflow_versions(request: Request, response: Response):
        workflow_id = request.query.get("id") or request.query.get("workflow_id") or ""
        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        versions = await service.list_workflow_versions(workflow_id)
        if versions is None:
            return response.render_json({"status": "error", "message": "Workflow introuvable."}, status_code=404)

        raw_version = request.query.get("version")
        if raw_version:
            try:
                version = int(raw_version)
            except ValueError:
                return response.render_json({"status": "error", "message": "Numéro de version invalide."}, status_code=400)
            selected = next((item for item in versions if item.version == version), None)
            if not selected:
                return response.render_json({"status": "error", "message": "Version introuvable."}, status_code=404)
            return response.render_json({"status": "success", "data": selected.to_dict(include_snapshot=True)})

        return response.render_json({
            "status": "success",
            "count": len(versions),
            "data": [item.to_dict() for item in versions],
        })

    @staticmethod
    async def restore_workflow_version(request: Request, response: Response):
        data = request.json or {}
        workflow_id = str(data.get("workflow_id") or data.get("id") or "")
        try:
            version = int(data.get("version"))
        except (TypeError, ValueError):
            return response.render_json({"status": "error", "message": "Numéro de version invalide."}, status_code=400)

        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        workflow = await service.restore_workflow_version(workflow_id, version)
        if not workflow:
            return response.render_json({"status": "error", "message": "Workflow ou version introuvable."}, status_code=404)
        return response.render_json({"status": "success", "data": workflow.to_dict()})

    @staticmethod
    async def update_workflow(request: Request, response: Response):
        workflow_id = request.query.get("id") or request.params.get("id") or ""
        data = request.json or {}

        trigger_module = data.get("trigger_module")
        trigger_event = data.get("trigger_event")
        if trigger_module is None and trigger_event is None and data.get("trigger"):
            parts = str(data.get("trigger")).split(".", 1)
            trigger_module = parts[0]
            trigger_event = parts[1] if len(parts) > 1 else ""

        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        try:
            wf = await service.update_workflow(
                workflow_id=workflow_id,
                name=data.get("name"),
                description=data.get("description"),
                trigger_module=trigger_module,
                trigger_event=trigger_event,
                nodes=data.get("nodes"),
                connections=data.get("connections"),
                active=data.get("active"),
                trigger_type=data.get("trigger_type"),
                webhook_token=data.get("webhook_token"),
            )
            if not wf:
                return response.render_json({"status": "error", "message": "Workflow introuvable."}, status_code=404)
            return response.render_json({"status": "success", "data": wf.to_dict()})
        except Exception as e:
            return response.render_json({"status": "error", "message": str(e)}, status_code=400)

    @staticmethod
    async def delete_workflow(request: Request, response: Response):
        raw_id = request.query.get("id") or request.params.get("id") or (request.json.get("id") if request.json else "") or ""
        workflow_id = str(raw_id)
        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        success = await service.delete_workflow(workflow_id)
        if not success:
            return response.render_json({"status": "error", "message": "Workflow introuvable."}, status_code=404)
        return response.render_json({"status": "success", "message": f"Workflow {workflow_id} supprimé avec succès."})

    @staticmethod
    async def activate_workflow(request: Request, response: Response):
        raw_id = request.query.get("id") or request.params.get("id") or (request.json.get("id") if request.json else "") or ""
        workflow_id = str(raw_id)
        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        wf = await service.activate_workflow(workflow_id)
        if not wf:
            return response.render_json({"status": "error", "message": "Workflow introuvable."}, status_code=404)
        return response.render_json({"status": "success", "message": "Workflow activé.", "data": wf.to_dict()})

    @staticmethod
    async def deactivate_workflow(request: Request, response: Response):
        raw_id = request.query.get("id") or request.params.get("id") or (request.json.get("id") if request.json else "") or ""
        workflow_id = str(raw_id)
        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        wf = await service.deactivate_workflow(workflow_id)
        if not wf:
            return response.render_json({"status": "error", "message": "Workflow introuvable."}, status_code=404)
        return response.render_json({"status": "success", "message": "Workflow désactivé.", "data": wf.to_dict()})

    @staticmethod
    async def test_workflow(request: Request, response: Response):
        data = request.json or {}
        raw_id = request.query.get("id") or request.params.get("id") or data.get("workflow_id") or data.get("id") or ""
        workflow_id = str(raw_id)
        payload = data.get("payload") or {}

        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        try:
            result = await service.test_workflow(workflow_id, payload)
            return response.render_json({"status": "success", "result": result})
        except Exception as e:
            return response.render_json({"status": "error", "message": str(e)}, status_code=400)

    @staticmethod
    async def list_workflow_executions(request: Request, response: Response):
        workflow_id = request.query.get("id") or request.params.get("id") or ""
        limit = int(request.query.get("limit") or 50)
        offset = int(request.query.get("offset") or 0)

        async with request.module.app.db.get_session() as session:
            executions = await ExecutionRepository.list_executions(
                session=session,
                workflow_id=workflow_id,
                limit=limit,
                offset=offset,
            )
            total = await ExecutionRepository.count_executions(
                session=session,
                workflow_id=workflow_id,
            )

        return response.render_json({
            "status": "success",
            "total": total,
            "count": len(executions),
            "data": [e.to_dict() for e in executions],
        })

    @staticmethod
    async def get_execution(request: Request, response: Response):
        execution_id = int(request.params.get("id") or 0)
        async with request.module.app.db.get_session() as session:
            execution = await ExecutionRepository.get_execution_by_id(session, execution_id, include_logs=True)

        if not execution:
            return response.render_json({"status": "error", "message": "Exécution introuvable."}, status_code=404)

        return response.render_json({"status": "success", "data": execution.to_dict(include_logs=True)})

    @staticmethod
    async def get_meta_actions(request: Request, response: Response):
        actions = ActionRegistryService.get_available_actions(request.module.app)
        return response.render_json({"status": "success", "count": len(actions), "data": actions})

    @staticmethod
    async def get_meta_events(request: Request, response: Response):
        events = ActionRegistryService.get_available_events(request.module.app)
        return response.render_json({"status": "success", "count": len(events), "data": events})

    @staticmethod
    async def handle_webhook(request: Request, response: Response):
        token = request.params.get("token") or ""
        if not token:
            return response.render_json({"status": "error", "message": "Token de webhook manquant."}, status_code=400)

        # Extraction des données du webhook
        body = request.json
        if body is None:
            body = request.form if getattr(request, "form", None) else {}

        request_data = {
            "body": body,
            "headers": dict(getattr(request, "headers", {})),
            "query": dict(getattr(request, "query", {})),
            "method": request.method,
        }

        if not isinstance(body, dict) or not isinstance(body.get("payload"), dict):
            return response.render_json({
                "status": "error",
                "message": "Corps webhook invalide : un objet JSON 'payload' est requis.",
            }, status_code=400)

        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        sync_wait = (getattr(request, "query", {}).get("sync") == "1")

        try:
            res = await service.handle_webhook_trigger(token, request_data, sync_wait=sync_wait)
            return response.render_json(res, status_code=200)
        except ValueError as ve:
            return response.render_json({"status": "error", "message": str(ve)}, status_code=404)
        except Exception as e:
            return response.render_json({"status": "error", "message": str(e)}, status_code=500)

    @staticmethod
    async def regenerate_webhook_token(request: Request, response: Response):
        workflow_id = request.query.get("id") or request.params.get("id") or ""
        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)
        try:
            new_token = await service.regenerate_webhook_token(workflow_id)
            return response.render_json({
                "status": "success",
                "webhook_token": new_token,
                "webhook_url": f"/api/melodi_automation/webhook/{new_token}",
            })
        except ValueError as ve:
            return response.render_json({"status": "error", "message": str(ve)}, status_code=404)
        except Exception as e:
            return response.render_json({"status": "error", "message": str(e)}, status_code=500)

    @staticmethod
    async def get_meta_nodes(request: Request, response: Response):
        from ..nodes.registry import NodeRegistry
        nodes = await ActionRegistryService.get_available_nodes(request.module.app)
        categories = NodeRegistry.get_categories()
        return response.render_json({
            "status": "success",
            "categories": categories,
            "count": len(nodes),
            "data": nodes,
        })

    @staticmethod
    async def test_node_step(request: Request, response: Response):
        data = request.json or {}
        node_type = data.get("type") or data.get("node_type")
        config = data.get("configuration") or data.get("config") or {}
        input_data = data.get("input_data") or data.get("input") or {}
        context = data.get("context") or {"payload": input_data, "steps": {}}

        from ..nodes.registry import NodeRegistry
        node = NodeRegistry.get(node_type)
        if not node:
            return response.render_json({"status": "error", "message": f"Nœud inconnu: '{node_type}'"}, status_code=404)

        try:
            res = await node.execute(input_data, config, context, request.module.app)
            return response.render_json({
                "status": "success",
                "output_data": res.output_data,
                "active_ports": res.active_ports,
                "stop_branch": res.stop_branch,
            })
        except Exception as e:
            return response.render_json({
                "status": "error",
                "message": str(e),
            }, status_code=400)

    @staticmethod
    async def simulate_workflow(request: Request, response: Response):
        """
        POST /api/melodi_automation/workflows/simulate
        Exécute en mémoire le graphe de nœuds et connexions fourni avec un payload initial.
        Retourne la chronologie, les entrées/sorties par nœud et l'arbre des variables disponibles.
        """
        data = request.json or {}
        nodes = data.get("nodes") or []
        connections = data.get("connections") or []
        initial_payload = data.get("initial_payload") or data.get("payload") or {}

        from ..services.execution_engine import ExecutionEngine
        try:
            result = await ExecutionEngine.simulate_graph(
                nodes_list=nodes,
                connections_list=connections,
                initial_payload=initial_payload,
                app=request.module.app,
            )
            return response.render_json(result)
        except Exception as e:
            return response.render_json({
                "status": "error",
                "message": f"Erreur lors de la simulation : {str(e)}",
            }, status_code=400)

    # ─── Import / Export ────────────────────────────────────────────────────────

    @staticmethod
    async def export_workflow(request: Request, response: Response):
        """
        GET /api/melodi_automation/workflows/export?id=2
        ou GET /api/melodi_automation/workflows/<id>/export
        Génère l'export JSON et retourne le lien direct de téléchargement du fichier.
        """
        raw_id = request.query.get("id") or request.params.get("id") or (request.json.get("id") if request.json else "") or ""
        workflow_id = str(raw_id)
        async with request.module.app.db.get_session() as session:
            wf = await WorkflowRepository.get_workflow_by_id(session, workflow_id)
            if not wf:
                return response.render_json({"status": "error", "message": "Workflow introuvable."}, status_code=404)

        export_data = {
            "melodi_automation_version": "1.0",
            "name": wf.name,
            "description": wf.description or "",
            "trigger_type": getattr(wf, "trigger_type", "event") or "event",
            "trigger_module": wf.trigger_module,
            "trigger_event": wf.trigger_event,
            "nodes": wf.nodes or [],
            "connections": wf.connections or [],
        }
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in wf.name)[:40]
        filename = f"workflow_{safe_name}.json"
        download_url = f"/api/melodi_automation/workflows/download?id={wf.id}"

        return response.render_json({
            "status": "success",
            "workflow_id": wf.id,
            "filename": filename,
            "download_url": download_url,
            "data": export_data,
        })

    @staticmethod
    async def download_workflow_file(request: Request, response: Response):
        """
        GET /api/melodi_automation/workflows/download?id=2
        ou GET /api/melodi_automation/workflows/<id>/download
        Sert le fichier .json en pièce jointe téléchargeable.
        """
        raw_id = request.query.get("id") or request.params.get("id") or ""
        workflow_id = str(raw_id)
        async with request.module.app.db.get_session() as session:
            wf = await WorkflowRepository.get_workflow_by_id(session, workflow_id)
            if not wf:
                return response.render_json({"status": "error", "message": "Workflow introuvable."}, status_code=404)

        export_data = {
            "melodi_automation_version": "1.0",
            "name": wf.name,
            "description": wf.description or "",
            "trigger_type": getattr(wf, "trigger_type", "event") or "event",
            "trigger_module": wf.trigger_module,
            "trigger_event": wf.trigger_event,
            "nodes": wf.nodes or [],
            "connections": wf.connections or [],
        }
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in wf.name)[:40]
        filename = f"workflow_{safe_name}.json"

        raw = json.dumps(export_data, ensure_ascii=False, indent=2)
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        from quart import Response as QuartResponse
        return QuartResponse(raw, status=200, headers=headers)

    @staticmethod
    async def import_workflow(request: Request, response: Response):
        """
        POST /api/melodi_automation/workflows/import
        Importe un workflow depuis un JSON (body ou fichier multipart).
        Crée un nouveau workflow DRAFT (active=False) sans écraser l'existant.
        """
        data = None

        # Tentative lecture depuis le corps JSON
        if request.json:
            data = request.json
        else:
            # Tentative lecture depuis multipart/form-data
            form = request.form or {}
            raw = form.get("workflow_json") or form.get("file")
            if raw:
                try:
                    data = json.loads(raw)
                except Exception:
                    pass

        if not data:
            return response.render_json(
                {"status": "error", "message": "Aucune donnée JSON de workflow fournie."},
                status_code=400,
            )

        # Validation minimale
        if "nodes" not in data or "connections" not in data:
            return response.render_json(
                {"status": "error", "message": "JSON invalide : champs 'nodes' et 'connections' requis."},
                status_code=400,
            )

        name = (data.get("name") or "Workflow importé") + " (Importé)"
        description = data.get("description") or ""
        trigger_type = data.get("trigger_type") or "event"
        trigger_module = data.get("trigger_module") or "unknown"
        trigger_event = data.get("trigger_event") or "unknown"
        nodes = data.get("nodes") or []
        connections = data.get("connections") or []

        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)

        try:
            new_wf = await service.create_workflow(
                name=name,
                description=description,
                trigger_module=trigger_module,
                trigger_event=trigger_event,
                trigger_type=trigger_type,
                nodes=nodes,
                connections=connections,
                active=False,
            )
            return response.render_json({
                "status": "success",
                "message": f"Workflow '{new_wf.name}' importé avec succès.",
                "data": new_wf.to_dict(),
            })
        except Exception as e:
            return response.render_json({"status": "error", "message": str(e)}, status_code=500)

