# Implementation Plan: Shinobi Light Viewer

**Branch**: `001-shinobi-viewer` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-shinobi-viewer/spec.md`

## Summary

Reproductor web local multi-cámara que indexa footage de Shinobi desde un HDD externo, muestra hasta 9 cámaras sincronizadas en un grid con reproducción timelapse client-side (via `playbackRate`), permite delimitar un sub-rango con un scrubber dual de dos punteros, y exporta los clips seleccionados como N archivos `.mp4` lossless (uno por cámara activa). El backend es FastAPI + SQLite; el frontend es Vanilla JS/HTML5 puro.

## Technical Context

**Language/Version**: Python 3.10+ (sistema objetivo: Windows con Python en PATH)

**Primary Dependencies**: FastAPI, Uvicorn, SQLite (stdlib), FFmpeg (subprocess), Vanilla JS / HTML5

**Storage**: SQLite en SSD local (`shinobi_index.db`)

**Testing**: pytest, pytest-asyncio, httpx

**Target Platform**: Windows local, acceso LAN vía browser de escritorio

**Project Type**: Web service (FastAPI backend + frontend estático servido por el mismo proceso)

**Performance Goals**:
- Grid de hasta 9 cámaras carga en < 3 segundos (SC-001)
- Seek del scrubber actualiza todas las celdas en < 500 ms (SC-002)
- Exportación de 1 hora × 4 cámaras disponible en < 5 minutos (SC-003)

**Constraints**:
- Zero writes al HDD externo — todo en SSD local
- mtime guard: omitir archivos modificados en los últimos 60 segundos
- Máximo 1 job de exportación activo simultáneamente
- Máximo 9 cámaras en el grid (3×3)
- Timelapse es client-side (`playbackRate`); FFmpeg solo para exportar

**Scale/Scope**: Operador único, LAN local, v1 sin auth

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requisito | Status |
|------|-----------|--------|
| Zero HDD writes | App nunca escribe en el directorio de footage (FR-019) | PASS — archivos HDD son solo leídos vía endpoint de streaming |
| mtime race guard | Indexer omite archivos con mtime < 60 s (FR-002) | PASS — verificado en cada ciclo de scan |
| Decoupled metadata | SQLite y cache en SSD local (FR-003) | PASS — DB_PATH y CACHE_DIR en SSD |
| Timelapse client-side | Sin generación de archivo timelapse en servidor para visualización | PASS — `playbackRate` en browser; FFmpeg solo en export |

Todos los gates pasan. Procediendo a Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-shinobi-viewer/
├── plan.md              # Este archivo
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py              # FastAPI app factory, startup/shutdown
│   ├── config.py            # Settings (FOOTAGE_DIR, DB_PATH, CACHE_DIR, PORT, SCAN_INTERVAL)
│   ├── database.py          # SQLite init, schema, get_conn()
│   ├── indexer.py           # Scan loop: startup + 60 s periódico, mtime guard, availability
│   ├── models.py            # Pydantic models: MonitorOut, VideoChunkOut, JobStatusOut, etc.
│   ├── api/
│   │   ├── monitors.py      # GET /api/monitors, GET /api/indexer/status
│   │   ├── chunks.py        # GET /api/monitors/{id}/chunks
│   │   ├── video.py         # GET /api/video/{chunk_id}  ← NUEVO: Range Request streaming
│   │   └── jobs.py          # POST /api/jobs/export, GET/DELETE /api/jobs/current, GET /api/downloads/{token}
│   └── services/
│       ├── ffmpeg.py        # concat_cmd, compute_export_size
│       └── job_manager.py   # Single-job lock, tokens, disk check, cancel
└── tests/
    ├── unit/
    ├── integration/
    └── contract/

frontend/
├── index.html               # Layout: sidebar + grid + scrubber + controles
├── app.js                   # GridPlayer, CellPlayer, Scrubber, ExportManager
└── style.css                # Grid layout, celdas, scrubber dual handle, spinner
```

**Structure Decision**: Web application con backend y frontend en el mismo proceso FastAPI. El nuevo endpoint clave es `GET /api/video/{chunk_id}` que sirve archivos del HDD con soporte Range Requests.

## Complexity Tracking

> No hay violaciones de constitución. Sección no requerida.
