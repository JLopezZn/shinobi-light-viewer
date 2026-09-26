# Feature Specification: Shinobi Light Viewer

**Feature Branch**: `001-shinobi-viewer`

**Created**: 2026-09-25

**Status**: Draft

**Input**: Reproductor local de footage de Shinobi: grid multi-cámara con reproducción timelapse sincronizada y selector de rango dual para exportar.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Armar el grid de cámaras (Priority: P1)

El operador abre el viewer, ve una lista de cámaras disponibles, activa las que quiere monitorear y el sistema construye un grid de video sincronizado — cada celda muestra el timelapse de esa cámara. Si selecciona 1 cámara el grid es 1×1; con 2 o 3 es 1×2 o 1×3; con 4 es 2×2, y así sucesivamente.

**Why this priority**: Sin el grid no existe la aplicación. Todo lo demás — el scrubber, la exportación — opera sobre este grid.

**Independent Test**: Apuntar el indexer a un directorio con `.mp4` de muestra de al menos 2 cámaras distintas, seleccionarlas, y verificar que el grid las muestra en celdas separadas reproduciéndose en timelapse y en sincronía.

**Acceptance Scenarios**:

1. **Given** el indexer ha escaneado el directorio, **When** el operador abre el viewer, **Then** la lista lateral muestra todas las cámaras disponibles con un toggle por cada una.
2. **Given** el operador activa N cámaras, **When** el grid se arma, **Then** aparecen exactamente N celdas de video organizadas en la grilla más cuadrada posible (1→1×1, 2→1×2, 3→1×3, 4→2×2, 5-6→2×3, etc.).
3. **Given** el grid está reproduciéndose, **When** el operador desactiva una cámara, **Then** esa celda desaparece y el grid se reorganiza sin interrumpir las demás.
4. **Given** todas las celdas están activas, **When** se selecciona una fecha y rango horario, **Then** todas las celdas reproducen el timelapse de esa cámara para ese período de forma sincronizada (el mismo punto del tiempo en todas).

---

### User Story 2 — Scrubber de rango dual (Priority: P2)

En la parte inferior de la pantalla hay una barra de progreso azul que representa el período completo seleccionado. Tiene dos punteros arrastrables: uno de inicio y uno de fin. El operador los arrastra para delimitar la porción exacta que le interesa exportar. La zona seleccionada se resalta visualmente. Al mover los punteros, el grid salta al frame correspondiente en todas las cámaras.

**Why this priority**: El scrubber es el mecanismo de precisión que convierte la revisión de footage en una acción concreta. Sin él la exportación no tiene delimitación.

**Independent Test**: Con el grid activo, arrastrar el puntero de inicio al 25 % de la barra y el de fin al 75 %, verificar que la zona intermedia queda resaltada y que todas las celdas del grid muestran el frame del punto de inicio.

**Acceptance Scenarios**:

1. **Given** hay un período cargado en el grid, **When** el operador abre el viewer, **Then** la barra muestra el período completo con el puntero de inicio al extremo izquierdo y el de fin al extremo derecho.
2. **Given** el scrubber está visible, **When** el operador arrastra el puntero de inicio, **Then** la zona a la izquierda del puntero queda oscurecida (fuera del rango) y el grid salta al frame del nuevo inicio.
3. **Given** ambos punteros están posicionados, **When** el operador arrastra el puntero de fin, **Then** la zona a la derecha del puntero queda oscurecida y el grid muestra el frame del fin.
4. **Given** un rango seleccionado, **When** el operador hace clic en cualquier punto de la zona resaltada, **Then** el grid salta a ese instante en todas las cámaras (scrub de posición).
5. **Given** los punteros están posicionados, **When** el operador pulsa Play, **Then** la reproducción comienza desde la posición actual del playhead (o desde el inicio del rango si no hay playhead posicionado) y se detiene al llegar al punto de fin.
6. **Given** hay un período cargado, **When** el operador usa los controles de transporte (⏮ ⏪ ⏩ ⏭), **Then** el playhead salta a la posición correspondiente y todas las celdas muestran el frame de ese instante.
6. **Given** el grid está reproduciéndose, **When** el operador observa el scrubber, **Then** un tercer marcador blanco (playhead) avanza en tiempo real mostrando el instante actual de reproducción.
7. **Given** el playhead es visible, **When** el operador lo arrastra a otra posición, **Then** todas las celdas del grid saltan a ese instante y la reproducción continúa desde ahí.

---

### User Story 3 — Exportar el rango seleccionado (Priority: P3)

Con el rango delimitado por los punteros, el operador pulsa "Exportar". El sistema genera un archivo `.mp4` por cada cámara activa en el grid, cubriendo exactamente el rango definido. Una barra de progreso muestra el avance. Al terminar, aparece un enlace de descarga por cada archivo.

**Why this priority**: La exportación es el entregable final del flujo. Depende del grid (US1) y del rango (US2).

**Independent Test**: Seleccionar 2 cámaras, posicionar los punteros para delimitar 10 minutos de footage, exportar, y verificar que se generan 2 archivos `.mp4` cuya duración coincide con los 10 minutos seleccionados.

**Acceptance Scenarios**:

1. **Given** hay N cámaras en el grid y un rango seleccionado, **When** el operador pulsa "Exportar", **Then** el sistema genera N archivos `.mp4` — uno por cámara — cubriendo exactamente el rango indicado.
2. **Given** una exportación en curso, **When** el sistema está procesando, **Then** se muestra una barra de progreso global y el botón "Exportar" se deshabilita.
3. **Given** la exportación terminó, **When** todos los archivos están listos, **Then** aparece un enlace de descarga por cada cámara, etiquetado con el nombre de la cámara.
4. **Given** el operador descarga un archivo, **When** la descarga completa, **Then** el archivo temporal se elimina automáticamente del SSD.
5. **Given** el rango seleccionado contiene gaps (períodos sin footage), **When** se exporta, **Then** el archivo resultante contiene solo el footage disponible, sin frames negros.

---

### Edge Cases

- ¿Qué pasa si una cámara no tiene footage en el período seleccionado? → Mostrar la celda vacía con un mensaje "Sin footage" y excluirla de la exportación.
- ¿Qué pasa si el puntero de inicio se arrastra más allá del puntero de fin? → Los punteros no se cruzan; el de inicio tiene un tope en la posición del de fin menos 1 segundo, y viceversa.
- ¿Qué pasa si no hay ninguna cámara activa y el operador pulsa Exportar? → El botón permanece deshabilitado cuando el grid está vacío.
- ¿Qué pasa si hay una exportación en curso y el operador cambia el rango o las cámaras? → Los controles de rango y selección de cámaras se bloquean durante la exportación.
- ¿Qué pasa si el SSD no tiene espacio suficiente para los N archivos? → Pre-chequear espacio antes de iniciar; rechazar con mensaje claro si es insuficiente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El indexer DEBE escanear recursivamente el directorio de footage e indexar archivos `.mp4` usando la estructura de Shinobi (`GroupKey/MonitorID/[YYYY-MM-DD/]filename.mp4`). El segmento de fecha es opcional.
- **FR-002**: El indexer DEBE omitir cualquier archivo cuya fecha de modificación sea de hace menos de 60 segundos.
- **FR-003**: El indexer DEBE almacenar todos los metadatos exclusivamente en una base SQLite local en el SSD — sin escribir nunca en el HDD externo.
- **FR-004**: El indexer DEBE ejecutar un escaneo completo al arrancar y repetirlo cada 60 segundos.
- **FR-005**: El sistema DEBE exponer un endpoint para listar todas las cámaras/monitores disponibles.
- **FR-006**: El sistema DEBE exponer un endpoint para consultar chunks de video por cámara y rango de tiempo.
- **FR-006b**: El sistema DEBE servir los archivos `.mp4` del HDD de forma directa mediante HTTP con soporte de Range Requests (`Accept-Ranges: bytes`), para que el browser pueda cargar y controlar la reproducción sin procesamiento previo.
- **FR-007**: La UI DEBE mostrar una lista lateral de cámaras con un toggle (activar/desactivar) por cada una.
- **FR-007b**: La UI DEBE proveer un selector de fecha más dos inputs de hora (inicio y fin del período) para definir el período de tiempo visible en el grid. Al confirmar el período, todas las celdas activas cargan y sincronizan su reproducción a partir del inicio del período.
- **FR-008**: La UI DEBE construir un grid de celdas de video con una celda por cámara activa, reorganizándose dinámicamente al activar o desactivar cámaras. El grid soporta un máximo de 9 cámaras simultáneas (3×3); el toggle de una décima cámara se deshabilita mientras haya 9 activas.
- **FR-009**: Cada celda del grid DEBE reproducir los chunks de su cámara directamente en un elemento `<video>` del browser a velocidad acelerada (`playbackRate`), sincronizada con todas las demás celdas al mismo instante de tiempo. El timelapse es un efecto client-side; no se genera ningún archivo intermedio en el servidor para la visualización.
- **FR-010**: La UI DEBE mostrar una barra de scrubber con dos punteros arrastrables (inicio y fin) que delimitan el rango de exportación.
- **FR-010b**: La UI DEBE proveer un selector de velocidad de reproducción con cuatro valores discretos: 1×, 4×, 8× (por defecto) y 16×. Al cambiar la velocidad, el `playbackRate` de todas las celdas activas se actualiza en sincronía.
- **FR-010c**: Mientras una celda está cargando o bufferando, DEBE mostrar un spinner centrado sobre fondo oscuro con el nombre de la cámara visible en la parte superior. Una vez listo el video, el spinner desaparece y la reproducción comienza automáticamente.
- **FR-011**: Al mover cualquier puntero, todas las celdas del grid DEBEN saltar al frame correspondiente al instante del puntero.
- **FR-012**: La zona del scrubber fuera del rango seleccionado DEBE oscurecerse visualmente; la zona dentro DEBE resaltarse en azul.
- **FR-013**: El sistema DEBE generar un archivo `.mp4` por cada cámara activa en el grid, cubriendo exactamente el rango delimitado por los punteros, usando concatenación lossless.
- **FR-014**: Antes de iniciar cualquier exportación, el sistema DEBE verificar que el SSD tiene espacio suficiente para N archivos; si no, rechazar con mensaje claro.
- **FR-015**: Solo puede haber una exportación activa a la vez; nuevas solicitudes DEBEN rechazarse con HTTP 409 mientras haya una en curso.
- **FR-016**: Durante la exportación, la UI DEBE mostrar una barra de progreso global y bloquear los controles de cámara y scrubber.
- **FR-017**: Al completar la exportación, la UI DEBE mostrar un enlace de descarga por cada archivo, etiquetado con el nombre de la cámara.
- **FR-018**: Los archivos temporales de exportación DEBEN eliminarse automáticamente del SSD tras la descarga.
- **FR-019**: El sistema NUNCA DEBE escribir, modificar, mover, renombrar ni eliminar ningún archivo en el directorio de footage del HDD externo.
- **FR-020**: Si una cámara activa no tiene footage en el rango seleccionado, su celda DEBE mostrar "Sin footage" y DEBE excluirse de la exportación.
- **FR-021**: Al pasar el cursor sobre la barra del scrubber, DEBE mostrarse un tooltip con la hora exacta correspondiente al punto bajo el cursor; el tooltip desaparece al salir de la barra.
- **FR-022**: La barra del scrubber DEBE mostrar un tercer marcador (playhead) que indica la posición actual de reproducción; el marcador avanza automáticamente durante la reproducción y puede arrastrarse para hacer seek a cualquier instante del período, sin interrumpir la reproducción.
- **FR-023**: La UI DEBE exponer controles de transporte: ir al inicio del rango (⏮), retroceder 30 s (⏪), play/pausa, avanzar 30 s (⏩) e ir al final del rango (⏭). Los saltos de 30 s se calculan desde la posición actual del playhead y se limitan a los extremos del rango. Todos los controles se habilitan al confirmar el período.
- **FR-024**: Al confirmar el período, los handles del scrubber DEBEN auto-posicionarse al rango real del footage disponible (inicio del primer chunk y fin del último chunk, calculado como unión de todas las cámaras activas). Si el operador seleccionó 12:00–22:00 pero el footage solo existe de 17:00–22:00, los handles quedan en 17:00–22:00 automáticamente.
- **FR-025**: La barra lateral DEBE incluir un botón "Seleccionar todas" que activa simultáneamente todas las cámaras disponibles. Cuando todas están activas, el botón cambia a "Deseleccionar todas" y al pulsarlo desactiva todas. Las cámaras deshabilitadas por límite de grid (máx. 9) no se consideran para este toggle.

### Key Entities

- **Monitor**: Cámara de Shinobi identificada por `GroupKey` + `MonitorID`.
- **VideoChunk**: Archivo `.mp4` grabado con start\_ts, end\_ts, duración, tamaño y ruta absoluta en el HDD.
- **Index**: Base SQLite en el SSD con tablas `monitors` y `video_chunks`.
- **GridCell**: Representación en UI de una cámara activa dentro del grid; contiene el estado de reproducción (posición actual, buffering).
- **ScrubRange**: El par (start\_ts, end\_ts) definido por los dos punteros del scrubber; determina qué se exporta.
- **ExportJob**: Operación transitoria que genera N archivos `.mp4` (uno por cámara activa) en el SSD, con ciclo de vida que termina al completarse todas las descargas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El grid con hasta 9 cámaras activas carga y comienza a reproducirse en menos de 3 segundos tras seleccionar el período.
- **SC-002**: Al arrastrar un puntero del scrubber, todas las celdas del grid actualizan su frame en menos de 500 ms.
- **SC-003**: La exportación de un rango de 1 hora para 4 cámaras simultáneas está disponible para descarga en menos de 5 minutos.
- **SC-004**: Los archivos exportados reproducen exactamente el rango seleccionado sin gaps ni corrupción.
- **SC-005**: Los archivos temporales de exportación se eliminan del SSD en menos de 60 segundos tras completarse cada descarga.
- **SC-006**: El indexer completa un escaneo de 10 000 archivos sin errores ni interrupciones en la grabación de Shinobi.

## Assumptions

- El directorio de footage de Shinobi es configurable al arrancar y no cambia durante la operación.
- El viewer se ejecuta localmente en la misma máquina que aloja el SSD — no hay requisito multi-usuario ni despliegue remoto en v1.
- FFmpeg está instalado y accesible en el PATH del sistema.
- El HDD externo está montado y es legible en todo momento; no se manejan escenarios de desconexión en caliente.
- La autenticación y el control de acceso están fuera del alcance de v1; el viewer es para uso local en LAN.
- El soporte para navegadores móviles está fuera del alcance de v1; la UI apunta a navegadores de escritorio.
- El timelapse del grid es el modo de visualización principal; la velocidad de reproducción es configurable (por defecto 8×).

## Clarifications

### Session 2026-09-25 (rev2 — nuevo spec)

- Q: ¿Cómo se reproduce el video en cada celda del grid — el backend genera un timelapse o el browser carga los chunks directamente? → A: El browser carga los chunks directamente vía HTTP Range Requests y los reproduce a alta velocidad (`playbackRate`). FFmpeg solo se usa para exportar.
- Q: ¿Cuántas cámaras simultáneas debe soportar el grid como máximo? → A: Máximo 9 cámaras (grilla 3×3); la décima se deshabilita si ya hay 9 activas.
- Q: ¿Cómo selecciona el operador el período de tiempo que se muestra en el grid? → A: Selector de fecha + dos inputs de hora (inicio y fin). El scrubber dual opera dentro de ese período para delimitar el sub-rango de exportación.
- Q: ¿Puede el operador cambiar la velocidad de reproducción del grid desde la UI? → A: Sí, selector con valores discretos: 1×, 4×, 8× (por defecto), 16×.
- Q: ¿Qué debe mostrar una celda del grid mientras los chunks están cargando o bufferando? → A: Spinner centrado sobre fondo oscuro con el nombre de la cámara visible arriba; desaparece al comenzar la reproducción.

- Q: How should the indexer determine when to scan the footage directory for new clips? → A: Startup scan immediately on launch, then periodic every 60 seconds.
- Q: If a user submits a new export or timelapse request while one is already processing, what should the system do? → A: Allow only one active job at a time; reject new requests with a clear error message while busy.
- Q: What should the system do when the local SSD has insufficient disk space to generate an export or timelapse? → A: Check available SSD space before starting; reject the job with a clear message if space is insufficient, without writing any partial files.
- Q: What should the user see in the UI while an export or timelapse job is processing? → A: Progress bar with a cancel option that aborts the job and cleans up partial files.
- Q: When the indexer finds a previously indexed clip no longer exists on the HDD, what should happen to that entry? → A: Mark it as unavailable in the index; show it grayed-out and non-selectable in the timeline.
