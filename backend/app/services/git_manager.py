import re
import subprocess
from pathlib import Path
from typing import Optional


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Cannot determine git repo root: {result.stderr.strip()}")
    return Path(result.stdout.strip())


REPO_ROOT: Path = _repo_root()

assert (REPO_ROOT / ".git").exists(), f"REPO_ROOT {REPO_ROOT} has no .git directory"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True)


def git_pull() -> dict:
    """Pull latest changes from the current branch.

    Returns dict with keys: status (success|up_to_date|failed), summary (str).
    On conflict/error, hard-resets to HEAD before returning.
    """
    branch_result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
    pull_args = ["git", "pull", "origin", current_branch] if current_branch else ["git", "pull"]
    result = _run(pull_args)
    if result.returncode != 0:
        _run(["git", "reset", "--hard", "HEAD"])
        return {"status": "failed", "summary": (result.stderr or result.stdout).strip()}
    output = result.stdout.strip()
    if "Already up to date" in output:
        return {"status": "up_to_date", "summary": output}
    return {"status": "success", "summary": output}


def list_branches() -> dict:
    """Fetch remote refs then list all branches.

    Returns dict with keys:
      branches: list of {name, is_current, is_local, is_remote}
      warning: str|None — set if git fetch failed
    """
    fetch = _run(["git", "fetch", "--prune", "--quiet"])
    warning = (fetch.stderr or fetch.stdout).strip() if fetch.returncode != 0 else None

    result = _run(["git", "branch", "-a"])
    if result.returncode != 0:
        return {"branches": [], "warning": result.stderr.strip() or "Failed to list branches"}

    local_names: set[str] = set()
    remote_names: set[str] = set()
    current: Optional[str] = None

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or "HEAD ->" in stripped:
            continue
        is_cur = stripped.startswith("* ")
        name_raw = stripped.lstrip("* ")
        if name_raw.startswith("remotes/origin/"):
            name = name_raw[len("remotes/origin/"):]
            remote_names.add(name)
        else:
            name = name_raw
            local_names.add(name)
            if is_cur:
                current = name

    all_names = local_names | remote_names
    branches = [
        {
            "name": n,
            "is_current": n == current,
            "is_local": n in local_names,
            "is_remote": n in remote_names,
        }
        for n in sorted(all_names)
    ]
    return {"branches": branches, "warning": warning}


def checkout_branch(branch: str) -> dict:
    """Check out the given branch.

    Returns dict with keys: status (success|already_current|failed), branch (str), summary (str|None).
    On failure, reverts to the previous branch.
    """
    cur = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    current = cur.stdout.strip() if cur.returncode == 0 else "HEAD"

    if branch == current:
        return {"status": "already_current", "branch": branch, "summary": None}

    result = _run(["git", "checkout", branch])
    if result.returncode != 0:
        _run(["git", "checkout", current])
        return {
            "status": "failed",
            "branch": current,
            "summary": (result.stderr or result.stdout).strip(),
        }
    return {"status": "success", "branch": branch, "summary": None}


_SAFE_BRANCH = re.compile(r"^[\w\-./]+$")


def is_safe_branch_name(name: str) -> bool:
    return bool(_SAFE_BRANCH.match(name)) and len(name) <= 200
