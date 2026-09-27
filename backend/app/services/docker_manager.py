import subprocess
from dataclasses import dataclass

# Maps raw Docker state strings to the three normalized values exposed by the API.
_STATUS_MAP: dict[str, str] = {
    "running": "running",
    "restarting": "running",
    "created": "stopped",
    "exited": "stopped",
    "paused": "stopped",
    "dead": "stopped",
    "removing": "stopped",
}


@dataclass
class ContainerStatus:
    status: str  # "running" | "stopped" | "unknown"
    container: str
    message: str | None = None


def get_container_status(container: str) -> ContainerStatus:
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Status}}", container],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return ContainerStatus(
                status="unknown",
                container=container,
                message="Container not found or Docker is unavailable",
            )
        raw = result.stdout.strip().lower()
        normalized = _STATUS_MAP.get(raw, "unknown")
        return ContainerStatus(status=normalized, container=container)
    except FileNotFoundError:
        return ContainerStatus(
            status="unknown",
            container=container,
            message="Docker CLI not found on PATH",
        )


def start_container(container: str) -> ContainerStatus:
    current = get_container_status(container)
    if current.status == "running":
        return ContainerStatus(
            status="running", container=container, message="Container was already running"
        )
    result = subprocess.run(
        ["docker", "start", container],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return get_container_status(container)


def stop_container(container: str) -> ContainerStatus:
    current = get_container_status(container)
    if current.status == "stopped":
        return ContainerStatus(
            status="stopped", container=container, message="Container was already stopped"
        )
    result = subprocess.run(
        ["docker", "stop", container],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return get_container_status(container)


def restart_container(container: str) -> ContainerStatus:
    result = subprocess.run(
        ["docker", "stop", container],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    result = subprocess.run(
        ["docker", "start", container],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return get_container_status(container)
