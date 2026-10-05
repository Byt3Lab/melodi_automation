from typing import Any
from core.module import ApplicationModule, Permission
from .models.automation_models import WorkflowModel, WorkflowVersionModel, ExecutionModel, ExecutionLogModel
from .services.automation_service import AutomationService
from .controllers.api import AutomationAPIController
from .controllers.web import AutomationWebController


class MelodiAutomationModule(ApplicationModule):
    def __init__(self):
        super().__init__(name="MELODI Automation Engine", router_name="melodi_automation")
        self.automation_service = None

    def _get_permissions(self):
        return [
            Permission(self, "automation:read", "Consulter les workflows d'automatisation"),
            Permission(self, "automation:create", "Créer des workflows d'automatisation"),
            Permission(self, "automation:update", "Modifier les workflows existants"),
            Permission(self, "automation:delete", "Supprimer des workflows"),
            Permission(self, "automation:execute", "Tester et exécuter manuellement des workflows"),
            Permission(self, "automation:executions_read", "Consulter les journaux et traces d'exécution"),
        ]

    async def run_dev_migrations(self):
        """Création automatique des tables de l'Automation Engine et mise à jour progressive du schéma."""
        await self.app.db.create_all([
            WorkflowModel,
            WorkflowVersionModel,
            ExecutionModel,
            ExecutionLogModel,
        ])
        # Mise à jour progressive du schéma (migration id INTEGER -> VARCHAR(36), trigger_type, webhook_token)
        from sqlalchemy import text
        from .config import AutomationTables

        async with self.app.db.get_session() as session:
            try:
                # 1. Vérifier si id de workflows est encore INTEGER
                res = await session.execute(text(
                    f"SELECT data_type FROM information_schema.columns "
                    f"WHERE table_name = '{AutomationTables.WORKFLOWS}' AND column_name = 'id';"
                ))
                col_type = res.scalar()
                if col_type and ("int" in str(col_type).lower()):
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
                        f"ALTER TABLE {AutomationTables.EXECUTIONS} ADD CONSTRAINT {AutomationTables.EXECUTIONS}_workflow_id_fkey "
                        f"FOREIGN KEY (workflow_id) REFERENCES {AutomationTables.WORKFLOWS}(id) ON DELETE CASCADE;"
                    ))
                    await session.commit()

                # 2. Colonnes trigger_type et webhook_token
                await session.execute(text(
                    f"ALTER TABLE {AutomationTables.WORKFLOWS} ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(50) DEFAULT 'event';"
                ))
                await session.execute(text(
                    f"ALTER TABLE {AutomationTables.WORKFLOWS} ADD COLUMN IF NOT EXISTS webhook_token VARCHAR(100);"
                ))
                await session.commit()
            except Exception as e:
                await session.rollback()
                print(f"[MELODI Automation] Avertissement migration schéma: {e}")

    async def load(self):
        self.permissions = self._get_permissions()

        # 1. Migrations des modèles et colonnes de l'Automation Engine
        try:
            await self.run_dev_migrations()
        except Exception as e:
            print(f"[MELODI Automation] Erreur lors du chargement des tables: {e}")

        # 2. Initialisation du service d'automatisation
        self.automation_service = AutomationService(self.app)

        # 3. Enregistrement des routes Web Admin
        self.admin_router.add_route("", AutomationWebController.admin_workflows, methods=["GET", "POST"])
        self.admin_router.add_route("/", AutomationWebController.admin_workflows, methods=["GET", "POST"])
        self.admin_router.add_route("/builder", AutomationWebController.admin_workflow_builder, methods=["GET", "POST"])
        self.admin_router.add_route("/executions", AutomationWebController.admin_executions, methods=["GET"])
        self.admin_router.add_route("/doc", AutomationWebController.admin_doc, methods=["GET"])

        # 4. Enregistrement des routes API d'Administration
        for router in (self.api_admin_router, self.api_router):
            # Routes REST & Routes Plates avec Paramètres Query (?id=...)
            router.add_route("/workflows", AutomationAPIController.list_workflows, methods=["GET"])
            router.add_route("/workflows", AutomationAPIController.create_workflow, methods=["POST"])
            router.add_route("/workflows/import", AutomationAPIController.import_workflow, methods=["POST"])
            router.add_route("/workflows/export", AutomationAPIController.export_workflow, methods=["GET", "POST"])
            router.add_route("/workflows/download", AutomationAPIController.download_workflow_file, methods=["GET"])
            router.add_route("/workflows/activate", AutomationAPIController.activate_workflow, methods=["POST"])
            router.add_route("/workflows/deactivate", AutomationAPIController.deactivate_workflow, methods=["POST"])
            router.add_route("/workflows/test", AutomationAPIController.test_workflow, methods=["POST"])
            router.add_route("/workflows/simulate", AutomationAPIController.simulate_workflow, methods=["POST"])
            router.add_route("/workflows/delete", AutomationAPIController.delete_workflow, methods=["POST", "DELETE"])
            router.add_route("/workflows/regenerate-webhook", AutomationAPIController.regenerate_webhook_token, methods=["POST"])
            router.add_route("/workflows/executions", AutomationAPIController.list_workflow_executions, methods=["GET"])
            router.add_route("/workflows/single", AutomationAPIController.get_workflow, methods=["GET"])
            router.add_route("/workflows/versions", AutomationAPIController.get_workflow_versions, methods=["GET"])
            router.add_route("/workflows/versions/restore", AutomationAPIController.restore_workflow_version, methods=["POST"])

            # Variantes avec <id> en fallback pour la rétrocompatibilité REST
            router.add_route("/workflows/<id>", AutomationAPIController.get_workflow, methods=["GET"])
            router.add_route("/workflows/<id>", AutomationAPIController.update_workflow, methods=["PUT", "POST"])
            router.add_route("/workflows/<id>", AutomationAPIController.delete_workflow, methods=["DELETE", "POST"])
            router.add_route("/workflows/<id>/export", AutomationAPIController.export_workflow, methods=["GET"])
            router.add_route("/workflows/<id>/download", AutomationAPIController.download_workflow_file, methods=["GET"])
            router.add_route("/workflows/<id>/activate", AutomationAPIController.activate_workflow, methods=["POST"])
            router.add_route("/workflows/<id>/deactivate", AutomationAPIController.deactivate_workflow, methods=["POST"])
            router.add_route("/workflows/<id>/test", AutomationAPIController.test_workflow, methods=["POST"])
            router.add_route("/workflows/<id>/regenerate-webhook", AutomationAPIController.regenerate_webhook_token, methods=["POST"])
            router.add_route("/workflows/<id>/executions", AutomationAPIController.list_workflow_executions, methods=["GET"])
            router.add_route("/executions/<id>", AutomationAPIController.get_execution, methods=["GET"])

            router.add_route("/meta/actions", AutomationAPIController.get_meta_actions, methods=["GET"])
            router.add_route("/meta/events", AutomationAPIController.get_meta_events, methods=["GET"])
            router.add_route("/meta/nodes", AutomationAPIController.get_meta_nodes, methods=["GET"])
            router.add_route("/nodes/test-step", AutomationAPIController.test_node_step, methods=["POST"])

        # Route Webhook publique pour déclenchements tiers
        self.api_router.add_route("/webhook/<token>", AutomationAPIController.handle_webhook, methods=["GET", "POST", "PUT", "DELETE"])

        # 5. Enregistrement des actions inter-modules de l'Automation Engine
        self._register_actions()

        # 6. Enregistrement de la navigation dans la barre d'administration MELODI
        self.register_navigation(
            id="automation_root",
            label="Automatisations",
            icon="name=alt_route&fill=white",
            url="/admin/melodi_automation",
            priority=55,
            children=[
                {"label": "Tous les Workflows", "icon": "name=account_tree&fill=white", "url": "/admin/melodi_automation"},
                {"label": "Nouveau Workflow", "icon": "name=add_circle&fill=white", "url": "/admin/melodi_automation/builder"},
                {"label": "Journal d'exécutions", "icon": "name=receipt_long&fill=white", "url": "/admin/melodi_automation/executions"},
                {"label": "Documentation", "icon": "name=description&fill=white", "url": "/admin/melodi_automation/doc"},
            ]
        )

        # 7. Abonnement dynamique de tous les workflows actifs en base
        try:
            await self.automation_service.register_all_active_triggers()
        except Exception as e:
            print(f"[melodi_automation] Avertissement lors de l'enregistrement des triggers actifs : {e}")

    def _register_actions(self):
        self.add_action("test_workflow", self.action_test_workflow)
        self.add_action("list_active_workflows", self.action_list_active_workflows)
        self.add_action("register_node", self.action_register_node)
        self.add_action("register_nodes", self.action_register_nodes)

    async def action_test_workflow(self, payload: dict) -> dict:
        workflow_id = int(payload.get("workflow_id") or 0)
        simulated_payload = payload.get("payload") or {}
        return await self.automation_service.test_workflow(workflow_id, simulated_payload)

    async def action_list_active_workflows(self, payload: dict) -> dict:
        async with self.app.db.get_session() as session:
            from .repositories.workflow_repository import WorkflowRepository
            workflows = await WorkflowRepository.get_all_active_workflows(session)
            return {"status": "success", "count": len(workflows), "data": [w.to_dict() for w in workflows]}

    async def action_register_node(self, payload: Any) -> dict:
        """
        Action de hook permettant à un module tiers d'enregistrer activement un nœud personnalisé.
        Usage : await app.hook_manager.action.execute('melodi_automation', 'register_node', node_or_dict)
        """
        from .nodes.registry import NodeRegistry
        from .nodes.base_node import BaseNode
        if isinstance(payload, BaseNode):
            NodeRegistry.register(payload)
            return {
                "status": "success",
                "node_id": payload.id,
                "name": payload.name,
                "message": f"Nœud '{payload.id}' enregistré avec succès dans l'Automation Engine.",
            }
        mod_name = payload.get("module") or "custom" if isinstance(payload, dict) else "custom"
        node = NodeRegistry.register_custom_node(payload, mod_name)
        return {
            "status": "success",
            "node_id": node.id,
            "name": node.name,
            "message": f"Nœud '{node.id}' enregistré avec succès dans l'Automation Engine.",
        }

    async def action_register_nodes(self, payload: Any) -> dict:
        """
        Action de hook permettant d'enregistrer plusieurs nœuds par lot.
        """
        from .nodes.registry import NodeRegistry
        from .nodes.base_node import BaseNode
        items = payload if isinstance(payload, list) else (payload.get("nodes") if isinstance(payload, dict) else [])
        registered = []
        for item in items:
            if isinstance(item, BaseNode):
                NodeRegistry.register(item)
                registered.append(item.id)
            elif isinstance(item, dict):
                mod_name = item.get("module") or "custom"
                node = NodeRegistry.register_custom_node(item, mod_name)
                registered.append(node.id)
        return {
            "status": "success",
            "count": len(registered),
            "registered_nodes": registered,
        }


module = MelodiAutomationModule()

