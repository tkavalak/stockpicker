"""Write NotificationAuditRecord rows to BigQuery."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from google.cloud import bigquery

from notification_service.models import DeliveryResult, NotificationAuditRecord

if TYPE_CHECKING:
    from notification_service.models import AlertDecision

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(
        self,
        project_id: str,
        dataset_id: str = "stock_picker",
        table_id: str = "notification_audit",
        *,
        client: bigquery.Client | None = None,
    ) -> None:
        self._client = client or bigquery.Client(project=project_id)
        self._table_ref = f"{project_id}.{dataset_id}.{table_id}"

    @property
    def table_ref(self) -> str:
        return self._table_ref

    def log_delivery(self, decision: AlertDecision, result: DeliveryResult) -> None:
        record = NotificationAuditRecord(
            decision_id=decision.decision_id,
            channel=result.channel,
            symbol=decision.symbol,
            status=result.status,
            http_status=result.http_status,
            latency_ms=result.latency_ms,
            dispatched_at=datetime.now(timezone.utc).isoformat(),
        )
        errors = self._client.insert_rows_json(self._table_ref, [record.to_bq_row()])
        if errors:
            logger.error("BigQuery insert errors for %s: %s", result.channel, errors)
        else:
            logger.debug(
                "Audit logged decision=%s channel=%s status=%s",
                decision.decision_id,
                result.channel,
                result.status,
            )
