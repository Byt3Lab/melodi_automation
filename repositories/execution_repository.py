from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.automation_models import (
    ExecutionModel,
    ExecutionLogModel,
    ExecutionStatus,
    WorkflowModel,
)


class ExecutionRepository:

    @staticmethod
    async def create_execution(
        session: AsyncSession,
        workflow_id: str,
        workflow_version: int,
        trigger_event: str,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionModel:
        execution = ExecutionModel(
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            trigger_event=trigger_event,
            status=ExecutionStatus.RUNNING,
            context_data=context_data or {},
            started_at=datetime.utcnow(),
            duration_ms=0,
        )
        session.add(execution)
        await session.flush()
        return execution

    @staticmethod
    async def update_execution_status(
        session: AsyncSession,
        execution_id: int,
        status: ExecutionStatus,
        context_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        duration_ms: int = 0,
        finished: bool = True,
    ) -> Optional[ExecutionModel]:
        stmt = select(ExecutionModel).where(ExecutionModel.id == execution_id)
        res = await session.execute(stmt)
        execution = res.scalar_one_or_none()
        if not execution:
            return None

        execution.status = status
        if context_data is not None:
            execution.context_data = context_data
        if error_message is not None:
            execution.error_message = error_message
        if finished:
            execution.finished_at = datetime.utcnow()
        if duration_ms > 0:
            execution.duration_ms = duration_ms
        elif execution.finished_at and execution.started_at:
            delta = execution.finished_at - execution.started_at
            execution.duration_ms = int(delta.total_seconds() * 1000)

        await session.flush()
        return execution

    @staticmethod
    async def create_log(
        session: AsyncSession,
        execution_id: int,
        workflow_id: str,
        node_id: str,
        node_type: str,
        node_name: str,
        status: ExecutionStatus,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
    ) -> ExecutionLogModel:
        log = ExecutionLogModel(
            execution_id=execution_id,
            workflow_id=workflow_id,
            node_id=node_id,
            node_type=node_type,
            node_name=node_name,
            status=status,
            input_data=input_data or {},
            output_data=output_data or {},
            error=error,
            started_at=started_at or datetime.utcnow(),
            finished_at=finished_at or datetime.utcnow(),
        )
        session.add(log)
        await session.flush()
        return log

    @staticmethod
    async def get_execution_by_id(
        session: AsyncSession,
        execution_id: int,
        include_logs: bool = True,
    ) -> Optional[ExecutionModel]:
        stmt = select(ExecutionModel).where(ExecutionModel.id == execution_id)
        if include_logs:
            stmt = stmt.options(
                selectinload(ExecutionModel.logs),
                selectinload(ExecutionModel.workflow),
            )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_executions(
        session: AsyncSession,
        workflow_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ExecutionModel]:
        stmt = (
            select(ExecutionModel)
            .options(selectinload(ExecutionModel.workflow))
            .order_by(desc(ExecutionModel.started_at), desc(ExecutionModel.id))
        )
        conditions = []
        if workflow_id:
            conditions.append(ExecutionModel.workflow_id == workflow_id)
        if status:
            conditions.append(ExecutionModel.status == status)
        if search and search.strip():
            clean_search = search.strip()
            search_term = f"%{clean_search}%"
            search_conds = [
                ExecutionModel.trigger_event.ilike(search_term),
                ExecutionModel.workflow_id.ilike(search_term),
                ExecutionModel.workflow.has(WorkflowModel.name.ilike(search_term)),
            ]
            if clean_search.isdigit():
                search_conds.append(ExecutionModel.id == int(clean_search))
            conditions.append(or_(*search_conds))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.limit(limit).offset(offset)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def count_executions(
        session: AsyncSession,
        workflow_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        search: Optional[str] = None,
    ) -> int:
        stmt = select(func.count(ExecutionModel.id))
        conditions = []
        if workflow_id:
            conditions.append(ExecutionModel.workflow_id == workflow_id)
        if status:
            conditions.append(ExecutionModel.status == status)
        if search and search.strip():
            clean_search = search.strip()
            search_term = f"%{clean_search}%"
            search_conds = [
                ExecutionModel.trigger_event.ilike(search_term),
                ExecutionModel.workflow_id.ilike(search_term),
                ExecutionModel.workflow.has(WorkflowModel.name.ilike(search_term)),
            ]
            if clean_search.isdigit():
                search_conds.append(ExecutionModel.id == int(clean_search))
            conditions.append(or_(*search_conds))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        res = await session.execute(stmt)
        return res.scalar() or 0
