import csv
import json
import os
import pytest
from src.pipeline.alert_manager import AlertManager


def test_record_error_and_warning():
    alert = AlertManager(pipeline_name="Test Pipeline")

    # Valida estado inicial
    assert len(alert.errors) == 0
    assert len(alert.warnings) == 0

    # Adiciona erros e avisos
    exc = Exception("Erro de teste")
    alert.record_error("sidra", exc)
    alert.record_warning("Aviso de teste")

    assert len(alert.errors) == 1
    assert alert.errors[0] == {"source": "sidra", "message": "Erro de teste"}
    assert len(alert.warnings) == 1
    assert alert.warnings[0] == "Aviso de teste"


def test_save_json(tmp_path):
    # Use a temporary directory to save logs
    log_dir = tmp_path / "logs"
    alert = AlertManager(pipeline_name="Test Pipeline")
    alert._log_dir = log_dir

    payload = {
        "run_id": alert.start_ts,
        "pipeline": alert.pipeline_name,
        "status": "SUCCESS",
        "duration_seconds": 12.5,
        "total_sources": 2,
        "sources_ok": ["sidra", "conab"],
        "sources_failed": [],
        "error_count": 0,
        "warning_count": 0,
        "errors": [],
        "warnings": [],
    }

    alert._save_json(payload)

    # Verify that the file was created and its content is identical
    ts_safe = alert.start_ts.replace(":", "-")
    expected_path = log_dir / f"pipeline_status_{ts_safe}.json"

    assert expected_path.exists()

    with open(expected_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["pipeline"] == "Test Pipeline"
    assert data["status"] == "SUCCESS"
    assert data["duration_seconds"] == 12.5
    assert data["sources_ok"] == ["sidra", "conab"]


def test_partial_source_and_structured_result(tmp_path):
    alert = AlertManager(pipeline_name="Test Pipeline")
    alert._log_dir = tmp_path / "logs"
    result = {
        "source": "zarc",
        "status": "partial",
        "rows_loaded": 10,
        "warnings": ["cana-de-acucar sem registros"],
    }
    alert.record_source("zarc", "partial", 1.0, result=result)

    alert.send_report(success=[], partial=["zarc"], failed=[], duration=1.0)

    ts_safe = alert.start_ts.replace(":", "-")
    status_path = alert._log_dir / f"pipeline_status_{ts_safe}.json"
    metrics_path = alert._log_dir / f"pipeline_metrics_{ts_safe}.csv"
    data = json.loads(status_path.read_text(encoding="utf-8"))

    assert data["status"] == "PARTIAL_SUCCESS"
    assert data["sources_partial"] == ["zarc"]
    with metrics_path.open(encoding="utf-8", newline="") as metrics_file:
        metric = next(csv.DictReader(metrics_file))
    assert json.loads(metric["result"])["status"] == "partial"
