# Research: Shinobi Light Viewer (rev2)

**Date**: 2026-09-25 | **Plan**: [plan.md](plan.md)

## Decision 1: Sincronización multi-`<video>`

**Decision**: Un video como master; los demás se corrigen con `requestAnimationFrame` mientras están reproduciéndose. Tolerancia de 50 ms antes de forzar corrección.

**Rationale**: `rAF` solo corre mientras el video está en play — no acumula drift como `setInterval`. La corrección es lightweight (solo `currentTime` assignment cuando excede tolerancia). Sin librerías externas.

**Patrón clave**:
```js
const MASTER = videos[0];
const TOLERANCE = 0.05; // seconds

function syncLoop() {
  const t = MASTER.currentTime;
  for (let i = 1; i < videos.length; i++) {
    if (Math.abs(videos[i].currentTime - t) > TOLERANCE) {
      videos[i].currentTime = t;
    }
  }
  if (!MASTER.paused) requestAnimationFrame(syncLoop);
}

function play()   { videos.forEach(v => { v.currentTime = MASTER.currentTime; v.play(); }); requestAnimationFrame(syncLoop); }
function pause()  { videos.forEach(v => v.pause()); }
function seek(vt) { videos.forEach(v => { v.currentTime = vt; }); }
```

**Alternativas consideradas**: `setInterval` — descartado por drift acumulativo. MediaSource Extensions — demasiado complejo para v1, requeriría server-sent chunks.

---

## Decision 2: Navegación entre chunks (chunk boundary)

**Decision**: Cada celda mantiene un array de chunks ordenado por `startTime`. Al buscar un `virtualTime`, se hace `find()` para localizar el chunk correcto y se calcula el offset dentro de él.

**Patrón clave**:
```js
// chunks = [{ src, startTime, endTime }, ...]  — startTime/endTime en ms epoch

function seekCamera(videoEl, chunks, virtualTimeMs) {
  const chunk = chunks.find(c => virtualTimeMs >= c.startTime && virtualTimeMs < c.endTime);
  if (!chunk) return;
  videoEl.src = chunk.src;
  videoEl.addEventListener('loadedmetadata', () => {
    videoEl.currentTime = (virtualTimeMs - chunk.startTime) / 1000;
  }, { once: true });
}

function loadNextChunk(videoEl, chunks, currentChunk) {
  const next = chunks[chunks.indexOf(currentChunk) + 1];
  if (next) { videoEl.src = next.src; videoEl.play(); }
}

videoEl.addEventListener('ended', () => loadNextChunk(videoEl, chunks, activeChunk));
```

**Alternativas consideradas**: MSE (Media Source Extensions) para playlist continua — descartado por complejidad en v1. `<source>` múltiples en un `<video>` — no permite seek entre chunks correctamente.

---

## Decision 3: HTTP Range Request streaming (FastAPI)

**Decision**: Endpoint `GET /api/video/{chunk_id}` que lee el archivo con `open()` + `seek()` y responde `206 Partial Content` para requests de rango, `200` para requests completos. Siempre incluye `Accept-Ranges: bytes`.

**Rationale**: El browser necesita `206` (no `200`) para habilitar seeking dentro del archivo. Leer con `seek()` es esencial para archivos de varios GB — nunca cargar el archivo completo en memoria.

**Patrón clave**:
```python
@app.get("/api/video/{chunk_id}")
async def stream_video(chunk_id: int, request: Request):
    path = resolve_chunk_path(chunk_id)   # lookup en DB
    size = os.path.getsize(path)
    range_header = request.headers.get("range")
    start, end = 0, size - 1
    status = 200
    if range_header:
        parts = range_header.strip("bytes=").split("-")
        start = int(parts[0]) if parts[0] else 0
        end   = int(parts[1]) if parts[1] else size - 1
        status = 206
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        "Content-Range": f"bytes {start}-{end}/{size}",
    }
    return StreamingResponse(
        _stream_file(path, start, end),
        status_code=status, media_type="video/mp4", headers=headers
    )
```

**Alternativas consideradas**: `FileResponse` de FastAPI — no soporta Range Requests correctamente en todas las versiones. StaticFiles mount — imposible para archivos en rutas arbitrarias del HDD externo.

---

## Decision 4: Scrubber dual handle (vanilla JS)

**Decision**: Dos `<div>` draggables posicionados con `left: X%` sobre una barra. El constraint (no cruzarse) se aplica en `mousemove` antes de actualizar `style.left`.

**Patrón clave**:
```js
let dragging = null;
document.querySelectorAll(".handle").forEach(h =>
  h.addEventListener("mousedown", e => { dragging = h; e.preventDefault(); })
);
document.addEventListener("mousemove", e => {
  if (!dragging) return;
  const { left, width } = document.querySelector(".scrubber").getBoundingClientRect();
  let pct = Math.max(0, Math.min(1, (e.clientX - left) / width));
  const otherId = dragging.id === "h-start" ? "h-end" : "h-start";
  const otherPct = parseFloat(document.getElementById(otherId).style.left) / 100;
  pct = dragging.id === "h-start"
    ? Math.min(pct, otherPct - 0.01)
    : Math.max(pct, otherPct + 0.01);
  dragging.style.left = (pct * 100) + "%";
  onScrubChange();  // callback para actualizar virtualTime en el grid
});
document.addEventListener("mouseup", () => { dragging = null; });
```

**Alternativas consideradas**: `<input type="range">` nativo — no soporta dos handles en HTML estándar. Librerías externas (noUiSlider, etc.) — descartadas para mantener cero dependencias en frontend.

---

## Decision 5: FFmpeg export (sin cambios respecto a v1)

**Decision**: Concat demuxer + `-c copy` para merge lossless. Progreso via `-progress pipe:1`. Un job a la vez. N archivos paralelos para N cámaras.

**Cambio respecto a v1**: El export ahora genera N archivos simultáneamente (uno por cámara activa), pero cada uno es un proceso FFmpeg independiente. Los N procesos corren en paralelo como `asyncio` tasks bajo el mismo job. El progreso se reporta como el mínimo de avance entre todos los procesos (el más lento marca el ritmo).

**Rationale**: Exportar en paralelo minimiza el tiempo total. El "single job" constraint aplica a nivel de sesión de exportación (no se pueden lanzar dos exportaciones mientras una está activa), no a nivel de proceso FFmpeg interno.
