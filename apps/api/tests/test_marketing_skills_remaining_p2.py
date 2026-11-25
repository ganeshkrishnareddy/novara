"""Named acceptance tests for the 46 newly vendored Marketing Skills rows.

Each named test drives the real FastAPI app and verifies the exact pinned
upstream SKILL.md, frontmatter at the pinned version, preserved MIT notice,
live SHA-256 / byte-length / Git blob-SHA checks for every bundled file,
workspace isolation and the closed 404 for unvendored skills. No skill is
executed, no upstream eval is run and no external action is claimed.
"""

from __future__ import annotations

import pytest

from novara_core.modules import marketing_skills as skills_module

from .conftest import auth, bootstrap
from .test_marketing_skills_p1 import _assert_pinned_row


@pytest.fixture(autouse=True)
def _clear_bundle_cache():
    skills_module.load_bundle.cache_clear()
    yield
    skills_module.load_bundle.cache_clear()

def test_mk_002_skill_is_pinned_verified_and_isolated(client):
    """MK-002: ad-creative is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-002", "ad-creative")

def test_mk_003_skill_is_pinned_verified_and_isolated(client):
    """MK-003: ads is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-003", "ads")

def test_mk_004_skill_is_pinned_verified_and_isolated(client):
    """MK-004: ai-seo is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-004", "ai-seo")

def test_mk_006_skill_is_pinned_verified_and_isolated(client):
    """MK-006: aso is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-006", "aso")

def test_mk_007_skill_is_pinned_verified_and_isolated(client):
    """MK-007: attribution is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-007", "attribution")

def test_mk_008_skill_is_pinned_verified_and_isolated(client):
    """MK-008: churn-prevention is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-008", "churn-prevention")

def test_mk_009_skill_is_pinned_verified_and_isolated(client):
    """MK-009: co-marketing is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-009", "co-marketing")

def test_mk_010_skill_is_pinned_verified_and_isolated(client):
    """MK-010: cold-email is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-010", "cold-email")

def test_mk_011_skill_is_pinned_verified_and_isolated(client):
    """MK-011: community-marketing is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-011", "community-marketing")

def test_mk_012_skill_is_pinned_verified_and_isolated(client):
    """MK-012: competitor-profiling is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-012", "competitor-profiling")

def test_mk_013_skill_is_pinned_verified_and_isolated(client):
    """MK-013: competitors is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-013", "competitors")

def test_mk_014_skill_is_pinned_verified_and_isolated(client):
    """MK-014: content-strategy is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-014", "content-strategy")

def test_mk_016_skill_is_pinned_verified_and_isolated(client):
    """MK-016: copy-editing is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-016", "copy-editing")

def test_mk_019_skill_is_pinned_verified_and_isolated(client):
    """MK-019: customer-research is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-019", "customer-research")

def test_mk_020_skill_is_pinned_verified_and_isolated(client):
    """MK-020: directory-submissions is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-020", "directory-submissions")

def test_mk_021_skill_is_pinned_verified_and_isolated(client):
    """MK-021: emails is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-021", "emails")

def test_mk_022_skill_is_pinned_verified_and_isolated(client):
    """MK-022: events is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-022", "events")

def test_mk_023_skill_is_pinned_verified_and_isolated(client):
    """MK-023: free-tools is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-023", "free-tools")

def test_mk_024_skill_is_pinned_verified_and_isolated(client):
    """MK-024: image is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-024", "image")

def test_mk_025_skill_is_pinned_verified_and_isolated(client):
    """MK-025: influencer-marketing is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-025", "influencer-marketing")

def test_mk_026_skill_is_pinned_verified_and_isolated(client):
    """MK-026: launch is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-026", "launch")

def test_mk_027_skill_is_pinned_verified_and_isolated(client):
    """MK-027: lead-magnets is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-027", "lead-magnets")

def test_mk_028_skill_is_pinned_verified_and_isolated(client):
    """MK-028: link-building is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-028", "link-building")

def test_mk_029_skill_is_pinned_verified_and_isolated(client):
    """MK-029: marketing-council is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-029", "marketing-council")

def test_mk_030_skill_is_pinned_verified_and_isolated(client):
    """MK-030: marketing-ideas is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-030", "marketing-ideas")

def test_mk_031_skill_is_pinned_verified_and_isolated(client):
    """MK-031: marketing-loops is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-031", "marketing-loops")

def test_mk_032_skill_is_pinned_verified_and_isolated(client):
    """MK-032: marketing-plan is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-032", "marketing-plan")

def test_mk_033_skill_is_pinned_verified_and_isolated(client):
    """MK-033: marketing-psychology is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-033", "marketing-psychology")

def test_mk_034_skill_is_pinned_verified_and_isolated(client):
    """MK-034: offers is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-034", "offers")

def test_mk_035_skill_is_pinned_verified_and_isolated(client):
    """MK-035: onboarding is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-035", "onboarding")

def test_mk_036_skill_is_pinned_verified_and_isolated(client):
    """MK-036: paywalls is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-036", "paywalls")

def test_mk_037_skill_is_pinned_verified_and_isolated(client):
    """MK-037: popups is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-037", "popups")

def test_mk_038_skill_is_pinned_verified_and_isolated(client):
    """MK-038: pricing is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-038", "pricing")

def test_mk_040_skill_is_pinned_verified_and_isolated(client):
    """MK-040: programmatic-seo is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-040", "programmatic-seo")

def test_mk_041_skill_is_pinned_verified_and_isolated(client):
    """MK-041: prospecting is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-041", "prospecting")

def test_mk_042_skill_is_pinned_verified_and_isolated(client):
    """MK-042: public-relations is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-042", "public-relations")

def test_mk_043_skill_is_pinned_verified_and_isolated(client):
    """MK-043: referrals is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-043", "referrals")

def test_mk_044_skill_is_pinned_verified_and_isolated(client):
    """MK-044: reverse-engineer-marketing is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-044", "reverse-engineer-marketing")

def test_mk_045_skill_is_pinned_verified_and_isolated(client):
    """MK-045: revops is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-045", "revops")

def test_mk_046_skill_is_pinned_verified_and_isolated(client):
    """MK-046: sales-enablement is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-046", "sales-enablement")

def test_mk_047_skill_is_pinned_verified_and_isolated(client):
    """MK-047: schema is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-047", "schema")

def test_mk_049_skill_is_pinned_verified_and_isolated(client):
    """MK-049: signup is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-049", "signup")

def test_mk_050_skill_is_pinned_verified_and_isolated(client):
    """MK-050: site-architecture is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-050", "site-architecture")

def test_mk_051_skill_is_pinned_verified_and_isolated(client):
    """MK-051: sms is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-051", "sms")

def test_mk_052_skill_is_pinned_verified_and_isolated(client):
    """MK-052: social is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-052", "social")

def test_mk_053_skill_is_pinned_verified_and_isolated(client):
    """MK-053: video is the exact pinned upstream artifact."""
    _assert_pinned_row(client, "MK-053", "video")
