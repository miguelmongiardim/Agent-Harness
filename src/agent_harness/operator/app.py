from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException

from agent_harness import __version__
from agent_harness.schemas import OperatorHealthResponse

OPERATOR_TOKEN_HEADER = "X-Agent-Harness-Operator-Token"


def create_operator_app(project_root: Path, token: str, profile: str = "default") -> FastAPI:
    app = FastAPI(title="Agent Harness Operator", version=__version__)
    app.state.project_root = project_root.resolve()
    app.state.operator_token = token
    app.state.profile = profile

    def require_operator_token(
        provided_token: str | None = Header(default=None, alias=OPERATOR_TOKEN_HEADER),
    ) -> None:
        if provided_token is None or not secrets.compare_digest(provided_token, token):
            raise HTTPException(
                status_code=401,
                detail="missing or invalid operator token",
            )

    @app.get("/health")
    def health() -> dict[str, object]:
        return OperatorHealthResponse(
            agent_harness_version=__version__,
        ).model_dump(mode="json")

    @app.api_route(
        "/api/v1/{path:path}",
        methods=["DELETE", "GET", "PATCH", "POST", "PUT"],
    )
    def api_not_implemented(
        path: str,
        _authorized: None = Depends(require_operator_token),
    ) -> None:
        del path, _authorized
        raise HTTPException(status_code=404, detail="operator API route not implemented")

    return app
