# Agentic AI Service (WO-9)

LangGraph orchestration framework that consumes `TriggerEvent` messages from `trigger-events`, runs a five-agent validation workflow, and publishes `AlertDecision` messages to `alert-decisions` when approved.

Full five-agent pipeline (WO-9–12): Data / Signal / Context agents, DecisionAgent (Vertex + OpenAI), **ControlAgent** (confidence gate, cooldown, escalation).

## Components

| Component | Role |
|-----------|------|
| `WorkflowState` | TypedDict: `trigger`, `market_snapshot`, `signal_summary`, `context_summary`, `raw_decision`, `final_decision` |
| `build_workflow_graph` | LangGraph `StateGraph`: Data → Signal → Context → Decision → Control |
| `AgentOrchestrator` | Idempotency (Firestore `agent_state`), 30s timeout, metrics |
| `TriggerEventConsumer` | Pub/Sub pull on `agentic-ai-trigger-events`, `MAX_CONCURRENT_WORKFLOWS` (default 5) |
| `AlertDecisionPublisher` | Publishes only `ALERT` / `ESCALATE` to `alert-decisions` |
| `AgenticAIAdmin` | `GET /health`, `GET /metrics` |

## Graph topology

```
data_agent ──(abort?)──► END
     │
     └──► signal_agent → context_agent → decision_agent → control_agent → END
```

Stale triggers (> `STALE_TRIGGER_SEC`, default 10s) short-circuit at `data_agent`.

## Environment

| Variable | Default |
|----------|---------|
| `GCP_PROJECT_ID` | required |
| `PUBSUB_SUBSCRIPTION_AGENTIC_AI` | `agentic-ai-trigger-events` |
| `PUBSUB_TOPIC_ALERT_DECISIONS` | `alert-decisions` |
| `FIRESTORE_COLLECTION_AGENT_STATE` | `agent_state` |
| `MAX_CONCURRENT_WORKFLOWS` | `5` |
| `WORKFLOW_TIMEOUT_SEC` | `30` |
| `PORT` | `8080` |
| `POLYGON_API_KEY` | News API key (ContextAgent) |
| `NEWS_API_URL` | Default `https://api.polygon.io/v2/reference/news` |
| `STALE_TRIGGER_SEC` | `10` |
| `VERTEX_AI_LOCATION` | Same as `GCP_REGION` (default `us-central1`) |
| `VERTEX_AI_MODEL` | `gemini-1.5-flash` |
| `OPENAI_API_KEY` | Fallback LLM (Secret Manager on deploy) |
| `OPENAI_MODEL` | `gpt-4o` |
| `CONFIDENCE_THRESHOLD` | `0.70` (must be less than escalation) |
| `ESCALATION_THRESHOLD` | `0.90` |
| `COOLDOWN_WINDOW_MINUTES` | `10` per symbol + rule |

## Local run

```bash
./services/agentic-ai-service/run.sh
```

## Tests

```bash
cd services/agentic-ai-service
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
PYTHONPATH=src .venv/bin/pytest tests/ -q
```

## Deploy

```bash
export GCP_PROJECT_ID=stockadvisor-498000
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Requires WO-4 infrastructure and WO-7 rule engine publishing to `trigger-events`.
