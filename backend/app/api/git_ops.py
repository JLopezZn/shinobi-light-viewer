import asyncio
import os
import subprocess
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ..api.admin import require_admin_token
from ..services import git_manager

router = APIRouter()

_op_lock = threading.Lock()
_pending_operation: Optional[str] = None


def _get_current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(git_manager.REPO_ROOT),
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _acquire(op: str) -> bool:
    global _pending_operation
    acquired = _op_lock.acquire(blocking=False)
    if acquired:
        _pending_operation = op
    return acquired


def _release() -> None:
    global _pending_operation
    _pending_operation = None
    _op_lock.release()


async def _exit_42_after_response() -> None:
    await asyncio.sleep(0.5)
    os._exit(42)


# ── GET /status ────────────────────────────────────────────────────────────────

@router.get("/status", dependencies=[Depends(require_admin_token)])
def git_status() -> dict:
    return {
        "branch": _get_current_branch(),
        "pending_operation": _pending_operation,
    }


# ── POST /update ───────────────────────────────────────────────────────────────

@router.post("/update", dependencies=[Depends(require_admin_token)])
async def git_update() -> dict:
    if not _acquire("update"):
        raise HTTPException(
            status_code=409,
            detail="Una operación está en curso. Intente de nuevo en unos segundos.",
        )
    try:
        result = git_manager.git_pull()
    finally:
        _release()

    if result["status"] == "success":
        asyncio.create_task(_exit_42_after_response())

    return result


# ── GET /branches ──────────────────────────────────────────────────────────────

@router.get("/branches", dependencies=[Depends(require_admin_token)])
def git_branches() -> dict:
    if not _acquire("update"):
        raise HTTPException(
            status_code=409,
            detail="Una operación está en curso. Intente de nuevo en unos segundos.",
        )
    try:
        result = git_manager.list_branches()
    finally:
        _release()
    return result


# ── POST /switch ───────────────────────────────────────────────────────────────

class SwitchRequest(BaseModel):
    branch: str

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        if not git_manager.is_safe_branch_name(v):
            raise ValueError(
                "Branch name must be ≤200 chars and contain only word characters, hyphens, dots, and slashes."
            )
        return v


@router.post("/switch", dependencies=[Depends(require_admin_token)])
async def git_switch(body: SwitchRequest) -> dict:
    if not _acquire("switch"):
        raise HTTPException(
            status_code=409,
            detail="Una operación está en curso. Intente de nuevo en unos segundos.",
        )
    try:
        result = git_manager.checkout_branch(body.branch)
    finally:
        _release()

    if result["status"] == "success":
        asyncio.create_task(_exit_42_after_response())

    return result
