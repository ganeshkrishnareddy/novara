"""Role-based permissions. Roles describe what a member may do inside one
workspace. There is no global administrator: authority is always scoped."""

from __future__ import annotations

ALL = "*"

WORKSPACE_MANAGE = "workspace:manage"
MEMBER_MANAGE = "member:manage"
MEMBER_INVITE = "member:invite"
CONTACT_READ = "contact:read"
CONTACT_WRITE = "contact:write"
CONTACT_ARCHIVE = "contact:archive"
CONTACT_DELETE = "contact:delete"
COMPANY_READ = "company:read"
COMPANY_WRITE = "company:write"
LEAD_READ = "lead:read"
LEAD_WRITE = "lead:write"
TASK_READ = "task:read"
TASK_WRITE = "task:write"
NOTE_WRITE = "note:write"
EVENT_READ = "event:read"
NOTIFICATION_READ = "notification:read"
OUTREACH_READ = "outreach:read"
OUTREACH_APPROVE = "outreach:approve"
# Document metadata and sharing have their own verbs (PM-095). Borrowing
# contact/note verbs made it impossible to grant document access without also
# granting unrelated CRM powers.
DOCUMENT_READ = "document:read"
DOCUMENT_WRITE = "document:write"
DOCUMENT_ADMIN = "document:admin"
# Governance / NV-070 fine-grained permissions (allow-listable in custom roles)
NOTIFICATION_WORKFLOW_READ = "notification_workflow:read"
NOTIFICATION_WORKFLOW_WRITE = "notification_workflow:write"
INTEGRATION_READ = "integration:read"
INTEGRATION_WRITE = "integration:write"
WEBHOOK_READ = "webhook:read"
WEBHOOK_WRITE = "webhook:write"
BILLING_READ = "billing:read"
BILLING_WRITE = "billing:write"
AUDIT_READ = "audit:read"

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({ALL}),
    "admin": frozenset(
        {
            WORKSPACE_MANAGE,
            MEMBER_MANAGE,
            MEMBER_INVITE,
            NOTIFICATION_WORKFLOW_READ,
            NOTIFICATION_WORKFLOW_WRITE,
            INTEGRATION_READ,
            INTEGRATION_WRITE,
            WEBHOOK_READ,
            WEBHOOK_WRITE,
            BILLING_READ,
            BILLING_WRITE,
            AUDIT_READ,
            CONTACT_READ,
            CONTACT_WRITE,
            CONTACT_ARCHIVE,
            CONTACT_DELETE,
            COMPANY_READ,
            COMPANY_WRITE,
            LEAD_READ,
            LEAD_WRITE,
            TASK_READ,
            TASK_WRITE,
            NOTE_WRITE,
            EVENT_READ,
            NOTIFICATION_READ,
            OUTREACH_READ,
            OUTREACH_APPROVE,
            DOCUMENT_READ,
            DOCUMENT_WRITE,
            DOCUMENT_ADMIN,
        }
    ),
    "sales_manager": frozenset(
        {
            CONTACT_READ,
            CONTACT_WRITE,
            CONTACT_ARCHIVE,
            COMPANY_READ,
            COMPANY_WRITE,
            LEAD_READ,
            LEAD_WRITE,
            TASK_READ,
            TASK_WRITE,
            NOTE_WRITE,
            EVENT_READ,
            NOTIFICATION_READ,
            OUTREACH_READ,
            OUTREACH_APPROVE,
            DOCUMENT_READ,
            DOCUMENT_WRITE,
            DOCUMENT_ADMIN,
        }
    ),
    "sales_rep": frozenset(
        {
            CONTACT_READ,
            CONTACT_WRITE,
            COMPANY_READ,
            LEAD_READ,
            LEAD_WRITE,
            TASK_READ,
            TASK_WRITE,
            NOTE_WRITE,
            NOTIFICATION_READ,
            OUTREACH_READ,
            DOCUMENT_READ,
            DOCUMENT_WRITE,
        }
    ),
    "marketing": frozenset(
        {
            CONTACT_READ,
            CONTACT_WRITE,
            COMPANY_READ,
            LEAD_READ,
            LEAD_WRITE,
            TASK_READ,
            TASK_WRITE,
            NOTE_WRITE,
            NOTIFICATION_READ,
            OUTREACH_READ,
            DOCUMENT_READ,
            DOCUMENT_WRITE,
            DOCUMENT_ADMIN,
        }
    ),
    "support": frozenset(
        {
            CONTACT_READ,
            CONTACT_WRITE,
            COMPANY_READ,
            TASK_READ,
            TASK_WRITE,
            NOTE_WRITE,
            NOTIFICATION_READ,
            DOCUMENT_READ,
        }
    ),
    "read_only": frozenset(
        {
            CONTACT_READ,
            COMPANY_READ,
            LEAD_READ,
            TASK_READ,
            EVENT_READ,
            NOTIFICATION_READ,
            OUTREACH_READ,
            DOCUMENT_READ,
        }
    ),
}


def has_permission(role: str, permission: str) -> bool:
    granted = ROLE_PERMISSIONS.get(role, frozenset())
    return ALL in granted or permission in granted
