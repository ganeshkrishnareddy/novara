"""Static wiring guards for the work-item and document UIs.

A visible control without a dispatcher is a dead button. These checks read the
actual SPA source so a future refactor cannot silently orphan the controls
added for PL-004/006/008/017/038 and PM-001/073/095.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[3] / "apps" / "web" / "app.js"


def _source() -> str:
    assert APP_JS.is_file(), f"SPA source missing: {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def _handlers(source: str, pattern: str) -> set[str]:
    return set(re.findall(pattern, source))


def test_project_detail_view_is_routed_and_rendered():
    source = _source()
    assert "async function loadProjectDetail(projectId, token)" in source
    assert "if (parts[0] === 'projects' && parts[1]) return loadProjectDetail" in source
    for marker in (
        "data-action=\"view-project\"",
        "data-action=\"create-project\"",
        "data-action=\"create-work-item\"",
        "data-action=\"toggle-project-state\"",
        "data-change=\"item-status\"",
        "data-change=\"item-assignee\"",
        "data-change=\"item-filter\"",
        "State set",
        "Overdue",
        "fmtDate(item.due_at)",
    ):
        assert marker in source, f"missing UI marker: {marker}"


def test_every_new_project_control_has_a_dispatch_handler():
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    changes = _handlers(source, r"kind === '([a-z0-9-]+)'")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in (
        "view-project", "create-project", "create-work-item", "toggle-project-state",
    ):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("item-filter", "item-status", "item-assignee"):
        assert name in changes, f"unhandled data-change: {name}"
    for name in ("create-project", "create-work-item", "project-state-create"):
        assert name in forms, f"unhandled data-form: {name}"


def test_project_search_types_are_selectable_and_navigable():
    source = _source()
    assert "['project', 'Projects'], ['project_item', 'Work items']" in source
    assert "project: 'layers', project_item: 'checkSquare'" in source
    assert "kind === 'project' || kind === 'project_item'" in source
    assert "data-change=\"search-type\"" in source


def test_new_project_handlers_are_declared_exactly_once():
    source = _source()
    cases = re.findall(r"case '([a-z0-9-]+)':", source)
    forms = re.findall(r"name === '([a-z0-9-]+)'", source)
    for name in (
        "view-project", "create-project", "create-work-item", "toggle-project-state",
    ):
        assert cases.count(name) == 1, f"action {name} declared {cases.count(name)} times"
    for name in ("create-project", "create-work-item", "project-state-create"):
        assert forms.count(name) == 1, f"form {name} declared {forms.count(name)} times"


def test_document_views_are_routed_and_permission_gated():
    source = _source()
    assert "async function loadDocuments(token)" in source
    assert "async function loadDocumentDetail(documentId, token)" in source
    assert "if (parts[0] === 'documents' && parts[1]) return loadDocumentDetail" in source
    assert "case 'documents': return loadDocuments(token)" in source
    assert "documentRead: 'document:read'" in source
    assert "documentWrite: 'document:write'" in source
    assert "documentAdmin: 'document:admin'" in source
    assert "{ route: 'documents', label: 'Documents', icon: 'archive', perm: P.documentRead }" in source
    assert source.count("can(P.documentRead)") >= 2
    assert "can(P.documentWrite)" in source
    assert "can(P.documentAdmin)" in source


def test_every_document_control_has_a_dispatch_handler():
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in (
        "view-document", "create-room", "create-document", "create-watermark-preview",
        "create-document-link", "revoke-document-link", "copy-document-token",
    ):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
    for name in ("create-room", "create-document", "create-watermark-preview", "create-document-link"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"
    for marker in (
        "data-action=\"view-document\"",
        "data-action=\"create-watermark-preview\"",
        "data-action=\"create-document-link\"",
        "data-action=\"revoke-document-link\"",
        "View only", "No download", "Page engagement",
        "No external message is sent", "Per-view watermark preview",
    ):
        assert marker in source, f"missing UI marker: {marker}"


def test_customer_profile_ui_shows_linked_support_conversations():
    source = _source()
    assert "async function loadContactDetail(id, token)" in source
    assert "api(apiW('/tickets') + '?contact_id=' + encodeURIComponent(id))" in source
    assert "Support conversations" in source
    assert "href=\"#/inbox/" in source
    assert "No conversations yet" in source
    assert "without a duplicate identity" in source


def test_membership_lifecycle_controls_are_wired_and_guarded():
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    for name in ("suspend-member", "reactivate-member"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
        assert source.count(f"'{name}'") >= 2, f"missing control: {name}"
    assert "data-change=\"member-role\"" in source
    assert "kind === 'member-role'" in source
    assert "m.user_id === me.user.id" in source
    assert "m.role === 'owner'" in source
    assert "last active owner cannot be suspended" in source


def test_survey_lifecycle_control_is_wired():
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    assert "survey-status" in actions
    assert source.count("case 'survey-status':") == 1
    for marker in (
        'data-action="survey-status"', 'data-status="active"', 'data-status="closed"',
        "Publish", "Reopen", "survey is closed", "Reopen it to record further responses",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    assert "method: 'PATCH', body: { status: el.dataset.status }" in source


def test_consent_controls_are_wired_without_render_tokens():
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    for name in ("consent-unsubscribe", "consent-resubscribe", "consent-dnc", "consent-preferences"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
        assert f'data-action="{name}"' in source, f"missing control: {name}"
    assert "async function consentTokens(contactId)" in source
    assert "apiW('/email/consent-links') + '?contact_id='" in source
    assert "name === 'consent-preferences'" in source
    assert "data-form=\"consent-preferences\"" in source
    assert "Global do-not-contact" in source
    assert "External identity" in source
    assert "Tokens are generated when a control is used and are never shown on screen." in source
    card = source[source.index("Consent & preferences"):source.index("Notes</div>", source.index("Consent & preferences"))]
    assert ".token" not in card and "href=" not in card


def test_project_membership_controls_are_wired_and_guarded():
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    for name in ("toggle-project-default-assignee", "toggle-project-subscribed", "remove-project-member"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
        assert f'data-action="{name}"' in source, f"missing control: {name}"
    assert "kind === 'project-member-role'" in source
    assert 'data-change="project-member-role"' in source
    assert "name === 'project-member-add'" in source
    assert 'data-form="project-member-add"' in source
    assert "api(base + '/members')" in source
    assert "checkboxField('restricted'" in source
    assert "restricted: fd.get('restricted') !== null" in source
    assert "Only listed project members can see or change this project." in source
    assert "Roles and the default assignee are managed on this project" in source
    assert "m.user_id === project.owner_id" in source
    assert "results[5].status === 'fulfilled'" in source


def test_campaign_journey_controls_are_wired_and_local_only():
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("campaign-run-journey", "campaign-record-engagement", "campaign-exit-enrollment"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
        assert f'data-action="{name}"' in source, f"missing control: {name}"
    for name in ("campaign-journey-step-add", "campaign-schedule", "campaign-enroll-contact"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"
        assert f'data-form="{name}"' in source, f"missing control: {name}"
    # The journey never presents delivery as real and never embeds a send action.
    assert "Steps record local analytics events only" in source
    assert "Nothing here represents a delivered message" in source
    assert "Nothing was sent" in source
    assert "toUtc" in source and "parsed.toISOString()" in source
    assert "api(apiW('/campaigns/analytics/lifecycle'))" in source
    assert "data-change=\"campaign-status\"" in source
    assert "kind === 'campaign-status'" in source


def test_workspace_admin_surface_is_routed_and_wired():
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    assert "toggle-flag" in actions
    assert source.count("case 'toggle-flag':") == 1
    assert 'data-action="toggle-flag"' in source
    for name in ("workspace-settings", "workspace-flag-create"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1
        assert f'data-form="{name}"' in source
    for marker in (
        "Workspace administration", "api(apiW('/admin/settings'))",
        "api(apiW('/admin/summary'))", "api(apiW('/flags'))",
        "method: 'PATCH', body: { enabled: enabled }",
        "Feature flags", "Non-sensitive settings",
    ):
        assert marker in source, f"missing UI marker: {marker}"


def test_experiment_management_ui_is_routed_and_wired():
    """GB-110..GB-116: every experiment control has one real dispatcher."""
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in (
        "experiment-create", "experiment-edit", "experiment-status",
        "experiment-results", "experiment-delete",
    ):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
        assert f'data-action="{name}"' in source, f"missing control: {name}"
    for name in ("experiment-create", "experiment-edit", "experiment-status", "experiment-result"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"
        assert f'data-form="{name}"' in source, f"missing form: {name}"
    for marker in (
        "async function loadInsights(token)", "api(apiW('/analytics'))",
        "encodeURIComponent(text('id')) + '/status'",
        "encodeURIComponent(text('id')) + '/results'",
        "method: isEdit ? 'PATCH' : 'POST'", "EXPERIMENT_STATUSES",
        "Experiments", "A hypothesis, a metric and measured results",
        "Every transition is recorded with its previous value.",
    ):
        assert marker in source, f"missing UI marker: {marker}"

def test_feature_flag_p1_controls_are_wired_and_guarded():
    """GB-001..GB-058: flag management surfaces have one real dispatcher each."""
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("flag-rules", "flag-exposures", "flag-sdk-payload"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
        assert f'data-action="{name}"' in source, f"missing control: {name}"
    for name in ("sdk-connection-create", "flag-rule-create"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"
        assert f'data-form="{name}"' in source, f"missing form: {name}"
    for marker in (
        "flagEnvironment", "data-change=\"flag-environment\"",
        "async function openFlagRules", "async function openFlagExposures",
        "async function openSdkPayload", "api(apiW('/flags/sdk/payload?environment='",
        "api(apiW('/flags/sdk/connections')", "'/rules'", "'/exposures'",
        "default_value: text('default_value')",
    ):
        assert marker in source, f"missing UI marker: {marker}"

def test_project_p1_work_management_controls_are_wired():
    """PL-005..PL-094: work-management controls have one dispatcher each."""
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("work-item-board", "work-item-labels", "work-item-modules", "work-item-activity"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
        assert f'data-action="{name}"' in source, f"missing control: {name}"
    assert "project-label-create" in forms
    for marker in (
        "itemPriority", "data-change=\"item-priority\"", "data-change=\"saved-view\"",
        "async function openWorkItemBoard", "async function openWorkItemLabels",
        "async function openWorkItemModules", "async function openWorkItemActivity",
        "async function applySavedView", "'/board'", "'/views'", "'/modules'", "'/labels'",
        "'/activity'",
    ):
        assert marker in source, f"missing UI marker: {marker}"

def test_support_p1_operations_ui_is_routed_and_wired():
    """CW-005..CW-166: support operations have one real dispatcher each."""
    source = _source()
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    for name in (
        "support-teams", "support-inboxes", "support-labels", "support-routing",
        "support-segments", "support-replies", "support-help", "support-reports",
    ):
        assert name in actions, f"unhandled support action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
        assert f"supportOpButton('{name}'" in source, f"missing control: {name}"
    for marker in (
        "ticketTeam", "ticketInbox", "ticketLabel", "data-change=\"ticket-inbox\"",
        "data-change=\"ticket-label\"", "async function openSupportCollection",
        "async function openSupportReplies", "async function openSupportHelp",
        "async function openSupportReports", "'/tickets/teams'", "'/tickets/inboxes'",
        "'/tickets/labels'", "'/tickets/routing-rules'", "'/tickets/segments'",
        "'/tickets/saved-replies'", "'/tickets/macros'", "'/tickets/help-portals'",
        "'/tickets/reports/overview'",
    ):
        assert marker in source, f"missing UI marker: {marker}"

def test_survey_extension_controls_are_rendered_and_dispatched():
    """FB-008..FB-044: survey configuration controls must not become dead UI."""
    source = _source()
    assert "async function loadSurveyDetail(surveyId, token)" in source
    assert "/feedback/surveys/' + encodeURIComponent(surveyId) + '/config" in source
    for marker in (
        'data-form="save-survey-config"',
        'data-form="add-survey-question"',
        'data-form="set-survey-embedded"',
        'data-action="survey-from-template"',
        'data-form="create-survey-from-template"',
        'display_option', 'visibility', 'theme', 'languages',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    assert "survey-from-template" in actions
    for name in ("save-survey-config", "add-survey-question",
                 "set-survey-embedded", "create-survey-from-template"):
        assert name in forms, f"unhandled data-form: {name}"

def test_feedback_extension_p2b_controls_are_rendered_and_dispatched():
    """FB-066..FB-095: link, tag and response-management controls must be live."""
    source = _source()
    for marker in (
        'data-form="create-survey-link"',
        'data-form="create-survey-tag"',
        'data-action="answer-finish"',
        'data-action="answer-delete"',
        'data-action="answers-export"',
        "/answers/export", "/links", "/tags",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("answer-finish", "answer-delete", "answers-export"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("create-survey-link", "create-survey-tag"):
        assert name in forms, f"unhandled data-form: {name}"

def test_feedback_targeting_controls_are_rendered_and_dispatched():
    """FB-055..FB-084: targeting and control controls must not become dead UI."""
    source = _source()
    for marker in (
        'data-form="create-action-class"',
        'data-form="create-trigger"',
        'data-form="save-survey-controls"',
        'data-form="evaluate-trigger"',
        'data-action="trigger-evaluate"',
        'collect_google_reviews', 'product_market_fit',
        "/feedback/targeting/triggers", "/feedback/targeting/action-classes",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    assert "trigger-evaluate" in actions
    for name in ("create-action-class", "create-trigger", "save-survey-controls",
                 "evaluate-trigger"):
        assert name in forms, f"unhandled data-form: {name}"

def test_search_engine_route_controls_are_rendered_and_dispatched():
    """MS-041/044/047: local search index controls must not become dead UI."""
    source = _source()
    assert "async function loadSearchIndexes(token)" in source
    assert "case 'search-indexes': return loadSearchIndexes(token)" in source
    for marker in (
        'data-action="create-search-index"',
        'data-action="search-index-delete"',
        'data-form="create-search-index"',
        'data-form="search-index-query"',
        "/search-engine/indexes", "api(base + '/version')",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("create-search-index", "search-index-delete"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("create-search-index", "search-index-query"):
        assert name in forms, f"unhandled data-form: {name}"


def test_notification_workflow_route_controls_are_rendered_and_dispatched():
    """NV-017/028/054/086/087: workflow controls must not become dead UI."""
    source = _source()
    assert "async function loadNotificationWorkflows(token)" in source
    assert "case 'notification-workflows': return loadNotificationWorkflows(token)" in source
    assert "{ route: 'notification-workflows', label: 'Notification workflows'" in source
    for marker in (
        'data-action="create-notification-workflow"',
        'data-action="instantiate-notification-template"',
        'data-action="trigger-notification-workflow"',
        'data-action="evaluate-notification-digest"',
        'data-action="create-notification-feed"',
        'data-action="create-notification-context"',
        'data-action="create-notification-layout"',
        'data-action="create-notification-webhook"',
        'data-form="filter-notification-messages"',
        "api(base + '/workflows')", "api(base + '/templates')",
        "api(base + '/api-contract')", "api(base + '/messages' + feedParam)",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("create-notification-workflow", "instantiate-notification-template",
                 "trigger-notification-workflow", "evaluate-notification-digest",
                 "create-notification-feed", "create-notification-context",
                 "create-notification-layout", "create-notification-webhook"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("create-notification-workflow", "instantiate-notification-template",
                 "trigger-notification-workflow", "evaluate-notification-digest",
                 "create-notification-feed", "create-notification-context",
                 "create-notification-layout", "create-notification-webhook",
                 "filter-notification-messages"):
        assert name in forms, f"unhandled data-form: {name}"


def test_feedback_intelligence_route_controls_are_rendered_and_dispatched():
    """FB-024/085/096/097/098: feedback controls must not become dead UI."""
    source = _source()
    assert "async function loadFeedbackIntelligence(token)" in source
    assert "case 'feedback-intelligence': return loadFeedbackIntelligence(token)" in source
    assert "{ route: 'feedback-intelligence', label: 'Feedback intelligence'" in source
    for marker in (
        'data-action="create-feedback-dataset"', 'data-action="create-feedback-field"',
        'data-action="create-feedback-segment"', 'data-action="create-feedback-dashboard"',
        'data-action="create-feedback-source"', 'data-action="ingest-feedback"',
        'data-action="view-feedback-records"', 'data-action="view-feedback-dashboard"',
        "api(base + '/api-contract')", "api(base + '/unify/insights')",
        "api(base + '/fields')", "api(base + '/dashboards')",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("create-feedback-dataset", "create-feedback-field", "create-feedback-segment",
                 "create-feedback-dashboard", "create-feedback-source", "ingest-feedback",
                 "view-feedback-records", "view-feedback-dashboard"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("create-feedback-dataset", "create-feedback-field", "create-feedback-segment",
                 "create-feedback-dashboard", "create-feedback-source", "ingest-feedback"):
        assert name in forms, f"unhandled data-form: {name}"


def test_experiment_stats_route_controls_are_rendered_and_dispatched():
    """GB-020/021/022/023/038/042: statistics controls must not be dead UI."""
    source = _source()
    assert "async function loadExperimentStats(token)" in source
    assert "case 'experiment-stats': return loadExperimentStats(token)" in source
    assert "{ route: 'experiment-stats', label: 'Experiment statistics'" in source
    for marker in (
        'data-action="create-experiment-metric"',
        'data-action="create-experiment-definition"',
        'data-action="record-experiment-observation"',
        'data-action="analyze-experiment"',
        'data-action="check-experiment-srm"',
        'data-action="check-experiment-health"',
        'data-action="run-power-analysis"',
        'data-action="run-correction"',
        "api(base + '/api-contract')", "api(base + '/metrics')", "api(base + '/experiments')",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("create-experiment-metric", "create-experiment-definition",
                 "record-experiment-observation", "analyze-experiment", "check-experiment-srm",
                 "check-experiment-health", "run-power-analysis", "run-correction"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("create-experiment-metric", "create-experiment-definition",
                 "record-experiment-observation", "analyze-experiment", "run-power-analysis",
                 "run-correction"):
        assert name in forms, f"unhandled data-form: {name}"


def test_experiment_ops_route_controls_are_rendered_and_dispatched():
    """GB-007/012/013/014/025/026/039/041/048/049 controls must not be dead UI."""
    source = _source()
    assert "async function loadExperimentOps(token)" in source
    assert "case 'experiment-ops': return loadExperimentOps(token)" in source
    assert "{ route: 'experiment-ops', label: 'Experiment operations'" in source
    for marker in (
        'data-action="create-experiment-project"', 'data-action="archive-experiment-project"',
        'data-action="create-saved-group"', 'data-action="create-experiment-dimension"',
        'data-action="create-experiment-segment"', 'data-action="view-flag-history"',
        'data-action="create-flag-revision"', 'data-action="publish-flag-revision"',
        'data-action="archive-flag"', 'data-action="diagnose-flag"',
        'data-action="create-aa-test"', 'data-action="view-aa-result"',
        'data-action="create-timeseries-point"', 'data-action="view-timeseries"',
        'data-action="view-stale-flags"',
        "api(base + '/api-contract')", "api(base + '/stale-flags')",
        "api(base + '/projects')", "api(apiW('/flags'))",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("create-experiment-project", "archive-experiment-project",
                 "create-saved-group", "create-experiment-dimension", "create-experiment-segment",
                 "view-flag-history", "create-flag-revision", "publish-flag-revision",
                 "archive-flag", "diagnose-flag", "create-aa-test", "view-aa-result",
                 "create-timeseries-point", "view-timeseries", "view-stale-flags"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("create-experiment-project", "create-saved-group", "create-experiment-dimension",
                 "create-experiment-segment", "create-flag-revision", "archive-flag",
                 "diagnose-flag", "create-aa-test", "create-timeseries-point", "view-timeseries"):
        assert name in forms, f"unhandled data-form: {name}"


def test_experiment_queries_route_controls_are_rendered_and_dispatched():
    """GB-024/027/028/034/035/037/101 controls must not be dead UI."""
    source = _source()
    assert "async function loadExperimentQueries(token)" in source
    assert "case 'experiment-queries': return loadExperimentQueries(token)" in source
    assert "{ route: 'experiment-queries', label: 'Experiment queries'" in source
    for marker in (
        'data-action="create-query-fact-table"', 'data-action="preview-query-fact-table"',
        'data-action="create-discovery-query"', 'data-action="run-discovery-query"',
        'data-action="create-assignment-query"', 'data-action="run-assignment-query"',
        'data-action="create-identifier-type"', 'data-action="normalize-identifier"',
        'data-action="create-identifier-join"', 'data-action="resolve-identifier-join"',
        'data-action="create-experiment-funnel"', 'data-action="view-experiment-funnel"',
        'data-action="create-experiment-report"', 'data-action="run-experiment-report"',
        'data-action="assess-carryover"', 'data-action="acknowledge-carryover"',
        "api(base + '/api-contract')", "api(base + '/fact-tables')",
        "api(base + '/discovery-queries')", "api(base + '/assignment-queries')",
        "api(base + '/identifier-types')", "api(base + '/identifier-joins')",
        "api(base + '/funnels')", "api(base + '/reports')", "api(base + '/carryover')",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("create-query-fact-table", "preview-query-fact-table",
                 "create-discovery-query", "run-discovery-query", "create-assignment-query",
                 "run-assignment-query", "create-identifier-type", "normalize-identifier",
                 "create-identifier-join", "resolve-identifier-join", "create-experiment-funnel",
                 "view-experiment-funnel", "create-experiment-report", "run-experiment-report",
                 "assess-carryover", "acknowledge-carryover"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("create-query-fact-table", "create-discovery-query", "create-assignment-query",
                 "create-identifier-type", "create-identifier-join", "resolve-identifier-join",
                 "create-experiment-funnel", "create-experiment-report", "assess-carryover"):
        assert name in forms, f"unhandled data-form: {name}"


def test_experiment_platform_route_controls_are_rendered_and_dispatched():
    """GB-061/062/065/066/067 controls must not be dead UI."""
    source = _source()
    assert "async function loadExperimentPlatform(token)" in source
    assert "case 'experiment-platform': return loadExperimentPlatform(token)" in source
    assert "{ route: 'experiment-platform', label: 'Experiment platform'" in source
    for marker in (
        'data-action="view-experiment-openapi"', 'data-action="bind-experiment-role"',
        'data-action="check-experiment-role"',
        "api(base + '/api-contract')", "api(base + '/openapi-status')",
        "api(base + '/rest-inventory')", "api(base + '/credentials')",
        "api(base + '/roles')", "api(base + '/roles/bindings')",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-experiment-openapi", "bind-experiment-role", "check-experiment-role"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("bind-experiment-role", "check-experiment-role"):
        assert name in forms, f"unhandled data-form: {name}"


def test_experiment_delivery_route_controls_are_rendered_and_dispatched():
    """GB-071/072/073/074/075/076/081/082/083 controls must not be dead UI."""
    source = _source()
    assert "async function loadExperimentDelivery(token)" in source
    assert "case 'experiment-delivery': return loadExperimentDelivery(token)" in source
    assert "{ route: 'experiment-delivery', label: 'Experiment delivery'" in source
    for marker in (
        'data-action="view-delivery-contract"', 'data-action="create-delivery-webhook"',
        'data-action="emit-delivery-webhook"', 'data-action="purge-delivery-cache"',
        'data-action="schedule-refresh-job"', 'data-action="run-refresh-job"',
        "api(base + '/api-contract')", "api(base + '/webhooks')",
        "api(base + '/notifier')", "api(base + '/cache')",
        "api(base + '/proxy')", "api(base + '/refresh-jobs')",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in (
        "view-delivery-contract", "create-delivery-webhook", "emit-delivery-webhook",
        "purge-delivery-cache", "schedule-refresh-job", "run-refresh-job",
    ):
        assert name in actions, f"unhandled data-action: {name}"
    for name in (
        "create-delivery-webhook", "emit-delivery-webhook",
        "purge-delivery-cache", "schedule-refresh-job",
    ):
        assert name in forms, f"unhandled data-form: {name}"


def test_survey_delivery_route_controls_are_rendered_and_dispatched():
    """FB-002..006/010/015/036/038/074/075/079/080/183/184..187 controls must not be dead UI."""
    source = _source()
    assert "async function loadSurveyDelivery(token)" in source
    assert "case 'survey-delivery': return loadSurveyDelivery(token)" in source
    assert "{ route: 'survey-delivery', label: 'Survey delivery'" in source
    for marker in (
        'data-action="view-survey-contract"', 'data-action="create-survey-config"',
        'data-action="evaluate-survey-creative"',
        "api(base + '/api-contract')", "api(base + '/configs')",
        "api(base + '/creatives')",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-survey-contract", "create-survey-config", "evaluate-survey-creative"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("create-survey-config", "evaluate-survey-creative"):
        assert name in forms, f"unhandled data-form: {name}"


def test_search_advanced_route_controls_are_rendered_and_dispatched():
    """MS-001/022/036/038/042/048/053/074..078/095/103 controls must not be dead UI."""
    source = _source()
    assert "async function loadSearchAdvanced(token)" in source
    assert "case 'search-advanced': return loadSearchAdvanced(token)" in source
    assert "{ route: 'search-advanced', label: 'Advanced search'" in source
    for marker in (
        'data-action="view-advanced-contract"',
        "api(base + '/api-contract')", "api(base + '/federations')",
        'data-form="advanced-hybrid-search"', 'data-form="advanced-suggest"',
        'data-form="advanced-federated-search"', 'data-form="create-advanced-embedder"',
        'data-form="create-advanced-suggestion"', 'data-form="create-advanced-federation"',
        'data-form="advanced-swap"', 'data-form="advanced-edit-function"',
        'data-form="advanced-compact"', 'data-form="create-advanced-template"',
        'data-form="advanced-template-render"', 'data-form="create-advanced-preview"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    assert "view-advanced-contract" in actions, "unhandled data-action: view-advanced-contract"
    for name in (
        "create-advanced-embedder", "advanced-hybrid-search", "create-advanced-suggestion",
        "advanced-suggest", "create-advanced-federation", "advanced-federated-search",
        "advanced-swap", "advanced-edit-function", "advanced-compact",
        "create-advanced-template", "advanced-template-render", "create-advanced-preview",
    ):
        assert name in forms, f"unhandled data-form: {name}"


def test_document_engagement_route_controls_are_rendered_and_dispatched():
    """PM-007/010/018/024/025/027/076/077/083/084/085/091 controls must not be dead UI."""
    source = _source()
    assert "async function loadDocumentEngagement(token)" in source
    assert "case 'document-engagement': return loadDocumentEngagement(token)" in source
    assert "{ route: 'document-engagement', label: 'Document engagement'" in source
    for marker in (
        'data-action="view-engagement-contract"', 'data-action="view-document-analytics"',
        'data-action="remove-internal-visitor"',
        "api(base + '/api-contract')", "api(base + '/internal-visitors')",
        'data-form="record-document-event"', 'data-form="record-document-click"',
        'data-form="add-document-reaction"', 'data-form="add-document-feedback"',
        'data-form="add-document-annotation"', 'data-form="add-internal-visitor"',
        'data-form="update-document-metadata"', 'data-form="promote-document-version"',
        'data-form="search-document-names"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-engagement-contract", "view-document-analytics", "remove-internal-visitor"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in (
        "record-document-event", "record-document-click", "add-document-reaction",
        "add-document-feedback", "add-document-annotation", "add-internal-visitor",
        "update-document-metadata", "promote-document-version", "search-document-names",
    ):
        assert name in forms, f"unhandled data-form: {name}"


def test_notification_automation_route_controls_are_rendered_and_dispatched():
    """NV-009/015/026/027/031/103/104/107/118 controls must not be dead UI."""
    source = _source()
    assert "async function loadNotificationAutomation(token)" in source
    assert "case 'notification-automation': return loadNotificationAutomation(token)" in source
    assert "{ route: 'notification-automation', label: 'Notification automation'" in source
    for marker in (
        'data-action="view-automation-contract"', 'data-action="toggle-automation-flag"',
        'data-action="remove-automation-routing-rule"',
        "api(base + '/api-contract')", "api(base + '/quotas')", "api(base + '/feature-flags')",
        "api(base + '/subscribers')", "api(base + '/code-steps')", "api(base + '/http-stubs')",
        "api(base + '/routing-rules')", "api(base + '/demo-providers')", "api(base + '/deliveries')",
        'data-form="automation-quota-override"', 'data-form="automation-subscriber-search"',
        'data-form="automation-subscriber-create"', 'data-form="automation-subscriber-bulk"',
        'data-form="automation-endpoint-add"', 'data-form="automation-code-step-create"',
        'data-form="automation-code-step-evaluate"', 'data-form="automation-http-stub-create"',
        'data-form="automation-http-step-create"', 'data-form="automation-routing-rule-create"',
        'data-form="automation-routing-evaluate"', 'data-form="automation-demo-send"',
        'data-form="automation-broadcast"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-automation-contract", "toggle-automation-flag", "remove-automation-routing-rule"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in (
        "automation-quota-override", "automation-subscriber-search", "automation-subscriber-create",
        "automation-subscriber-bulk", "automation-endpoint-add", "automation-code-step-create",
        "automation-code-step-evaluate", "automation-http-stub-create", "automation-http-step-create",
        "automation-routing-rule-create", "automation-routing-evaluate", "automation-demo-send",
        "automation-broadcast",
    ):
        assert name in forms, f"unhandled data-form: {name}"


def test_sales_engagement_route_controls_are_rendered_and_dispatched():
    """SB-008/009/010/012/015/017/019/022/023/026/028/055 controls must not be dead UI."""
    source = _source()
    assert "async function loadSalesEngagement(token)" in source
    assert "case 'sales-engagement': return loadSalesEngagement(token)" in source
    assert "{ route: 'sales-engagement', label: 'Sales engagement'" in source
    for marker in (
        'data-action="view-sales-contract"', 'data-action="activate-free-signals"',
        'data-action="activate-sales-signal"', 'data-action="evaluate-sales-cohort"',
        'data-action="remove-send-rule"', 'data-action="outbox-transition"',
        "api(base + '/api-contract')", "api(base + '/signals')", "api(base + '/cohorts')",
        "api(base + '/drafts')", "api(base + '/delivery-status')", "api(base + '/delivery-rules')",
        "api(base + '/local-queue')",
        'data-form="sales-cohort-create"', 'data-form="sales-offer-suggest"',
        'data-form="sales-drafts-generate"', 'data-form="sales-sending-mode"',
        'data-form="sales-autopilot-optin"', 'data-form="sales-sending-pause"',
        'data-form="sales-send-rule-create"', 'data-form="sales-outbox-enqueue"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-sales-contract", "activate-free-signals", "activate-sales-signal",
                 "evaluate-sales-cohort", "remove-send-rule", "outbox-transition"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("sales-cohort-create", "sales-offer-suggest", "sales-drafts-generate",
                 "sales-sending-mode", "sales-autopilot-optin", "sales-sending-pause",
                 "sales-send-rule-create", "sales-outbox-enqueue"):
        assert name in forms, f"unhandled data-form: {name}"


def test_conversation_ops_route_controls_are_rendered_and_dispatched():
    """CW-006/010/020/021/022/025/029/032/052/053/054/055/056 controls must not be dead UI."""
    source = _source()
    assert "async function loadConversationOps(token)" in source
    assert "case 'conversation-ops': return loadConversationOps(token)" in source
    assert "{ route: 'conversation-ops', label: 'Conversation ops'" in source
    for marker in (
        'data-action="view-conversation-contract"',
        'data-action="expire-conversation-snoozes"',
        'data-action="unsnooze-conversation"',
        'data-action="conversation-set-typing"',
        'data-action="remove-conversation-folder"',
        "api(base + '/api-contract')", "api(base + '/presence')", "api(base + '/snoozes')",
        "api(base + '/mentions')", "api(base + '/folders')", "api(base + '/mutes')",
        "api(base + '/inbox-hours')",
        'data-form="conversation-presence"', 'data-form="conversation-snooze"',
        'data-form="conversation-mention-note"', 'data-form="conversation-reply"',
        'data-form="conversation-collision"', 'data-form="conversation-receipt"',
        'data-form="conversation-bulk"', 'data-form="conversation-folder-create"',
        'data-form="conversation-mute"', 'data-form="conversation-hours-create"',
        'data-form="conversation-hours-override"', 'data-form="conversation-hours-holiday"',
        'data-form="conversation-hours-close-region"',
        'data-form="conversation-hours-availability"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-conversation-contract", "expire-conversation-snoozes",
                 "unsnooze-conversation", "conversation-set-typing", "remove-conversation-folder"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("conversation-presence", "conversation-snooze", "conversation-mention-note",
                 "conversation-reply", "conversation-collision", "conversation-receipt",
                 "conversation-bulk", "conversation-folder-create", "conversation-mute",
                 "conversation-hours-create", "conversation-hours-override",
                 "conversation-hours-holiday", "conversation-hours-close-region",
                 "conversation-hours-availability"):
        assert name in forms, f"unhandled data-form: {name}"

def test_exposure_route_controls_are_rendered_and_dispatched():
    """GB-134..GB-147 provider adapters must be visible and operable in the UI."""
    source = _source()
    assert "async function loadExperimentExposure(token)" in source
    assert "case 'experiment-exposure': return loadExperimentExposure(token)" in source
    assert "{ route: 'experiment-exposure', label: 'Experiment exposure'" in source
    for marker in (
        'data-action="view-exposure-contract"', 'data-action="view-exposure-sample"',
        'data-action="toggle-exposure-tracker"',
        "api(base + '/api-contract')", "api(base + '/providers')",
        "api(base + '/trackers')", "api(base + '/exposures')",
        "api(base + '/exposures/stats')", "api(base + '/rejections')",
        "api(base + '/batches')",
        'data-form="exposure-tracker-create"', 'data-form="exposure-mapping-set"',
        'data-form="exposure-ingest"', 'data-form="exposure-batch-ingest"',
        "openConfirm('Disable exposure tracker'",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-exposure-contract", "view-exposure-sample", "toggle-exposure-tracker"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("exposure-tracker-create", "exposure-mapping-set", "exposure-ingest",
                 "exposure-batch-ingest"):
        assert name in forms, f"unhandled data-form: {name}"


def test_wiki_pages_route_controls_are_rendered_and_dispatched():
    """PL-096..PL-103 wiki collaboration must be visible and operable in the UI."""
    source = _source()
    assert "async function loadWikiPages(token)" in source
    assert "case 'wiki-pages': return loadWikiPages(token)" in source
    assert "{ route: 'wiki-pages', label: 'Wiki pages'" in source
    assert "'wiki-pages': ['Wiki pages', 'Operations']" in source
    for marker in (
        'data-action="view-wiki-contract"', 'data-action="wiki-restore-revision"',
        'data-action="wiki-comment-block"', 'data-action="wiki-resolve-comment"',
        "api(base + '/api-contract')", "api(pbase + '/revisions')",
        "api(pbase + '/analytics')", "api(pbase + '/publication')",
        "api(pbase + '/exports')", "api(pbase + '/labels')",
        "api(pbase + '/blocks')", "api(pbase + '/comments')",
        "api(pbase + '/editing')", "api(base + '/trees')",
        'data-form="wiki-page-select"', 'data-form="wiki-revision"',
        'data-form="wiki-view"', 'data-form="wiki-publication"',
        'data-form="wiki-export"', 'data-form="wiki-label"',
        'data-form="wiki-parent"', 'data-form="wiki-collection"',
        'data-form="wiki-blocks"', 'data-form="wiki-editing"',
        'data-form="wiki-comment-inline"',
        "openConfirm('Restore wiki revision'",
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-wiki-contract", "wiki-restore-revision", "wiki-comment-block",
                 "wiki-resolve-comment"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("wiki-page-select", "wiki-revision", "wiki-view", "wiki-publication",
                 "wiki-export", "wiki-label", "wiki-parent", "wiki-collection",
                 "wiki-blocks", "wiki-editing", "wiki-comment-inline"):
        assert name in forms, f"unhandled data-form: {name}"


def test_work_item_planning_route_controls_are_rendered_and_dispatched():
    """PL-013..PL-141 planning features must be visible and operable in the UI."""
    source = _source()
    assert "async function loadWorkItemPlanning(token)" in source
    assert "case 'work-item-planning': return loadWorkItemPlanning(token)" in source
    assert "{ route: 'work-item-planning', label: 'Work-item planning'" in source
    assert "'work-item-planning': ['Work-item planning', 'Operations']" in source
    for marker in (
        'data-action="view-planning-contract"', 'data-action="planning-open-item"',
        'data-action="planning-materialize"', 'data-action="planning-unsubscribe"',
        "api(base + '/api-contract')", "api(pbase + '/relations')",
        "api(pbase + '/dependencies')", "api(pbase + '/estimates')",
        "api(base + '/calendar')", "api(base + '/roadmap')", "api(base + '/timeline')",
        "api(pbase + '/updates')", "api(pbase + '/recurrences')",
        "api(pbase + '/time-logs')", "api(pbase + '/subscribers')",
        "api(pbase + '/notification-recipients')", "api(base + '/estimates/aggregate')",
        'data-form="planning-item-select"', 'data-form="planning-relation"',
        'data-form="planning-dependency"', 'data-form="planning-scheme"',
        'data-form="planning-estimate"', 'data-form="planning-schedule"',
        'data-form="planning-cell"', 'data-form="planning-update"',
        'data-form="planning-recurrence"', 'data-form="planning-time-log"',
        'data-form="planning-subscribe"', 'data-form="planning-template"',
        'data-form="planning-instantiate"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-planning-contract", "planning-open-item",
                 "planning-materialize", "planning-unsubscribe"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("planning-item-select", "planning-relation", "planning-dependency",
                 "planning-scheme", "planning-estimate", "planning-schedule",
                 "planning-cell", "planning-update", "planning-recurrence",
                 "planning-time-log", "planning-subscribe", "planning-template",
                 "planning-instantiate"):
        assert name in forms, f"unhandled data-form: {name}"


def test_marketing_content_route_controls_are_rendered_and_dispatched():
    """MT-009/029/031/032/036/037/048 must be visible and operable."""
    source = _source()
    assert "async function loadMarketingContent(token)" in source
    assert "case 'marketing-content': return loadMarketingContent(token)" in source
    assert "{ route: 'marketing-content', label: 'Marketing content'" in source
    assert "'marketing-content': ['Marketing content', 'Operations']" in source
    for marker in (
        'data-action="view-marketing-content-contract"',
        'data-action="marketing-page-preview"',
        'data-action="marketing-page-publish"',
        'data-action="marketing-dashboard-view"',
        "api(base + '/api-contract')", "api(base + '/landing-pages')",
        "api(base + '/assets')", "api(base + '/dashboard')",
        "api(apiW('/marketing-content/contact-types')",
        "api(apiW('/marketing-content/forms')",
        "api(apiW('/marketing-content/dynamic-content')",
        "No Mautic source, hosted service, external storage, email, SMS or outbound HTTP",
        'data-form="marketing-contact-classify"', 'data-form="marketing-contact-identify"',
        'data-form="marketing-contact-get"',
        'data-form="marketing-page-create"', 'data-form="marketing-form-create"',
        'data-form="marketing-form-progressive"', 'data-form="marketing-form-submit"',
        'data-form="marketing-content-create"', 'data-form="marketing-dynamic-resolve"',
        'data-form="marketing-asset-add"', 'data-form="marketing-widget-create"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-marketing-content-contract",
                 "marketing-page-preview", "marketing-page-publish", "marketing-dashboard-view"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
    for name in ("marketing-contact-classify", "marketing-contact-identify",
                 "marketing-contact-get", "marketing-page-create", "marketing-form-create", "marketing-form-progressive",
                 "marketing-form-submit", "marketing-content-create", "marketing-dynamic-resolve",
                 "marketing-asset-add", "marketing-widget-create"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"


def test_support_reporting_route_controls_are_rendered_and_dispatched():
    """CW-096/097/098/099/101/104/114/117 must be visible and operable."""
    source = _source()
    assert "async function loadSupportReporting(token)" in source
    assert "case 'support-reporting': return loadSupportReporting(token)" in source
    assert "{ route: 'support-reporting', label: 'Support reporting'" in source
    assert "'support-reporting': ['Support reporting', 'Operations']" in source
    for marker in (
        'data-action="view-support-reporting-contract"',
        'data-action="support-report-export"',
        'data-action="support-csat-token-issue"',
        "api(base + '/reports/agents'", "api(base + '/reports/teams'",
        "api(base + '/reports/inboxes'", "api(base + '/reports/labels'",
        "api(base + '/reports/runs')", "api(base + '/csat-rules')",
        "api(base + '/csat-responses')", "api(base + '/api-contract')",
        "No Chatwoot source, hosted endpoint, webhook callback, outbound HTTP or message delivery",
        'data-form="support-report-filter"', 'data-form="support-csat-rule-create"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-support-reporting-contract", "support-report-export",
                 "support-csat-token-issue"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
    for name in ("support-report-filter", "support-csat-rule-create"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"


def test_email_engagement_route_controls_are_rendered_and_dispatched():
    """MT-014/015/017/018/020/021/022/023/024 email features must be visible."""
    source = _source()
    assert "async function loadEmailEngagement(token)" in source
    assert "case 'email-engagement': return loadEmailEngagement(token)" in source
    assert "{ route: 'email-engagement', label: 'Email engagement'" in source
    assert "'email-engagement': ['Email engagement', 'Operations']" in source
    for marker in (
        'data-action="view-email-contract"', 'data-action="email-open-template"',
        'data-action="email-online-version"',
        "api(base + '/api-contract')", "api(base + '/templates')",
        "api(pbase + '/formats')", "api(pbase + '/translations')",
        "api(pbase + '/variants/select')", "api(pbase + '/images')",
        "api(pbase + '/engagement')", "api(pbase + '/online')", "api(base + '/signatures')",
        'data-form="email-template-create"', 'data-form="email-translation-create"',
        'data-form="email-variant-create"', 'data-form="email-token-create"',
        'data-form="email-bounce-create"', 'data-form="email-reply-create"',
        'data-form="email-signature-save"', 'data-form="email-image-add"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-email-contract", "email-open-template", "email-online-version"):
        assert name in actions, f"unhandled data-action: {name}"
    for name in ("email-template-create", "email-translation-create", "email-variant-create",
                 "email-token-create", "email-bounce-create", "email-reply-create",
                 "email-signature-save", "email-image-add"):
        assert name in forms, f"unhandled data-form: {name}"


def test_work_collaboration_route_controls_are_rendered_and_dispatched():
    """PL-031/032/039/048/050/051/130/132 must be visible and operable."""
    source = _source()
    assert "async function loadWorkCollaboration(token)" in source
    assert "case 'work-collab': return loadWorkCollaboration(token)" in source
    assert "{ route: 'work-collab', label: 'Work collaboration'" in source
    assert "'work-collab': ['Work collaboration', 'Operations']" in source
    for marker in (
        'data-action="view-collab-contract"', 'data-action="collab-open-item"',
        'data-action="collab-cursor-next"', 'data-action="collab-cursor-prev"',
        'data-action="collab-guarded-open"',
        "api(base + '/api-contract')", "api(cursorPath)",
        "api(base + '/projects/' + encodeURIComponent(projectId) + '/collaboration')",
        "api(pbase + '/attachments')", "api(pbase + '/mentions')",
        "api(pbase + '/shaped')", "api(pbase + '/restriction')", "api(pbase + '/guarded')",
        "api(apiW('/storage/files'))",
        "No Plane source, Django transport, hosted endpoint, outbound HTTP or external import provider is claimed.",
        'data-form="collab-project-select"', 'data-form="collab-item-select"',
        'data-form="collab-cursor-page"', 'data-form="collab-csv-import"',
        'data-form="collab-attachment-add"', 'data-form="collab-mention-create"',
        'data-form="collab-team-note"', 'data-form="collab-restriction-set"',
        'data-form="collab-shape"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-collab-contract", "collab-open-item",
                 "collab-cursor-next", "collab-cursor-prev", "collab-guarded-open"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
    for name in ("collab-project-select", "collab-item-select", "collab-cursor-page",
                 "collab-csv-import", "collab-attachment-add", "collab-mention-create",
                 "collab-team-note", "collab-restriction-set", "collab-shape"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"


def test_advanced_experimentation_route_controls_are_rendered_and_dispatched():
    """GB-187/188/189/214/215/217/222/237 must be visible and operable."""
    source = _source()
    assert "async function loadAdvancedExperiments(token)" in source
    assert "case 'advanced-experiments': return loadAdvancedExperiments(token)" in source
    assert "{ route: 'advanced-experiments', label: 'Advanced experimentation'" in source
    assert "'advanced-experiments': ['Advanced experimentation', 'Operations']" in source
    for marker in (
        'data-action="view-adv-contract"', 'data-action="adv-open-analysis"',
        "api(base + '/api-contract')", "api(base + '/analyses')",
        "api(base + '/holdouts')", "api(base + '/bandits/' + encodeURIComponent(banditKey))",
        "api(base + '/analyses/' + encodeURIComponent(analysisId))",
        "No GrowthBook source, stats package, hosted platform, warehouse, SDK or external statistics service is claimed.",
        'data-form="adv-analysis-create"', 'data-form="adv-bandit-arm"',
        'data-form="adv-bandit-recommend"', 'data-form="adv-bandit-reward"',
        'data-form="adv-holdout-create"', 'data-form="adv-holdout-check"',
    ):
        assert marker in source, f"missing UI marker: {marker}"
    actions = _handlers(source, r"case '([a-z0-9-]+)':")
    forms = _handlers(source, r"name === '([a-z0-9-]+)'")
    for name in ("view-adv-contract", "adv-open-analysis"):
        assert name in actions, f"unhandled data-action: {name}"
        assert source.count(f"case '{name}':") == 1, f"duplicate action: {name}"
    for name in ("adv-analysis-create", "adv-bandit-arm", "adv-bandit-recommend",
                 "adv-bandit-reward", "adv-holdout-create", "adv-holdout-check"):
        assert name in forms, f"unhandled data-form: {name}"
        assert source.count(f"name === '{name}'") == 1, f"duplicate form: {name}"
