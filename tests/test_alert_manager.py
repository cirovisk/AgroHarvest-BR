import json
import os
from unittest.mock import MagicMock, patch
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
    # Usando diretório temporário para salvar logs
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
        "warnings": []
    }

    alert._save_json(payload)

    # Verifica se o arquivo foi criado e seu conteúdo é idêntico
    ts_safe = alert.start_ts.replace(":", "-")
    expected_path = log_dir / f"pipeline_status_{ts_safe}.json"
    
    assert expected_path.exists()
    
    with open(expected_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["pipeline"] == "Test Pipeline"
    assert data["status"] == "SUCCESS"
    assert data["duration_seconds"] == 12.5
    assert data["sources_ok"] == ["sidra", "conab"]


@patch("urllib.request.urlopen")
def test_send_telegram_success_no_alert(mock_urlopen):
    # Quando tudo der sucesso e ALERT_ON_SUCCESS=false (default), não envia Telegram
    alert = AlertManager(pipeline_name="Test Pipeline")
    alert._token = "test_token"
    alert._chat_id = "test_chat"

    alert.send_report(success=["sidra"], failed=[], duration=5.0)

    mock_urlopen.assert_not_called()


@patch("urllib.request.urlopen")
def test_send_telegram_success_with_alert_on_success(mock_urlopen, tmp_path):
    # Configura mock de resposta
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    with patch.dict(os.environ, {"ALERT_ON_SUCCESS": "true", "TELEGRAM_BOT_TOKEN": "token123", "TELEGRAM_CHAT_ID": "chat456"}):
        alert = AlertManager(pipeline_name="Test Pipeline")
        alert._log_dir = tmp_path
        alert.send_report(success=["sidra"], failed=[], duration=5.0)

        assert mock_urlopen.call_count == 1
        # Verifica URL e argumentos do Request
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        assert req.full_url == "https://api.telegram.org/bottoken123/sendMessage"
        assert req.get_header("Content-type") == "application/json"
        
        # Verifica corpo enviado
        body = json.loads(req.data.decode("utf-8"))
        assert body["chat_id"] == "chat456"
        assert "✅" in body["text"]
        assert "SUCESSO" in body["text"]
        assert "Test Pipeline" in body["text"]


@patch("urllib.request.urlopen")
def test_send_telegram_failure_always_alerts(mock_urlopen, tmp_path):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    with patch.dict(os.environ, {"ALERT_ON_SUCCESS": "false", "TELEGRAM_BOT_TOKEN": "token123", "TELEGRAM_CHAT_ID": "chat456"}):
        alert = AlertManager(pipeline_name="Test Pipeline")
        alert._log_dir = tmp_path
        alert.record_error("zarc", Exception("Erro crítico"))
        
        alert.send_report(success=["sidra"], failed=["zarc"], duration=10.0)

        assert mock_urlopen.call_count == 1
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        
        assert "⚠️" in body["text"]
        assert "FALHA PARCIAL" in body["text"]
        assert "zarc" in body["text"]
        assert "Erro crítico" in body["text"]
