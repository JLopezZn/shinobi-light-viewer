# Quickstart Validation Guide: Shinobi Pod Manager

**Feature**: `002-shinobi-pod-manager` | **Date**: 2026-09-27

## Prerequisites

- Docker Desktop (Windows) or Docker Engine (Linux) installed and running
- A Docker container named per `SHINOBI_CONTAINER` env var (default: `shinobi`) exists
- `.env` configured with `ADMIN_TOKEN` and `SHINOBI_CONTAINER`
- Application running via `start.bat` (Windows) or `start.sh` (Linux)

## Environment Setup

Add to `backend/.env`:
```
SHINOBI_CONTAINER=shinobi
ADMIN_TOKEN=my-secret-token
```

---

## Scenario 1: Safe startup (start.bat / start.sh)

**Goal**: Verify the server waits for the Shinobi container before starting.

1. Stop the Shinobi container manually: `docker stop shinobi`
2. Run `start.bat` (Windows) or `./start.sh` (Linux)
3. **Expected**: Script prints `[docker] Waiting for Shinobi container...` and retries every 5 seconds
4. Start the container from another terminal: `docker start shinobi`
5. **Expected**: Script detects `running` state and proceeds to launch uvicorn
6. Server URL appears: `[start] Shinobi Light Viewer → http://localhost:8090`

**Timeout scenario**:
1. Keep container stopped and run the startup script
2. Wait 120 seconds
3. **Expected**: Script prints `[docker] Timeout: Shinobi container did not start within 120s` and exits with code 1, uvicorn is NOT launched

---

## Scenario 2: Admin token gate

**Goal**: Verify Docker endpoints are protected.

```bash
# Without token — expect 401
curl -X GET http://localhost:8090/api/admin/docker/status

# With correct token — expect 200
curl -X GET http://localhost:8090/api/admin/docker/status \
  -H "X-Admin-Token: my-secret-token"
```

**Expected response** (container running):
```json
{"status": "running", "container": "shinobi"}
```

**Expected response** (container stopped):
```json
{"status": "stopped", "container": "shinobi"}
```

---

## Scenario 3: Stop container from UI

**Goal**: Verify stop operation and UI state update.

1. Ensure Shinobi container is running: `docker ps | grep shinobi`
2. Open `http://localhost:8090` in browser
3. Navigate to Admin section, enter token when prompted
4. Observe status badge shows **"En ejecución"**
5. Click **"Detener Shinobi"**
6. **Expected**: Button becomes disabled, status badge transitions to **"Detenido"** within 30 seconds
7. Verify: `docker ps | grep shinobi` shows no running container

---

## Scenario 4: Start container from UI

**Goal**: Verify start operation.

1. Ensure container is stopped (continue from Scenario 3, or run `docker stop shinobi`)
2. In Admin section, click **"Iniciar Shinobi"**
3. **Expected**: Button disabled, status transitions to **"En ejecución"** within 30 seconds
4. Verify: `docker ps | grep shinobi` shows running container

---

## Scenario 5: Restart container from UI

**Goal**: Verify restart is atomic stop+start.

1. Ensure container is running
2. Click **"Reiniciar Shinobi"**
3. **Expected**: Status briefly shows **"Detenido"** (or a "reiniciando..." indicator), then returns to **"En ejecución"**
4. Verify container uptime reset: `docker inspect shinobi --format='{{.State.StartedAt}}'` shows recent timestamp

---

## Scenario 6: Error handling — Docker unavailable

**Goal**: Verify graceful degradation when Docker is not running.

1. Stop Docker daemon (or Docker Desktop)
2. In Admin section, observe status polling result
3. **Expected**: Status badge shows **"Desconocido"** with an informational message
4. Try clicking "Iniciar Shinobi"
5. **Expected**: Error message appears, app does not crash or hang

---

## Scenario 7: Already-stopped / already-running idempotency

```bash
# Container already stopped — stop again
docker stop shinobi 2>/dev/null; true
curl -X POST http://localhost:8090/api/admin/docker/stop \
  -H "X-Admin-Token: my-secret-token"
# Expected: {"status": "stopped", "container": "shinobi", "message": "Container was already stopped"}

# Container already running — start again
docker start shinobi
curl -X POST http://localhost:8090/api/admin/docker/start \
  -H "X-Admin-Token: my-secret-token"
# Expected: {"status": "running", "container": "shinobi", "message": "Container was already running"}
```

---

## API Reference

See [`contracts/admin-docker-api.md`](contracts/admin-docker-api.md) for full endpoint specs.

## Data Model Reference

See [`data-model.md`](data-model.md) for status values and configuration variables.
