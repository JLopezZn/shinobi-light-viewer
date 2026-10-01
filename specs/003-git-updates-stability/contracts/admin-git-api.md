# Contract: Admin Git API (Main App)

**Server**: FastAPI app on `http://localhost:$PORT` (default 8090)
**Auth**: All endpoints require `X-Admin-Token: <ADMIN_TOKEN>` header (existing pattern)
**Router prefix**: `/api/admin/git`

---

## GET /api/admin/git/status

Returns the current branch and last update result. Useful for UI initialization.

**Response 200**:
```json
{
  "branch": "main",
  "pending_operation": null
}
```

`pending_operation` is `null`, `"update"`, or `"switch"`.

---

## POST /api/admin/git/update

Pulls the latest changes from the current branch. On success, exits the app process with code 42 (supervisor restarts automatically). The HTTP response is sent **before** the exit — the client receives the result, then the app restarts.

**Request body**: none

**Response 200 — success** (sent before restart):
```json
{
  "status": "success",
  "summary": "2 files changed, 15 insertions(+), 3 deletions(-)"
}
```

**Response 200 — up to date**:
```json
{
  "status": "up_to_date",
  "summary": "Already up to date."
}
```
*(No restart triggered when already up to date.)*

**Response 200 — failed**:
```json
{
  "status": "failed",
  "summary": "CONFLICT (content): Merge conflict in backend/app/main.py"
}
```
*(Hard-reset performed; running version unchanged; no restart.)*

**Response 409** — another operation in progress:
```json
{ "detail": "Una operación está en curso. Intente de nuevo en unos segundos." }
```

**Response 401** — missing/invalid token.

---

## GET /api/admin/git/branches

Fetches remote refs, then returns all known branches.

**Response 200**:
```json
{
  "branches": [
    { "name": "main",                       "is_current": false, "is_local": true,  "is_remote": true  },
    { "name": "003-git-updates-stability",  "is_current": true,  "is_local": true,  "is_remote": true  },
    { "name": "feature/experimental",       "is_current": false, "is_local": false, "is_remote": true  }
  ]
}
```

**Response 200 with fetch warning** (if `git fetch` failed but local list available):
```json
{
  "branches": [ ... ],
  "warning": "No se pudo conectar al remoto. Mostrando ramas locales conocidas."
}
```

**Response 409** — operation in progress (same as above).
**Response 401** — missing/invalid token.

---

## POST /api/admin/git/switch

Checks out the requested branch. On success, exits with code 42 (supervisor restarts). Response sent before exit.

**Request body**:
```json
{ "branch": "main" }
```

**Response 200 — success** (sent before restart):
```json
{ "status": "success", "branch": "main" }
```

**Response 200 — already on branch**:
```json
{ "status": "already_current", "branch": "003-git-updates-stability" }
```
*(No restart triggered.)*

**Response 200 — failed** (checkout error; previous branch restored):
```json
{
  "status": "failed",
  "branch": "003-git-updates-stability",
  "summary": "error: pathspec 'nonexistent' did not match any file(s) known to git"
}
```

**Response 409** — operation in progress.
**Response 422** — invalid/missing `branch` field.
**Response 401** — missing/invalid token.
