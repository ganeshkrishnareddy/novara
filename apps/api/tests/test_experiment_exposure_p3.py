"""Named acceptance tests for the clean-room experiment exposure adapters.

Each GB row's test drives the real FastAPI app, ingests that provider's
documented payload shape through a locally configured tracker and proves the
normalised exposure reaches NOVARA's shared event spine with no outbound
traffic. No vendor SDK, hosted API or upstream source is used.
"""

from __future__ import annotations

import socket

from .conftest import auth, bootstrap

API = "/api/v1/workspaces/{wid}"
EXPOSURE_EVENT = "experiment.exposure_recorded"

PROVIDERS = {
    "GB-134": "amplitude",
    "GB-135": "clevertap",
    "GB-136": "custom",
    "GB-137": "firebase",
    "GB-138": "freshpaint",
    "GB-139": "fullstory",
    "GB-140": "heap",
    "GB-141": "jitsu",
    "GB-142": "keenio",
    "GB-143": "langfuse",
    "GB-144": "mparticle",
    "GB-145": "arizephoenix",
    "GB-146": "segment",
    "GB-147": "snowplow",
}

# Independently recorded field expectations, not read from the module, so a
# sample payload that quietly stops matching the documented shape fails.
EXPECTED_FIELDS = {
    "amplitude": ("event_type", "event_properties", "experiment_id", "variation_id"),
    "clevertap": ("event", "properties", "experiment_id", "variation_id"),
    "custom": (None, None, "experiment_id", "variation_id"),
    "firebase": ("event", "params", "experiment_id", "variation_id"),
    "freshpaint": ("event", "properties", "experiment_id", "variation_id"),
    "fullstory": ("event", "properties", "experiment_id", "variation_id"),
    "heap": ("event", "properties", "experiment_id", "variation_id"),
    "jitsu": ("event", "props", "experiment_id", "variation_id"),
    "keenio": ("event_name", "keen.properties", "experiment_id", "variation_id"),
    "langfuse": ("name", "metadata", "experiment_id", "variation_id"),
    "mparticle": ("event", "attributes", "experiment_id", "variation_id"),
    "arizephoenix": ("event", "attributes", "experiment_id", "variation_id"),
    "segment": ("event", "properties", "experiment_id", "variation_id"),
    "snowplow": ("event", "properties", "experiment_id", "variation_id"),
}


def _ctx(client):
    tokens = bootstrap(client, "ExposureLab", "exposure-owner@example.com")
    return tokens["workspace_id"], auth(tokens["access_token"])


def _base(wid):
    return API.format(wid=wid) + "/experiment-exposure"


def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("an exposure adapter attempted outbound network traffic")

    monkeypatch.setattr(socket.socket, "connect", blocked)


def _get_path(data, dotted):
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _run_provider(client, monkeypatch, key):
    """Ingest one provider's documented sample, end to end, offline."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    providers = client.get(_base(wid) + "/providers", headers=h).json()
    assert key in {p["key"] for p in providers}
    event_field, props_field, experiment_field, variation_field = EXPECTED_FIELDS[key]
    sample = client.get(_base(wid) + f"/providers/{key}/sample", headers=h).json()["payload"]
    if event_field:
        assert event_field in sample
    props = _get_path(sample, props_field) if props_field else sample
    assert props[experiment_field] == "exp-1"
    assert props[variation_field] == "var-a"

    created = client.post(_base(wid) + "/trackers", headers=h, json={"provider_key": key})
    assert created.status_code == 201, created.text
    tracker_id = created.json()["id"]
    result = client.post(_base(wid) + f"/trackers/{tracker_id}/exposures", headers=h,
                         json={"payload": sample})
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "accepted"
    assert result.json()["experiment_id"] == "exp-1"
    assert result.json()["variation_id"] == "var-a"

    rows = client.get(_base(wid) + "/exposures", headers=h).json()
    assert len(rows) == 1
    assert rows[0]["provider_key"] == key
    assert rows[0]["subject"] == "subject-123"
    events = client.get(API.format(wid=wid) + "/events", headers=h).json()
    assert any(e["event_type"] == EXPOSURE_EVENT for e in events)
    stats = client.get(_base(wid) + "/exposures/stats", headers=h).json()
    assert stats["by_provider"][key] == 1 and stats["external_calls"] is False
    contract = client.get(_base(wid) + "/api-contract", headers=h).json()
    assert contract["external_calls"] is False and contract["external_delivery"] is False
    assert contract["vendor_sdk_used"] is False
    return wid, h, tracker_id, sample


def test_gb134_amplitude_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Amplitude's $exposure payload normalises locally with no outbound traffic."""
    _run_provider(client, monkeypatch, "amplitude")


def test_gb135_clevertap_exposure_maps_to_local_event_spine(client, monkeypatch):
    """CleverTap's Experiment Viewed payload normalises locally."""
    _run_provider(client, monkeypatch, "clevertap")


def test_gb136_custom_exposure_maps_to_local_event_spine(client, monkeypatch):
    """The caller-written Custom adapter normalises a plain local payload."""
    _run_provider(client, monkeypatch, "custom")


def test_gb137_firebase_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Firebase Analytics params normalise locally."""
    _run_provider(client, monkeypatch, "firebase")


def test_gb138_freshpaint_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Freshpaint properties normalise locally."""
    _run_provider(client, monkeypatch, "freshpaint")


def test_gb139_fullstory_exposure_maps_to_local_event_spine(client, monkeypatch):
    """FullStory properties normalise locally."""
    _run_provider(client, monkeypatch, "fullstory")


def test_gb140_heap_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Heap properties normalise locally."""
    _run_provider(client, monkeypatch, "heap")


def test_gb141_jitsu_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Jitsu props normalise locally."""
    _run_provider(client, monkeypatch, "jitsu")


def test_gb142_keenio_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Keen IO's nested keen.properties payload normalises locally."""
    _run_provider(client, monkeypatch, "keenio")


def test_gb143_langfuse_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Langfuse metadata normalises locally."""
    _run_provider(client, monkeypatch, "langfuse")


def test_gb144_mparticle_exposure_maps_to_local_event_spine(client, monkeypatch):
    """mParticle attributes normalise locally."""
    _run_provider(client, monkeypatch, "mparticle")


def test_gb145_arizephoenix_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Arize Phoenix attributes normalise locally."""
    _run_provider(client, monkeypatch, "arizephoenix")


def test_gb146_segment_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Segment's Experiment Viewed payload normalises locally."""
    _run_provider(client, monkeypatch, "segment")


def test_gb147_snowplow_exposure_maps_to_local_event_spine(client, monkeypatch):
    """Snowplow properties normalise locally."""
    _run_provider(client, monkeypatch, "snowplow")


def test_exposure_retries_are_idempotent_and_invalid_payloads_are_rejected(client, monkeypatch):
    """Replays dedupe on a stable key and bad payloads are logged, not dropped."""
    _no_network(monkeypatch)
    wid, h, tracker_id, sample = _run_provider(client, monkeypatch, "segment")
    again = client.post(_base(wid) + f"/trackers/{tracker_id}/exposures", headers=h,
                        json={"payload": sample})
    assert again.status_code == 201 and again.json()["status"] == "duplicate"
    assert len(client.get(_base(wid) + "/exposures", headers=h).json()) == 1
    invalid = client.post(_base(wid) + f"/trackers/{tracker_id}/exposures", headers=h,
                          json={"payload": {"event": "Something Else", "userId": "u1"}})
    assert invalid.status_code == 422
    rejections = client.get(_base(wid) + "/rejections", headers=h).json()
    assert rejections and "not an exposure" in rejections[0]["reason"]


def test_exposure_batch_counts_accepted_duplicate_and_rejected(client, monkeypatch):
    """Batch ingestion returns deterministic per-item results and one summary event."""
    _no_network(monkeypatch)
    wid, h, tracker_id, sample = _run_provider(client, monkeypatch, "amplitude")
    batch = client.post(_base(wid) + f"/trackers/{tracker_id}/exposures/batch", headers=h, json={
        "items": [
            {"payload": sample, "event_id": "evt-1"},
            {"payload": sample, "event_id": "evt-1"},
            {"payload": {"event_type": "not-an-exposure"}},
            {"payload": {**sample, "user_id": "subject-456"}, "event_id": "evt-2"},
        ],
    })
    assert batch.status_code == 201, batch.text
    body = batch.json()
    assert (body["total"], body["accepted"], body["duplicates"], body["rejected"]) == (4, 2, 1, 1)
    assert client.get(_base(wid) + "/batches", headers=h).json()[0]["accepted"] == 2
    assert len(client.get(_base(wid) + "/exposures", headers=h).json()) == 3


def test_custom_mapping_overrides_documented_field_paths(client, monkeypatch):
    """A workspace can remap any provider field via a dotted-path local mapping."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    created = client.post(_base(wid) + "/trackers", headers=h,
                          json={"provider_key": "custom"})
    assert created.status_code == 201, created.text
    tracker_id = created.json()["id"]
    for source, target in (("ctx.experiment", "experiment"),
                           ("ctx.variant", "variation"), ("ctx.user", "subject")):
        mapped = client.put(_base(wid) + f"/trackers/{tracker_id}/mappings", headers=h,
                            json={"source_field": source, "target_field": target})
        assert mapped.status_code == 200, mapped.text
    mappings = client.get(_base(wid) + f"/trackers/{tracker_id}/mappings", headers=h).json()
    assert len(mappings) == 3
    result = client.post(_base(wid) + f"/trackers/{tracker_id}/exposures", headers=h, json={
        "payload": {"ctx": {"experiment": "remote-exp", "variant": "variant-b",
                            "user": "user-9"}},
    })
    assert result.status_code == 201, result.text
    assert result.json()["experiment_id"] == "remote-exp"
    assert result.json()["variation_id"] == "variant-b"
    assert client.get(_base(wid) + "/exposures", headers=h,
                      params={"experiment_id": "remote-exp"}).json()[0]["subject"] == "user-9"
    bad = client.put(_base(wid) + f"/trackers/{tracker_id}/mappings", headers=h,
                     json={"source_field": "x", "target_field": "arbitrary"})
    assert bad.status_code == 422


def test_tracker_configuration_is_validated_and_can_be_disabled(client, monkeypatch):
    """Unknown providers are refused, duplicates conflict and disabled trackers reject."""
    _no_network(monkeypatch)
    wid, h = _ctx(client)
    assert client.post(_base(wid) + "/trackers", headers=h,
                       json={"provider_key": "not-a-provider"}).status_code == 422
    created = client.post(_base(wid) + "/trackers", headers=h,
                          json={"provider_key": "heap"})
    assert created.status_code == 201
    tracker_id = created.json()["id"]
    assert client.post(_base(wid) + "/trackers", headers=h,
                       json={"provider_key": "heap"}).status_code == 409
    updated = client.put(_base(wid) + f"/trackers/{tracker_id}", headers=h,
                         json={"enabled": False, "note": "paused"})
    assert updated.status_code == 200 and updated.json()["enabled"] is False
    sample = client.get(_base(wid) + "/providers/heap/sample", headers=h).json()["payload"]
    assert client.post(_base(wid) + f"/trackers/{tracker_id}/exposures", headers=h,
                       json={"payload": sample}).status_code == 409
    assert client.get(_base(wid) + "/providers/missing/sample", headers=h).status_code == 404
    assert client.post(_base(wid) + "/trackers/missing/exposures", headers=h,
                       json={"payload": sample}).status_code == 404


def test_exposure_adapters_are_workspace_isolated(client, monkeypatch):
    """A second workspace cannot read or ingest through another workspace's tracker."""
    _no_network(monkeypatch)
    wid, h, tracker_id, sample = _run_provider(client, monkeypatch, "segment")
    other = client.post("/api/v1/workspaces", headers=h, json={"name": "Other exposure lab"})
    assert other.status_code == 200, other.text
    other_wid, other_h = other.json()["workspace_id"], auth(other.json()["access_token"])
    assert client.get(_base(other_wid) + "/trackers", headers=other_h).json() == []
    assert client.get(_base(other_wid) + "/exposures", headers=other_h).json() == []
    assert client.get(_base(other_wid) + "/rejections", headers=other_h).json() == []
    assert client.get(_base(other_wid) + "/exposures/stats", headers=other_h).json()["total"] == 0
    assert client.post(_base(other_wid) + f"/trackers/{tracker_id}/exposures", headers=other_h,
                       json={"payload": sample}).status_code == 404
    assert client.put(_base(other_wid) + f"/trackers/{tracker_id}", headers=other_h,
                      json={"enabled": False, "note": ""}).status_code == 404
    assert client.get(_base(other_wid) + f"/trackers/{tracker_id}/mappings",
                      headers=other_h).status_code == 404
