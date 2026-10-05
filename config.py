from core import get_prefix_table
from core.db.base_module_tables import BaseModuleTables

MODULE_NAME = "melodi_automation"
PREFIX_TABLE = get_prefix_table(MODULE_NAME)


class AutomationTables(BaseModuleTables):
    WORKFLOWS = f"{PREFIX_TABLE}workflows"
    WORKFLOW_VERSIONS = f"{PREFIX_TABLE}workflow_versions"
    EXECUTIONS = f"{PREFIX_TABLE}executions"
    EXECUTION_LOGS = f"{PREFIX_TABLE}execution_logs"
