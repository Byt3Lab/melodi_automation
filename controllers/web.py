import json
from core.routing import Request, Response
from core.page_builder import Page, Component
from base.components import admin_layout

from ..repositories.workflow_repository import WorkflowRepository
from ..repositories.execution_repository import ExecutionRepository
from ..services.action_registry_service import ActionRegistryService
from ..services.automation_service import AutomationService
from ..models.automation_models import ExecutionStatus


class AutomationWebController:
    """
    Contrôleur Web pour l'interface d'administration de MELODI Automation Engine.
    """

    @staticmethod
    async def admin_workflows(request: Request, response: Response):
        search = request.query.get("q")
        active_only = request.query.get("active_only") == "1"

        if request.method == "POST":
            form = request.form or {}
            action_type = form.get("action_type")
            wf_id = str(form.get("workflow_id") or "")
            service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)

            if action_type == "toggle_active":
                active_val = form.get("active") in ("true", "1", "on")
                if active_val:
                    await service.activate_workflow(wf_id)
                else:
                    await service.deactivate_workflow(wf_id)
                return response.redirect("/admin/melodi_automation")

            elif action_type == "delete":
                await service.delete_workflow(wf_id)
                return response.redirect("/admin/melodi_automation")

            elif action_type == "test_run":
                raw_payload = form.get("simulated_payload") or "{}"
                try:
                    payload = json.loads(raw_payload) if isinstance(raw_payload, str) else {}
                except Exception:
                    payload = {}
                await service.test_workflow(wf_id, payload)
                return response.redirect("/admin/melodi_automation/executions")

        async with request.module.app.db.get_session() as session:
            workflows = await WorkflowRepository.list_workflows(
                session=session,
                search=search,
                active_only=active_only,
                limit=100,
            )
            total_workflows = await WorkflowRepository.count_workflows(session=session)
            active_workflows = await WorkflowRepository.count_workflows(session=session, active_only=True)
            total_executions = await ExecutionRepository.count_executions(session=session)
            failed_executions = await ExecutionRepository.count_executions(
                session=session, status=ExecutionStatus.FAILED
            )

        content = Component(
            module_name="melodi_automation",
            name="admin_workflows",
            context={
                "workflows": [w.to_dict() for w in workflows],
                "search": search or "",
                "active_only": active_only,
                "stats": {
                    "total_workflows": total_workflows,
                    "active_workflows": active_workflows,
                    "total_executions": total_executions,
                    "failed_executions": failed_executions,
                },
            },
        )
        page = Page("Automatisations & Workflows", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    async def admin_workflow_builder(request: Request, response: Response):
        wf_id_str = request.query.get("id")
        wf_id = wf_id_str if wf_id_str else None
        workflow_data = None
        service = getattr(request.module, "automation_service", None) or AutomationService(request.module.app)

        if request.method == "POST":
            form = request.form or {}

            # Action spéciale : régénération de token webhook
            if form.get("action_type") == "regenerate_webhook" and wf_id:
                await service.regenerate_webhook_token(wf_id)
                return response.redirect(f"/admin/melodi_automation/builder?id={wf_id}")

            name = form.get("name") or "Nouveau Workflow"
            description = form.get("description")
            trigger_type = form.get("trigger_type") or "event"
            active = form.get("active") in ("true", "1", "on")

            raw_nodes = form.get("nodes_json")
            raw_conns = form.get("connections_json")

            try:
                nodes = json.loads(raw_nodes) if raw_nodes else []
            except Exception:
                nodes = []

            try:
                connections = json.loads(raw_conns) if raw_conns else []
            except Exception:
                connections = []

            trigger = form.get("trigger") or ""
            trigger_parts = trigger.split(".", 1) if "." in trigger else [trigger, ""]
            trigger_module = trigger_parts[0] if trigger_type == "event" else "webhook"
            trigger_event = trigger_parts[1] if (len(trigger_parts) > 1 and trigger_type == "event") else "inbound"

            if trigger_type == "event":
                trigger_node = next(
                    (
                        node for node in nodes
                        if isinstance(node, dict) and node.get("type") in ("core.trigger_event", "trigger")
                    ),
                    None,
                )
                trigger_config = trigger_node.get("configuration") if trigger_node else None
                if isinstance(trigger_config, dict):
                    trigger_module = trigger_config.get("trigger_module") or trigger_module
                    trigger_event = trigger_config.get("trigger_event") or trigger_event

            if wf_id:
                await service.update_workflow(
                    workflow_id=wf_id,
                    name=name,
                    description=description,
                    trigger_module=trigger_module,
                    trigger_event=trigger_event,
                    trigger_type=trigger_type,
                    nodes=nodes,
                    connections=connections,
                    active=active,
                )
            else:
                new_wf = await service.create_workflow(
                    name=name,
                    description=description,
                    trigger_module=trigger_module,
                    trigger_event=trigger_event,
                    trigger_type=trigger_type,
                    nodes=nodes,
                    connections=connections,
                    active=active,
                )
                wf_id = new_wf.id

            return response.redirect("/admin/melodi_automation")

        if wf_id:
            async with request.module.app.db.get_session() as session:
                wf = await WorkflowRepository.get_workflow_by_id(session, wf_id)
                if wf:
                    workflow_data = wf.to_dict()

        available_actions = ActionRegistryService.get_available_actions(request.module.app)
        available_events = ActionRegistryService.get_available_events(request.module.app)
        available_nodes = await ActionRegistryService.get_available_nodes(request.module.app)
        from ..nodes.registry import NodeRegistry
        node_categories = NodeRegistry.get_categories()

        content = Component(
            module_name="melodi_automation",
            name="admin_workflow_builder",
            context={
                "workflow": workflow_data,
                "is_edit": workflow_data is not None,
                "available_actions": available_actions,
                "available_events": available_events,
                "available_nodes": available_nodes,
                "node_categories": node_categories,
            },
        )
        page = Page("Constructeur de Workflow", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    async def admin_executions(request: Request, response: Response):
        execution_id_str = request.query.get("id")
        status_param = request.query.get("status")
        search_param = request.query.get("q")
        workflow_id_param = request.query.get("workflow_id")
        selected_execution = None

        status_filter = None
        if status_param and status_param.lower() in ("success", "failed", "running", "pending", "cancelled"):
            try:
                status_filter = ExecutionStatus(status_param.lower())
            except ValueError:
                status_filter = None

        async with request.module.app.db.get_session() as session:
            if execution_id_str and execution_id_str.isdigit():
                selected_execution = await ExecutionRepository.get_execution_by_id(
                    session, int(execution_id_str), include_logs=True
                )

            executions = await ExecutionRepository.list_executions(
                session=session,
                workflow_id=workflow_id_param,
                status=status_filter,
                search=search_param,
                limit=60,
            )

            # Si aucune sélection explicite n'a été faite et qu'on a des exécutions, charger la première
            if not selected_execution and executions:
                selected_execution = await ExecutionRepository.get_execution_by_id(
                    session, executions[0].id, include_logs=True
                )

            total_count = await ExecutionRepository.count_executions(session=session)
            success_count = await ExecutionRepository.count_executions(session=session, status=ExecutionStatus.SUCCESS)
            failed_count = await ExecutionRepository.count_executions(session=session, status=ExecutionStatus.FAILED)
            running_count = await ExecutionRepository.count_executions(session=session, status=ExecutionStatus.RUNNING)

        content = Component(
            module_name="melodi_automation",
            name="admin_executions",
            context={
                "executions": [e.to_dict() for e in executions],
                "selected_execution": selected_execution.to_dict(include_logs=True) if selected_execution else None,
                "selected_id": int(execution_id_str) if (execution_id_str and execution_id_str.isdigit()) else (selected_execution.id if selected_execution else None),
                "is_explicit_selection": bool(execution_id_str and execution_id_str.isdigit()),
                "current_status": status_param or "all",
                "search_query": search_param or "",
                "workflow_filter": workflow_id_param or "",
                "stats": {
                    "total": total_count,
                    "success": success_count,
                    "failed": failed_count,
                    "running": running_count,
                },
            },
        )
        page = Page("Journal des Exécutions", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    async def admin_doc(request: Request, response: Response):
        """Page de documentation de MELODI Automation Engine."""
        content = Component(
            module_name="melodi_automation",
            name="admin_doc",
            context={},
        )
        page = Page("Documentation — Automation Engine", admin_layout(content))
        return await response.render_page(page)
