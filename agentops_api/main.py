"""AgentOps Control Center API entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentops_api.config import CORS_ORIGINS  # noqa: E402
from agentops_api.db import init_db  # noqa: E402
from agentops_api.routes import router  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AgentOps Control Center",
    version="0.1.0",
    description="Observability and administration plane for the journey-generation agents.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/api/meta")
def meta() -> dict[str, str]:
    return {
        "name": "AgentOps Control Center",
        "version": "0.1.0",
        "product": "HDFC Journey Generation Platform",
    }


def run() -> None:
    import uvicorn

    uvicorn.run("agentops_api.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    run()
