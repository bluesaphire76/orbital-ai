from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_loki_configuration_has_bounded_local_retention():
    config = (
        ROOT
        / "observability"
        / "loki"
        / "loki.yml"
    ).read_text()

    assert "store: tsdb" in config
    assert "schema: v13" in config
    assert "retention_enabled: true" in config
    assert "retention_period: 168h" in config
    assert "reporting_enabled: false" in config


def test_alloy_uses_bounded_docker_labels():
    config = (
        ROOT
        / "observability"
        / "alloy"
        / "config.alloy"
    ).read_text()

    assert 'regex  = "orbitalai"' in config
    assert 'target_label = "service_name"' in config
    assert 'replacement  = "orbitalai"' in config

    assert '"platform"' in config
    assert '"service_name"' in config

    # Keep the Loki index deliberately low-cardinality.
    assert 'target_label = "container"' not in config
    assert 'target_label = "container_id"' not in config
    assert 'target_label = "run_id"' not in config
    assert 'target_label = "norad_id"' not in config
    assert 'target_label = "object_id"' not in config
    assert 'target_label = "pair_id"' not in config


def test_logging_images_are_version_pinned():
    compose = (
        ROOT
        / "deploy"
        / "compose"
        / "compose.observability.yml"
    ).read_text()

    assert "grafana/loki:3.7.6" in compose
    assert "grafana/alloy:v1.19.2" in compose
    assert "grafana/loki:latest" not in compose
    assert "grafana/alloy:latest" not in compose

    assert (
        "/var/run/docker.sock:/var/run/docker.sock:ro"
        in compose
    )


def test_loki_datasource_is_provisioned():
    datasource = (
        ROOT
        / "observability"
        / "grafana"
        / "provisioning"
        / "datasources"
        / "loki.yml"
    ).read_text()

    assert "uid: orbitalai-loki" in datasource
    assert "url: http://loki:3100" in datasource
    assert "editable: false" in datasource


def test_logging_dashboard_uses_only_loki_datasource():
    dashboard_path = (
        ROOT
        / "observability"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "json"
        / "orbitalai-platform-logs.json"
    )

    dashboard = json.loads(
        dashboard_path.read_text()
    )

    assert (
        dashboard["title"]
        == "OrbitalAI - Platform Logs"
    )

    assert (
        dashboard["uid"]
        == "orbitalai-platform-logs"
    )

    assert dashboard["refresh"] == "30s"
    assert len(dashboard["panels"]) == 4

    for panel in dashboard["panels"]:
        assert (
            panel["datasource"]["uid"]
            == "orbitalai-loki"
        )

        for target in panel["targets"]:
            assert (
                'platform="orbitalai"'
                in target["expr"]
            )
