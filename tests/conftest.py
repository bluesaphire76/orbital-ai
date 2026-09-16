import pytest


@pytest.fixture(autouse=True)
def isolated_operational_metrics(tmp_path, monkeypatch):
    """No test may update the runtime telemetry shared with local containers."""
    monkeypatch.setenv("ORBITAL_METRICS_DIR", str(tmp_path / "metrics"))
