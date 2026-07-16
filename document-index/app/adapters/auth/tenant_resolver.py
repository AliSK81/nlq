from __future__ import annotations

from fastapi import Request


def resolve_tenant_id(request: Request) -> str:
    """Derive tenant from auth headers. MVP: always default."""
    auth_token = request.headers.get("x-auth-token")
    if auth_token:
        return auth_token.split(":")[0] if ":" in auth_token else "default"
    return "default"
