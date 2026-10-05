import asyncio
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.automation_models import WorkflowModel
from ..repositories.workflow_repository import WorkflowRepository
from .execution_engine import ExecutionEngine
from .executor_interface import AutomationExecutor, AsyncInternalExecutor


class AutomationService:
    """
    Service d'orchestration global de l'Automation Engine.
    Gère la persistance des workflows et la liaison dynamique avec le système de hooks/événements.
    """

    def __init__(self, app: Any, executor: Optional[AutomationExecutor] = None):
        self.app = app
        self.executor = executor or AsyncInternalExecutor()
        self._subscribed_events: Dict[str, Any] = {}

    def get_session(self) -> AsyncSession:
        return self.app.db.get_session()

    @staticmethod
    def _build_trigger_context(workflow: WorkflowModel, payload: Dict[str, Any], webhook: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = {
            "event": {
                "module": workflow.trigger_module,
                "name": workflow.trigger_event,
                "payload": payload,
            },
            "payload": payload,
            "steps": {},
            "variables": {},
            "workflow": {
                "id": workflow.id,
                "name": workflow.name,
                "version": workflow.version,
            },
        }
        if webhook is not None:
            context["webhook"] = webhook
        return context

    async def register_all_active_triggers(self):
        """
        Scanne tous les workflows actifs en base et s'abonne aux événements correspondants
        auprès de app.hook_manager.event_listener.
        """
        async with self.get_session() as session:
            active_workflows = await WorkflowRepository.get_all_active_workflows(session)

        triggers = {
            (workflow.trigger_module, workflow.trigger_event)
            for workflow in active_workflows
            if workflow.trigger_type == "event" and workflow.trigger_module and workflow.trigger_event
        }
        self._sync_event_subscriptions(triggers)

    def _sync_event_subscriptions(self, triggers):
        desired = {f"{module}.{event}" for module, event in triggers}
        listener = getattr(getattr(self.app, "hook_manager", None), "event_listener", None)
        for key, callback in list(self._subscribed_events.items()):
            if key not in desired:
                module, event = key.split(".", 1)
                if listener:
                    listener.remove(module, event, callback)
                del self._subscribed_events[key]
        for module, event in triggers:
            self._subscribe_event(module, event)

    async def _refresh_event_subscriptions(self):
        async with self.get_session() as session:
            active_workflows = await WorkflowRepository.get_all_active_workflows(session)
        triggers = {
            (workflow.trigger_module, workflow.trigger_event)
            for workflow in active_workflows
            if workflow.trigger_type == "event" and workflow.trigger_module and workflow.trigger_event
        }
        self._sync_event_subscriptions(triggers)

    def _subscribe_event(self, module_name: str, event_name: str):
        key = f"{module_name}.{event_name}"
        if key in self._subscribed_events:
            return

        async def _listener(payload: Any = None):
            await self.handle_event_notification(module_name, event_name, payload)

        self._subscribed_events[key] = _listener

        if hasattr(self.app, "hook_manager") and hasattr(self.app.hook_manager, "event_listener"):
            self.app.hook_manager.event_listener.add(module_name, event_name, _listener)

    async def handle_event_notification(self, module_name: str, event_name: str, payload: Any):
        """
        Invoqué dès qu'un événement est émis dans l'ERP. Recherche les workflows actifs
        et les transmet à l'exécuteur en arrière-plan.
        """
        async with self.get_session() as session:
            workflows = await WorkflowRepository.get_active_workflows_for_event(
                session, module_name, event_name
            )

        if not workflows:
            return

        for wf in workflows:
            normalized_payload = payload if isinstance(payload, dict) else {"data": payload}
            context = self._build_trigger_context(wf, normalized_payload)
            context["event"]["module"] = module_name
            context["event"]["name"] = event_name
            # Déclenchement non-bloquant
            await self.executor.run(ExecutionEngine, wf, context, self.app)

    async def create_workflow(
        self,
        name: str,
        description: Optional[str] = None,
        trigger_module: str = "",
        trigger_event: str = "",
        nodes: Optional[List[Dict[str, Any]]] = None,
        connections: Optional[List[Dict[str, Any]]] = None,
        active: bool = False,
        created_by: Optional[str] = None,
        trigger_type: str = "event",
        webhook_token: Optional[str] = None,
    ) -> WorkflowModel:
        async with self.get_session() as session:
            wf = await WorkflowRepository.create_workflow(
                session=session,
                name=name,
                description=description,
                trigger_module=trigger_module,
                trigger_event=trigger_event,
                nodes=nodes,
                connections=connections,
                active=active,
                created_by=created_by,
                trigger_type=trigger_type,
                webhook_token=webhook_token,
            )
            await session.commit()
            if active and trigger_module and trigger_event and trigger_type == "event":
                self._subscribe_event(trigger_module, trigger_event)
            return wf

    async def update_workflow(self, workflow_id: str, **kwargs) -> Optional[WorkflowModel]:
        async with self.get_session() as session:
            wf = await WorkflowRepository.update_workflow(session, workflow_id, **kwargs)
            if wf:
                await session.commit()
                await self._refresh_event_subscriptions()
            return wf

    async def list_workflow_versions(self, workflow_id: str):
        async with self.get_session() as session:
            workflow = await WorkflowRepository.get_workflow_by_id(session, workflow_id)
            if not workflow:
                return None
            await WorkflowRepository._ensure_current_snapshot(session, workflow)
            await session.commit()
            return await WorkflowRepository.list_workflow_versions(session, workflow_id)

    async def restore_workflow_version(self, workflow_id: str, version: int) -> Optional[WorkflowModel]:
        async with self.get_session() as session:
            workflow = await WorkflowRepository.restore_workflow_version(session, workflow_id, version)
            if workflow:
                await session.commit()
        if workflow:
            await self._refresh_event_subscriptions()
        return workflow

    async def delete_workflow(self, workflow_id: str) -> bool:
        async with self.get_session() as session:
            res = await WorkflowRepository.delete_workflow(session, workflow_id)
            if res:
                await session.commit()
        if res:
            await self._refresh_event_subscriptions()
            return res

    async def activate_workflow(self, workflow_id: str) -> Optional[WorkflowModel]:
        async with self.get_session() as session:
            wf = await WorkflowRepository.set_active(session, workflow_id, True)
            if wf:
                await session.commit()
                await self._refresh_event_subscriptions()
            return wf

    async def deactivate_workflow(self, workflow_id: str) -> Optional[WorkflowModel]:
        async with self.get_session() as session:
            wf = await WorkflowRepository.set_active(session, workflow_id, False)
            if wf:
                await session.commit()
                await self._refresh_event_subscriptions()
            return wf

    async def test_workflow(self, workflow_id: str, simulated_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Exécution manuelle immédiate d'un workflow (synchrone pour l'appelant de test).
        """
        async with self.get_session() as session:
            wf = await WorkflowRepository.get_workflow_by_id(session, workflow_id)

        if not wf:
            raise ValueError(f"Workflow {workflow_id} introuvable.")

        payload = simulated_payload or {}
        webhook = None
        if wf.trigger_type == "webhook":
            webhook = {
                "body": {"payload": payload},
                "headers": {"content-type": "application/json"},
                "query": {},
                "method": "POST",
            }
        context = self._build_trigger_context(wf, payload, webhook)

        # Exécution synchrone directe
        return await ExecutionEngine.execute(wf, context, self.app)

    async def handle_webhook_trigger(self, token: str, request_data: Dict[str, Any], sync_wait: bool = False) -> Dict[str, Any]:
        """
        Déclenche le workflow associé à un webhook entrant.
        """
        async with self.get_session() as session:
            wf = await WorkflowRepository.get_active_workflow_by_webhook_token(session, token)

        if not wf:
            raise ValueError(f"Aucun workflow actif trouvé pour le webhook token '{token}'.")

        body_data = request_data.get("body") if isinstance(request_data, dict) else {}
        if not isinstance(body_data, dict) or not isinstance(body_data.get("payload"), dict):
            raise ValueError("Corps webhook invalide : un objet JSON 'payload' est requis.")
        payload = body_data["payload"]
        context = self._build_trigger_context(wf, payload, request_data)

        if sync_wait:
            return await ExecutionEngine.execute(wf, context, self.app)

        # Déclenchement non-bloquant en tâche de fond
        await self.executor.run(ExecutionEngine, wf, context, self.app)
        return {
            "status": "received",
            "workflow_id": wf.id,
            "workflow_name": wf.name,
            "message": "Webhook reçu et exécution lancée en arrière-plan.",
        }

    async def regenerate_webhook_token(self, workflow_id: str) -> str:
        """
        Génère un nouveau token sécurisé pour un workflow webhook.
        """
        async with self.get_session() as session:
            token = await WorkflowRepository.generate_webhook_token(session, workflow_id)
            if not token:
                raise ValueError(f"Workflow {workflow_id} introuvable.")
            await session.commit()
            return token

