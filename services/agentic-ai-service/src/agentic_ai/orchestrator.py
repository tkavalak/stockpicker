"""AgentOrchestrator — run LangGraph workflow with timeout and idempotency."""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any

from agentic_ai.graph import get_compiled_graph
from agentic_ai.idempotency import AgentStateStore
from agentic_ai.models import (
    ACTION_ALERT,
    ACTION_ESCALATE,
    OUTCOME_COMPLETED,
    OUTCOME_DUPLICATE,
    OUTCOME_TIMEOUT,
    AlertDecision,
    TriggerEvent,
    alert_decision_from_state,
    ignore_decision,
)
from agentic_ai.state import WorkflowState

logger = logging.getLogger(__name__)

WORKFLOW_TIMEOUT_SEC = float(os.environ.get("WORKFLOW_TIMEOUT_SEC", "30"))


@dataclass(frozen=True)
class WorkflowRunResult:
    decision: AlertDecision | None
    outcome: str
    latency_ms: int
    published: bool = False


class AgentOrchestrator:
    def __init__(
        self,
        *,
        state_store: AgentStateStore | None = None,
        workflow_timeout_sec: float = WORKFLOW_TIMEOUT_SEC,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._state_store = state_store or AgentStateStore()
        self._graph = get_compiled_graph()
        self._timeout_sec = workflow_timeout_sec
        self._executor = executor or ThreadPoolExecutor(
            max_workers=int(os.environ.get("WORKFLOW_EXECUTOR_THREADS", "8"))
        )
        self._workflows_started = 0
        self._workflows_completed = 0
        self._workflows_timed_out = 0
        self._workflows_duplicate = 0

    @property
    def metrics(self) -> dict[str, int]:
        return {
            "workflows_started": self._workflows_started,
            "workflows_completed": self._workflows_completed,
            "workflows_timed_out": self._workflows_timed_out,
            "workflows_duplicate": self._workflows_duplicate,
        }

    def run(self, trigger: TriggerEvent) -> WorkflowRunResult:
        self._workflows_started += 1
        start = time.monotonic()

        prior = self._state_store.get_prior_decision(trigger.event_id)
        if prior is not None:
            self._workflows_duplicate += 1
            latency = int((time.monotonic() - start) * 1000)
            logger.info(
                "Skipping duplicate workflow event_id=%s (prior outcome cached)",
                trigger.event_id,
            )
            return WorkflowRunResult(
                decision=prior,
                outcome=OUTCOME_DUPLICATE,
                latency_ms=latency,
            )

        initial: WorkflowState = {"trigger": trigger.to_dict(), "abort": False}

        try:
            final_state = self._executor.submit(
                self._invoke_graph, initial
            ).result(timeout=self._timeout_sec)
        except FuturesTimeoutError:
            self._workflows_timed_out += 1
            latency = int((time.monotonic() - start) * 1000)
            logger.warning(
                "TIMEOUT workflow event_id=%s exceeded %.0fs",
                trigger.event_id,
                self._timeout_sec,
            )
            self._state_store.save_decision(
                event_id=trigger.event_id,
                trigger=trigger.to_dict(),
                decision=ignore_decision(trigger, reason="workflow timeout"),
                outcome=OUTCOME_TIMEOUT,
                latency_ms=latency,
            )
            return WorkflowRunResult(
                decision=None,
                outcome=OUTCOME_TIMEOUT,
                latency_ms=latency,
            )

        latency = int((time.monotonic() - start) * 1000)
        decision = self._decision_from_graph(final_state, trigger)
        self._state_store.save_decision(
            event_id=trigger.event_id,
            trigger=trigger.to_dict(),
            decision=decision,
            outcome=OUTCOME_COMPLETED,
            latency_ms=latency,
        )
        self._workflows_completed += 1
        return WorkflowRunResult(
            decision=decision,
            outcome=OUTCOME_COMPLETED,
            latency_ms=latency,
        )

    def _invoke_graph(self, initial: WorkflowState) -> dict[str, Any]:
        return self._graph.invoke(initial)

    def _decision_from_graph(
        self, final_state: dict[str, Any], trigger: TriggerEvent
    ) -> AlertDecision:
        final = final_state.get("final_decision")
        if isinstance(final, dict):
            return alert_decision_from_state(final, trigger)
        return ignore_decision(trigger, reason="workflow produced no final_decision")

    def should_publish(self, decision: AlertDecision | None) -> bool:
        if decision is None:
            return False
        return decision.action in (ACTION_ALERT, ACTION_ESCALATE)
