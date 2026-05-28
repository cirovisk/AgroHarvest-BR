"""
Sistema de Alertas do Pipeline AgroHarvest (PostgreSQL).

- Grava um JSON de status em data/logs/ após cada execução.
- Envia resumo no Telegram via Bot API (opcional, requer TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env).

Uso no main.py:
    alert = AlertManager()
    alert.record_error("zarc", exception)
    alert.send_report(success=["conab"], failed=["zarc"], duration=42.3)
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class AlertManager:
    """Coleta métricas de execução, persiste JSON e notifica via Telegram."""

    def __init__(self, pipeline_name: str = "AgroHarvest BR (PostgreSQL)"):
        self.pipeline_name = pipeline_name
        self.errors: list[dict] = []
        self.warnings: list[str] = []
        self.started_at: float = time.monotonic()
        self.start_ts: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        self._token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
        self._chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")
        self._alert_on_success: bool = os.getenv("ALERT_ON_SUCCESS", "false").lower() == "true"
        self._log_dir: Path = Path(os.getenv("LOG_STATUS_PATH", "data/logs"))

    # ------------------------------------------------------------------
    # Coleta de eventos
    # ------------------------------------------------------------------

    def record_error(self, source: str, exc: Exception) -> None:
        """Registra uma falha de source para inclusão no relatório."""
        self.errors.append({"source": source, "message": str(exc)})

    def record_warning(self, message: str) -> None:
        """Registra um aviso livre para inclusão no relatório."""
        self.warnings.append(message)

    # ------------------------------------------------------------------
    # Relatório final
    # ------------------------------------------------------------------

    def send_report(self, success: list[str], failed: list[str], duration: float | None = None) -> None:
        """
        Salva o JSON de status e (opcionalmente) envia mensagem Telegram.

        Args:
            success: Lista de sources que concluíram com êxito.
            failed:  Lista de sources que falharam.
            duration: Duração total em segundos (calculada automaticamente se omitida).
        """
        if duration is None:
            duration = time.monotonic() - self.started_at

        total = len(success) + len(failed)
        if not failed:
            status = "SUCCESS"
        elif success:
            status = "PARTIAL_FAILURE"
        else:
            status = "FAILURE"

        payload = {
            "run_id": self.start_ts,
            "pipeline": self.pipeline_name,
            "status": status,
            "duration_seconds": round(duration, 1),
            "total_sources": total,
            "sources_ok": success,
            "sources_failed": failed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }

        self._save_json(payload)

        should_notify = (status != "SUCCESS") or self._alert_on_success
        if should_notify:
            self._send_telegram(payload)
        else:
            log.info("[AlertManager] Pipeline OK — notificação Telegram suprimida (ALERT_ON_SUCCESS=false).")

    # ------------------------------------------------------------------
    # Persistência JSON
    # ------------------------------------------------------------------

    def _save_json(self, payload: dict) -> None:
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            ts_safe = self.start_ts.replace(":", "-")
            out_path = self._log_dir / f"pipeline_status_{ts_safe}.json"
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info(f"[AlertManager] Status gravado em: {out_path}")
        except Exception as e:
            log.error(f"[AlertManager] Falha ao gravar JSON de status: {e}")

    # ------------------------------------------------------------------
    # Notificação Telegram
    # ------------------------------------------------------------------

    def _build_message(self, payload: dict) -> str:
        status_icon = {"SUCCESS": "✅", "PARTIAL_FAILURE": "⚠️", "FAILURE": "🔴"}.get(payload["status"], "❓")
        status_label = {
            "SUCCESS": "SUCESSO",
            "PARTIAL_FAILURE": "FALHA PARCIAL",
            "FAILURE": "FALHA TOTAL",
        }.get(payload["status"], payload["status"])

        lines = [
            f"{status_icon} <b>{payload['pipeline']}</b> — {status_label}",
            "",
            f"📅 {payload['run_id']}",
            f"⏱ Duração: {payload['duration_seconds']}s",
            f"📊 Fontes: {payload['total_sources']} total",
        ]

        if payload["sources_ok"]:
            lines.append(f"✅ Sucesso ({len(payload['sources_ok'])}): {', '.join(payload['sources_ok'])}")

        if payload["sources_failed"]:
            lines.append(f"❌ Falhou ({len(payload['sources_failed'])}): {', '.join(payload['sources_failed'])}")

        if payload["errors"]:
            lines.append("")
            lines.append("<b>Erros:</b>")
            for err in payload["errors"][:5]:  # limita a 5 para não truncar no Telegram
                lines.append(f"  • <code>{err['source']}</code>: {err['message'][:120]}")
            if len(payload["errors"]) > 5:
                lines.append(f"  … e mais {len(payload['errors']) - 5} erro(s)")

        if payload["warnings"]:
            lines.append("")
            lines.append(f"⚠️ Avisos: {len(payload['warnings'])}")

        return "\n".join(lines)

    def _send_telegram(self, payload: dict) -> None:
        if not self._token or not self._chat_id:
            log.warning(
                "[AlertManager] TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não definidos — notificação Telegram ignorada."
            )
            return

        text = self._build_message(payload)
        api_url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        body = json.dumps(
            {
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "HTML",
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                api_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    log.info("[AlertManager] Notificação Telegram enviada com sucesso.")
                else:
                    log.warning(f"[AlertManager] Telegram retornou status inesperado: {resp.status}")
        except urllib.error.URLError as e:
            log.error(f"[AlertManager] Falha ao enviar notificação Telegram: {e}")
        except Exception as e:
            log.error(f"[AlertManager] Erro inesperado no envio Telegram: {e}")
