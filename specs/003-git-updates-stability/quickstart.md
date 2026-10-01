# Quickstart Validation Guide: Git Updates, Branch Switcher & App Stability

**Date**: 2026-10-01 | **Feature**: 003-git-updates-stability

This guide describes how to verify the three user stories end-to-end once implementation is complete.

## Prerequisites

- The feature branch `003-git-updates-stability` is checked out and dependencies installed
- `backend/.env` is configured with valid `FOOTAGE_DIR`, `DB_PATH`, `CACHE_DIR`, `ADMIN_TOKEN`
- A git remote is configured and accessible
- At least one other local or remote branch exists besides the current one

---

## S1: Auto-Restart After Crash (P1)

**Goal**: Verify the app recovers automatically and enters crash-capped state after repeated failures.

### Test 1.1 — Single crash recovery

1. Start the app: `./start.sh` (or `start.bat`)
2. Open the main UI at `http://localhost:$PORT` and confirm it loads
3. Open the status page at `http://localhost:$STATUS_PORT` — confirm state shows `running`
4. Kill the uvicorn process: `kill -9 $(lsof -ti:$PORT)` (Linux/macOS) or `taskkill /F /IM uvicorn.exe` (Windows)
5. Wait up to 10 seconds
6. **Expected**: Main UI at `$PORT` becomes available again; status page shows `running`; crash count = 1

### Test 1.2 — Crash-cap and manual recovery

1. With the app running, simulate 5 rapid crashes within 2 minutes (repeat the kill from 1.1 five times)
2. After the 5th crash, wait 5 seconds
3. **Expected**: Main UI at `$PORT` is unreachable; status page at `$STATUS_PORT` is still accessible and shows state = `crash_capped`
4. On the status page, click "Reiniciar App"
5. **Expected**: Status page shows `starting` then `running`; main UI becomes accessible; crash count resets to 0

---

## S2: Buscar Actualizaciones Button (P2)

**Goal**: Verify update pull works, shows result, and triggers restart.

### Test 2.1 — Up to date

1. With the app running and no new commits on the remote, click "Buscar Actualizaciones" in the UI
2. **Expected**: Button shows loading state; result message says "Already up to date." (or equivalent); no restart occurs

### Test 2.2 — Successful update

1. Push a new commit to the remote on the current branch (can be a whitespace change in any file)
2. Click "Buscar Actualizaciones"
3. **Expected**: Update pull succeeds; UI shows success message with file-change summary; app restarts automatically within 30 seconds; after restart, `git log -1` on the server shows the new commit

### Test 2.3 — Conflict / error handling

1. Manually create a local change that conflicts with the remote (edit a file without committing)
2. Push a conflicting commit to the remote
3. Click "Buscar Actualizaciones"
4. **Expected**: Error message shown in UI with conflict detail; `git status` shows clean working tree (hard-reset performed); running version is unchanged; no restart

### Test 2.4 — Mutual exclusion

1. Click "Buscar Actualizaciones" to start an update
2. Immediately try to open the branch selector before the update completes
3. **Expected**: Branch selector (or switch action) returns a "operación en curso" message; only one operation proceeds

---

## S3: Branch Switcher (P3)

**Goal**: Verify branch switching works, shows all branches, and restarts into the new branch.

### Test 3.1 — Branch list shows remote branches

1. Create a new branch on the remote that does not exist locally: `git push origin HEAD:refs/heads/test-remote-branch`
2. Open the branch selector dropdown in the UI
3. **Expected**: Loading indicator shown during fetch; `test-remote-branch` appears in the list with `is_remote: true, is_local: false`

### Test 3.2 — Successful branch switch

1. In the branch selector, choose a branch different from the current one and confirm
2. **Expected**: App restarts automatically; after restart, `git rev-parse --abbrev-ref HEAD` returns the selected branch name; UI shows the new branch name

### Test 3.3 — Already on selected branch

1. In the branch selector, choose the currently active branch
2. **Expected**: UI shows "ya estás en esta rama" (or equivalent); no restart occurs

### Test 3.4 — Switch failure / revert

1. Attempt to switch to a branch name that does not exist (forge a POST to `/api/admin/git/switch` with `{"branch": "nonexistent"}`)
2. **Expected**: Error response with git error detail; `git rev-parse --abbrev-ref HEAD` still returns the original branch; app has not restarted

---

## Verification Checklist

| Scenario | Pass condition |
|----------|---------------|
| S1.1 | App recovers within 10 s after single kill |
| S1.2 | Status page accessible when main app is crash-capped; manual restart works |
| S2.1 | "Already up to date" shown; no restart |
| S2.2 | Update applied; app restarts; new commit visible |
| S2.3 | Error shown; repo left clean; no restart |
| S2.4 | Concurrent operation blocked with clear message |
| S3.1 | Remote-only branch visible in selector after fetch |
| S3.2 | Branch switched; app restarted on new branch |
| S3.3 | No restart on selecting current branch |
| S3.4 | Switch failure reverts; original branch retained |

---

## API References

See [contracts/admin-git-api.md](contracts/admin-git-api.md) for endpoint request/response shapes.
See [contracts/status-server-api.md](contracts/status-server-api.md) for status server endpoint shapes.
See [data-model.md](data-model.md) for entity definitions and crash-cap algorithm.
