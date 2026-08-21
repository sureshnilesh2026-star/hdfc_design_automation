# hdfc_design_automation

AI agentic journey-generation platform: contracts, agents, and the **AgentOps Control Center**.

## Agents

| Agent | Status |
|---|---|
| Intent Recognition | Operational |
| Platform Capability | Operational |
| Knowledge Repository | Operational (filesystem index) |
| Journey Planner | Operational |
| Component Intelligence, Response Orchestrator, JSON Compiler, Validation, Output, HITL, Learning | In development |

## AgentOps dashboard

See [`frontend/README.md`](frontend/README.md).

```bash
pip install -e ".[agentops,dev]"
python -m agentops_api.main
cd frontend && npm install && npm run dev
```
