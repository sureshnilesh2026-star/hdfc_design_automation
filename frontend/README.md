# AgentOps Control Center

Visual control plane for the HDFC journey-generation agents. The dashboard lives in `frontend/` and talks to the AgentOps API in `agentops_api/`. Existing agents are not modified.

## What you get

- Login, session tokens, and role-based access (Super Admin, Approver, Viewer)
- Landing dashboard with system health and the full workflow graph
- Four operational agents wired to real Python implementations
- Future agents shown as **In development** with no invented metrics
- Live execution traces, retry/replay, incidents, knowledge documents, audit logs

## Run locally

From the repository root:

```bash
pip install -e ".[agentops,dev]"
python -m agentops_api.main
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Seed accounts

| User ID   | Role         | Default password     |
|-----------|--------------|----------------------|
| admin     | Super Admin  | `ChangeMeAdmin!1`    |
| approver  | Approver     | `ChangeMeApprover!1` |
| viewer    | Viewer       | `ChangeMeViewer!1`   |

Passwords are stored as PBKDF2 hashes. Change them from Administration after first login.

### Runtime honesty

- Intent Recognition and Journey Planner use OpenAI when `OPENAI_API_KEY` is set.
- Without a key they run the existing deterministic stand-ins. The UI labels this as `deterministic-fallback`.
- Platform Capability and Knowledge Repository never call an LLM.
- Future pipeline stages stay `In development` until they are registered in `agentops_api/registry.py`.

## Adding a new agent

1. Implement the agent.
2. Add an `AgentContract` in `agentops_api/registry.py` (`lifecycle: "operational"`).
3. Expose health, input/output, and execution events through the existing workflow runner.
4. The dashboard picks the agent up without a layout redesign.
