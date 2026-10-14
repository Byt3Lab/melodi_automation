import enum
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import JSON, UniqueConstraint
from core.orm.model import (
    BaseModel,
    Mapped,
    mapped_column,
    relationship,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    Enum,
    ForeignKey,
)

from ..config import AutomationTables


class WorkflowStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowModel(BaseModel):
    __tablename__ = AutomationTables.WORKFLOWS

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trigger_module: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default="event", nullable=False)
    webhook_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Graph definitions (Nodes and Connections) and Custom Types
    nodes: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    connections: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    custom_types: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __init__(self, **kwargs):
        if "id" not in kwargs or not kwargs["id"]:
            kwargs["id"] = str(uuid.uuid4())
        super().__init__(**kwargs)


    executions: Mapped[List["ExecutionModel"]] = relationship(
        "ExecutionModel",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "active": self.active,
            "version": self.version,
            "trigger_module": self.trigger_module,
            "trigger_event": self.trigger_event,
            "trigger": f"{self.trigger_module}.{self.trigger_event}",
            "trigger_type": getattr(self, "trigger_type", "event") or "event",
            "webhook_token": getattr(self, "webhook_token", None),
            "webhook_url": f"/api/melodi_automation/webhook/{self.webhook_token}" if getattr(self, "webhook_token", None) else None,
            "nodes": self.nodes or [],
            "connections": self.connections or [],
            "custom_types": getattr(self, "custom_types", []) or [],
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkflowVersionModel(BaseModel):
    __tablename__ = AutomationTables.WORKFLOW_VERSIONS
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_automation_workflow_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(f"{AutomationTables.WORKFLOWS}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[str] = mapped_column(String(255), nullable=False, default="Workflow modifié")
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self, include_snapshot: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "version": self.version,
            "change_summary": self.change_summary,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_snapshot:
            data["snapshot"] = self.snapshot or {}
        return data


class ExecutionModel(BaseModel):
    __tablename__ = AutomationTables.EXECUTIONS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(f"{AutomationTables.WORKFLOWS}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, native_enum=False),
        default=ExecutionStatus.PENDING,
        nullable=False,
        index=True,
    )
    context_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    workflow: Mapped[Optional[WorkflowModel]] = relationship(
        "WorkflowModel",
        back_populates="executions",
        lazy="selectin",
    )
    logs: Mapped[List["ExecutionLogModel"]] = relationship(
        "ExecutionLogModel",
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self, include_logs: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow.name if self.workflow else None,
            "workflow_version": self.workflow_version,
            "trigger_event": self.trigger_event,
            "status": self.status.value if isinstance(self.status, ExecutionStatus) else str(self.status),
            "context_data": self.context_data or {},
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
        }
        if include_logs and self.logs:
            data["logs"] = [log.to_dict() for log in self.logs]
        return data


class ExecutionLogModel(BaseModel):
    __tablename__ = AutomationTables.EXECUTION_LOGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{AutomationTables.EXECUTIONS}.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    node_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, native_enum=False),
        default=ExecutionStatus.PENDING,
        nullable=False,
    )
    input_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    execution: Mapped[Optional[ExecutionModel]] = relationship(
        "ExecutionModel",
        back_populates="logs",
        lazy="selectin",
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "node_type": self.node_type,
            "node_name": self.node_name,
            "status": self.status.value if isinstance(self.status, ExecutionStatus) else str(self.status),
            "input_data": self.input_data or {},
            "output_data": self.output_data or {},
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
