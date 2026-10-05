import abc
import asyncio
from typing import Any, Dict


class AutomationExecutor(abc.ABC):
    """
    Interface pour l'exécution d'un workflow.
    Permet d'alterner entre exécution asynchrone in-process et worker distribué (Celery).
    """

    @abc.abstractmethod
    async def run(self, execution_engine: Any, workflow: Any, context: Dict[str, Any], app: Any) -> Any:
        pass


class AsyncInternalExecutor(AutomationExecutor):
    """
    Exécuteur asynchrone interne par défaut.
    Lance la tâche de manière non-bloquante via asyncio.create_task.
    """

    def __init__(self):
        self._running_tasks = set()

    async def run(self, execution_engine: Any, workflow: Any, context: Dict[str, Any], app: Any) -> Any:
        # Exécution non-bloquante en tâche de fond pour isoler le flux appelant
        coro = execution_engine.execute(workflow, context, app)
        task = asyncio.create_task(coro)
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)
        return task
