import copy
import secrets
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, or_, and_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.automation_models import WorkflowModel, WorkflowVersionModel, WorkflowStatus


class WorkflowRepository:

    @staticmethod
    def _definition_snapshot(workflow: WorkflowModel) -> Dict[str, Any]:
        nodes = copy.deepcopy(workflow.nodes or [])
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("configuration"), dict):
                node["configuration"].pop("webhook_token", None)
        return {
            "name": workflow.name,
            "description": workflow.description,
            "trigger_module": workflow.trigger_module,
            "trigger_event": workflow.trigger_event,
            "trigger_type": getattr(workflow, "trigger_type", "event") or "event",
            "nodes": nodes,
            "connections": copy.deepcopy(workflow.connections or []),
            "custom_types": copy.deepcopy(getattr(workflow, "custom_types", []) or []),
        }

    @staticmethod
    async def _save_version_snapshot(
        session: AsyncSession,
        workflow: WorkflowModel,
        change_summary: str,
    ) -> WorkflowVersionModel:
        version_record = WorkflowVersionModel(
            workflow_id=workflow.id,
            version=workflow.version,
            snapshot=WorkflowRepository._definition_snapshot(workflow),
            change_summary=change_summary,
            created_by=workflow.created_by,
            created_at=datetime.utcnow(),
        )
        session.add(version_record)
        await session.flush()
        return version_record

    @staticmethod
    async def _ensure_current_snapshot(session: AsyncSession, workflow: WorkflowModel) -> None:
        records = await WorkflowRepository.list_workflow_versions(session, workflow.id)
        if not any(record.version == workflow.version for record in records):
            await WorkflowRepository._save_version_snapshot(
                session, workflow, "État initial enregistré dans l'historique"
            )

    @staticmethod
    async def list_workflow_versions(
        session: AsyncSession,
        workflow_id: str,
    ) -> List[WorkflowVersionModel]:
        stmt = (
            select(WorkflowVersionModel)
            .where(WorkflowVersionModel.workflow_id == workflow_id)
            .order_by(WorkflowVersionModel.version.desc())
        )
        result = await session.execute(stmt)
        records = [
            record for record in result.scalars().all()
            if record.workflow_id == workflow_id
        ]
        return sorted(records, key=lambda record: record.version, reverse=True)

    @staticmethod
    async def get_workflow_version(
        session: AsyncSession,
        workflow_id: str,
        version: int,
    ) -> Optional[WorkflowVersionModel]:
        records = await WorkflowRepository.list_workflow_versions(session, workflow_id)
        return next((record for record in records if record.version == version), None)

    @staticmethod
    async def get_workflow_by_id(session: AsyncSession, workflow_id: str) -> Optional[WorkflowModel]:
        stmt = select(WorkflowModel).where(WorkflowModel.id == workflow_id)
        try:
            res = await session.execute(stmt)
            return res.scalar_one_or_none()
        except Exception as e:
            if any(k in str(e) for k in ("trigger_type", "webhook_token", "integer", "character varying", "column")):
                from sqlalchemy import text
                from ..config import AutomationTables
                try:
                    await session.rollback()
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.EXECUTION_LOGS} DROP CONSTRAINT IF EXISTS {AutomationTables.EXECUTION_LOGS}_workflow_id_fkey;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.EXECUTIONS} DROP CONSTRAINT IF EXISTS {AutomationTables.EXECUTIONS}_workflow_id_fkey;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.WORKFLOWS} ALTER COLUMN id TYPE VARCHAR(36) USING id::VARCHAR;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.EXECUTIONS} ALTER COLUMN workflow_id TYPE VARCHAR(36) USING workflow_id::VARCHAR;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.EXECUTION_LOGS} ALTER COLUMN workflow_id TYPE VARCHAR(36) USING workflow_id::VARCHAR;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.WORKFLOWS} ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(50) DEFAULT 'event';"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.WORKFLOWS} ADD COLUMN IF NOT EXISTS webhook_token VARCHAR(100);"
                    ))
                    await session.commit()
                    res = await session.execute(stmt)
                    return res.scalar_one_or_none()
                except Exception:
                    pass
            raise

    @staticmethod
    async def list_workflows(
        session: AsyncSession,
        search: Optional[str] = None,
        active_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowModel]:
        stmt = select(WorkflowModel)
        conditions = []
        if active_only:
            conditions.append(WorkflowModel.active == True)
        if search:
            search_term = f"%{search.strip()}%"
            conditions.append(
                or_(
                    WorkflowModel.name.ilike(search_term),
                    WorkflowModel.description.ilike(search_term),
                    WorkflowModel.trigger_module.ilike(search_term),
                    WorkflowModel.trigger_event.ilike(search_term),
                )
            )
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(WorkflowModel.updated_at.desc(), WorkflowModel.id.desc()).limit(limit).offset(offset)
        try:
            res = await session.execute(stmt)
            return list(res.scalars().all())
        except Exception as e:
            if any(k in str(e) for k in ("trigger_type", "webhook_token", "integer", "character varying", "column")):
                from sqlalchemy import text
                from ..config import AutomationTables
                try:
                    await session.rollback()
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.EXECUTION_LOGS} DROP CONSTRAINT IF EXISTS {AutomationTables.EXECUTION_LOGS}_workflow_id_fkey;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.EXECUTIONS} DROP CONSTRAINT IF EXISTS {AutomationTables.EXECUTIONS}_workflow_id_fkey;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.WORKFLOWS} ALTER COLUMN id TYPE VARCHAR(36) USING id::VARCHAR;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.EXECUTIONS} ALTER COLUMN workflow_id TYPE VARCHAR(36) USING workflow_id::VARCHAR;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.EXECUTION_LOGS} ALTER COLUMN workflow_id TYPE VARCHAR(36) USING workflow_id::VARCHAR;"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.WORKFLOWS} ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(50) DEFAULT 'event';"
                    ))
                    await session.execute(text(
                        f"ALTER TABLE {AutomationTables.WORKFLOWS} ADD COLUMN IF NOT EXISTS webhook_token VARCHAR(100);"
                    ))
                    await session.commit()
                    res = await session.execute(stmt)
                    return list(res.scalars().all())
                except Exception:
                    pass
            raise

    @staticmethod
    async def count_workflows(
        session: AsyncSession,
        search: Optional[str] = None,
        active_only: bool = False,
    ) -> int:
        stmt = select(func.count(WorkflowModel.id))
        conditions = []
        if active_only:
            conditions.append(WorkflowModel.active == True)
        if search:
            search_term = f"%{search.strip()}%"
            conditions.append(
                or_(
                    WorkflowModel.name.ilike(search_term),
                    WorkflowModel.description.ilike(search_term),
                    WorkflowModel.trigger_module.ilike(search_term),
                    WorkflowModel.trigger_event.ilike(search_term),
                )
            )
        if conditions:
            stmt = stmt.where(and_(*conditions))
        res = await session.execute(stmt)
        return res.scalar() or 0

    @staticmethod
    async def create_workflow(
        session: AsyncSession,
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
        custom_types: Optional[List[Dict[str, Any]]] = None,
    ) -> WorkflowModel:
        if trigger_type == "webhook" and not webhook_token:
            webhook_token = f"wh_{secrets.token_urlsafe(16)}"

        workflow = WorkflowModel(
            name=name,
            description=description,
            trigger_module=trigger_module,
            trigger_event=trigger_event,
            trigger_type=trigger_type,
            webhook_token=webhook_token,
            nodes=nodes or [],
            connections=connections or [],
            custom_types=custom_types or [],
            active=active,
            version=1,
            created_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(workflow)
        await session.flush()
        await WorkflowRepository._save_version_snapshot(session, workflow, "Création du workflow")
        return workflow

    @staticmethod
    async def update_workflow(
        session: AsyncSession,
        workflow_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        trigger_module: Optional[str] = None,
        trigger_event: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        connections: Optional[List[Dict[str, Any]]] = None,
        active: Optional[bool] = None,
        trigger_type: Optional[str] = None,
        webhook_token: Optional[str] = None,
        custom_types: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[WorkflowModel]:
        workflow = await WorkflowRepository.get_workflow_by_id(session, workflow_id)
        if not workflow:
            return None

        # Workflow metadata and graph changes create immutable definition revisions.
        definition_changed = False
        if name is not None and name != workflow.name:
            definition_changed = True
        if description is not None and description != workflow.description:
            definition_changed = True
        if nodes is not None and nodes != workflow.nodes:
            workflow.nodes = nodes
            definition_changed = True
        if connections is not None and connections != workflow.connections:
            workflow.connections = connections
            definition_changed = True
        if custom_types is not None and custom_types != getattr(workflow, "custom_types", []):
            workflow.custom_types = custom_types
            definition_changed = True
        if trigger_module is not None and trigger_module != workflow.trigger_module:
            workflow.trigger_module = trigger_module
            definition_changed = True
        if trigger_event is not None and trigger_event != workflow.trigger_event:
            workflow.trigger_event = trigger_event
            definition_changed = True
        if trigger_type is not None and trigger_type != getattr(workflow, "trigger_type", "event"):
            workflow.trigger_type = trigger_type
            if trigger_type == "webhook" and not workflow.webhook_token:
                workflow.webhook_token = f"wh_{secrets.token_urlsafe(16)}"
            elif trigger_type == "event":
                workflow.webhook_token = None
            definition_changed = True
        if webhook_token is not None and webhook_token != getattr(workflow, "webhook_token", None):
            workflow.webhook_token = webhook_token
            definition_changed = True

        if definition_changed:
            await WorkflowRepository._ensure_current_snapshot(session, workflow)
            workflow.version += 1

        if name is not None:
            workflow.name = name
        if description is not None:
            workflow.description = description
        if active is not None:
            workflow.active = active

        workflow.updated_at = datetime.utcnow()
        await session.flush()
        if definition_changed:
            await WorkflowRepository._save_version_snapshot(
                session, workflow, "Définition modifiée"
            )
        return workflow

    @staticmethod
    async def restore_workflow_version(
        session: AsyncSession,
        workflow_id: str,
        version: int,
    ) -> Optional[WorkflowModel]:
        workflow = await WorkflowRepository.get_workflow_by_id(session, workflow_id)
        if not workflow:
            return None

        selected = await WorkflowRepository.get_workflow_version(session, workflow_id, version)
        if not selected:
            return None

        await WorkflowRepository._ensure_current_snapshot(session, workflow)
        snapshot = selected.snapshot or {}
        workflow.name = snapshot.get("name", workflow.name)
        workflow.description = snapshot.get("description", workflow.description)
        workflow.trigger_module = snapshot.get("trigger_module", workflow.trigger_module)
        workflow.trigger_event = snapshot.get("trigger_event", workflow.trigger_event)
        workflow.trigger_type = snapshot.get("trigger_type", workflow.trigger_type)
        workflow.nodes = snapshot.get("nodes", workflow.nodes)
        workflow.connections = snapshot.get("connections", workflow.connections)
        workflow.custom_types = snapshot.get("custom_types", getattr(workflow, "custom_types", []))
        if workflow.trigger_type == "webhook" and not workflow.webhook_token:
            workflow.webhook_token = f"wh_{secrets.token_urlsafe(16)}"
        workflow.version += 1
        workflow.updated_at = datetime.utcnow()
        await session.flush()
        await WorkflowRepository._save_version_snapshot(
            session, workflow, f"Restauration de la version {version}"
        )
        return workflow

    @staticmethod
    async def delete_workflow(session: AsyncSession, workflow_id: str) -> bool:
        workflow = await WorkflowRepository.get_workflow_by_id(session, workflow_id)
        if not workflow:
            return False
        await session.delete(workflow)
        await session.flush()
        return True

    @staticmethod
    async def set_active(session: AsyncSession, workflow_id: str, active: bool) -> Optional[WorkflowModel]:
        workflow = await WorkflowRepository.get_workflow_by_id(session, workflow_id)
        if not workflow:
            return None
        workflow.active = active
        workflow.updated_at = datetime.utcnow()
        await session.flush()
        return workflow

    @staticmethod
    async def get_active_workflows_for_event(
        session: AsyncSession,
        trigger_module: str,
        trigger_event: str,
    ) -> List[WorkflowModel]:
        stmt = (
            select(WorkflowModel)
            .where(
                WorkflowModel.active == True,
                WorkflowModel.trigger_type == "event",
                WorkflowModel.trigger_module == trigger_module,
                WorkflowModel.trigger_event == trigger_event,
            )
            .order_by(WorkflowModel.id.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_all_active_workflows(session: AsyncSession) -> List[WorkflowModel]:
        stmt = (
            select(WorkflowModel)
            .where(WorkflowModel.active == True)
            .order_by(WorkflowModel.id.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_active_workflow_by_webhook_token(
        session: AsyncSession,
        token: str,
    ) -> Optional[WorkflowModel]:
        stmt = (
            select(WorkflowModel)
            .where(
                WorkflowModel.active == True,
                WorkflowModel.trigger_type == "webhook",
                WorkflowModel.webhook_token == token,
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def generate_webhook_token(session: AsyncSession, workflow_id: str) -> Optional[str]:
        workflow = await WorkflowRepository.get_workflow_by_id(session, workflow_id)
        if not workflow:
            return None
        token = f"wh_{secrets.token_urlsafe(16)}"
        workflow.webhook_token = token
        workflow.updated_at = datetime.utcnow()
        await session.flush()
        return token

