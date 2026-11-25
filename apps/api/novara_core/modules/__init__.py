"""Capability modules. Each module owns its tables and its APIRouter.

The orchestrator wires every router into the core app here; module files never
edit main.py. All modules consume the same identity, workspace, permission and
event contracts from novara_core.
"""

from __future__ import annotations

from fastapi import FastAPI


MODULE_NAMES = (
    "sales",
    "crm_intelligence",
    "marketing",
    "email_campaigns",
    "support",
    "visitor_conversations",
    "feedback",
    "feedback_extensions",
    "feedback_targeting",
    "feedback_intelligence",
    "experiment_stats",
    "experiment_operations",
    "experiment_queries",
    "experiment_platform",
    "experiment_delivery",
    "survey_delivery",
    "search_advanced",
    "analytics",
    "feature_flags",
    "search",
    "search_engine",
    "projects",
    "project_intake",
    "project_extensions",
    "documents",
    "document_links",
    "document_security",
    "document_engagement",
    "storage",
    "automation",
    "notification_preferences",
    "notification_workflows",
    "notification_automation",
    "agents",
    "integrations",
    "jobs",
    "adapters",
    "operations",
    "workspace_admin",
    "api_resources",
    "api_v2",
    "document_store",
    "api_keys",
    "marketing_skills",
    "sales_engagement",
    "conversation_ops",
    "experiment_exposure",
    "wiki_pages",
    "email_engagement",
    "work_item_planning",
    "support_reporting",
    "marketing_content",
    "plane_collaboration_api",
    "experiment_advanced_stats",
    "feature_flag_governance",
    "access_governance",
)


def import_all() -> tuple:
    """Import every module so its tables and event names are registered.

    Also used by Alembic's env.py so migrations see the complete schema.
    """
    import importlib

    return tuple(importlib.import_module(f"{__name__}.{name}") for name in MODULE_NAMES)


def include_all(app: FastAPI) -> None:
    """Attach every module's workspace-scoped router to the one application.

    A module may also expose a token-scoped public router (for example a
    one-time CSAT response route) with no bearer dependency. It is registered
    explicitly here so every route remains visible in the generated contract.
    """
    for module in import_all():
        app.include_router(module.router)
        public_router = getattr(module, "public_router", None)
        if public_router is not None:
            app.include_router(public_router)

from . import experiment_advanced_stats  # noqa: F401  T-106

