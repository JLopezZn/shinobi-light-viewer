# Feature Specification: Shinobi Pod Manager

**Feature Branch**: `002-shinobi-pod-manager`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: "Necesito que la aplicacion tenga un gestor de shinobi para apagar, iniciar o reiniciar el pod donde corre shinobi, ya que la computadora donde actualmente corre shinobi lo tiene corriendo con docker desktop en windows, pero la funcionalidad debe funcionar tanto para windows como para linux, que pretendo con esto, que si alguien quiere reiniciar la pc vaya a este gestor y primero detenga el servicio de shinobi y asi no se corrompa el hdd, por cierto, tambien debes modificar el start.bat y start.sh para que no arranque el server hasta que primero inicie el pod ya que aveces arranca primero el server sin que este corriendo shinobi y este crashea"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detener Shinobi antes de reiniciar la PC (Priority: P1)

Un usuario quiere reiniciar o apagar la computadora donde corre Shinobi. Para no corromper el HDD externo donde están grabadas las cámaras, primero abre el gestor de Shinobi desde la aplicación web y detiene el contenedor Docker de Shinobi. Una vez confirmado que el servicio se detuvo correctamente, puede reiniciar la PC con seguridad.

**Why this priority**: Es el caso de uso principal que motivó la feature. Sin esta capacidad, los usuarios apagan la PC sin detener Shinobi, lo que puede corromper los archivos del HDD externo.

**Independent Test**: Se puede probar de forma independiente iniciando el contenedor de Shinobi, yendo a la sección de Gestor, presionando "Detener", y verificando que el contenedor ya no está en ejecución.

**Acceptance Scenarios**:

1. **Given** el contenedor de Shinobi está corriendo, **When** el usuario hace clic en "Detener Shinobi", **Then** el sistema envía el comando de detención al Docker runtime, espera confirmación, y muestra el estado actualizado como "Detenido".
2. **Given** el contenedor de Shinobi ya está detenido, **When** el usuario hace clic en "Detener Shinobi", **Then** el sistema informa que el servicio ya está inactivo sin generar un error.
3. **Given** el contenedor de Shinobi está corriendo, **When** el comando de detención falla (ej. Docker no responde), **Then** el sistema muestra un mensaje de error claro y el estado no cambia.

---

### User Story 2 - Iniciar Shinobi desde la aplicación (Priority: P2)

Un usuario quiere arrancar el contenedor de Shinobi desde la interfaz web, por ejemplo después de haber reiniciado la PC o haberlo detenido manualmente.

**Why this priority**: Complemento natural del flujo de detención. Permite el ciclo completo de gestión sin necesidad de acceso directo al servidor.

**Independent Test**: Se puede probar deteniendo el contenedor manualmente, yendo al gestor, presionando "Iniciar Shinobi", y verificando que el contenedor vuelve a estar en ejecución.

**Acceptance Scenarios**:

1. **Given** el contenedor de Shinobi está detenido, **When** el usuario hace clic en "Iniciar Shinobi", **Then** el sistema lanza el contenedor y muestra el estado como "En ejecución" una vez que está listo.
2. **Given** el contenedor de Shinobi ya está corriendo, **When** el usuario hace clic en "Iniciar Shinobi", **Then** el sistema informa que el servicio ya está activo sin lanzar un duplicado.
3. **Given** Docker no está disponible o el contenedor no existe, **When** el usuario intenta iniciar Shinobi, **Then** el sistema muestra un error descriptivo.

---

### User Story 3 - Reiniciar Shinobi desde la aplicación (Priority: P2)

Un usuario quiere reiniciar el contenedor de Shinobi (detener + iniciar) para aplicar cambios de configuración o recuperarse de un estado inconsistente, sin necesidad de hacerlo en dos pasos.

**Why this priority**: Operación de mantenimiento frecuente que combina detener e iniciar en una sola acción, reduciendo el riesgo de olvidar el paso de inicio.

**Independent Test**: Se puede probar con el contenedor corriendo, presionando "Reiniciar Shinobi", y verificando que el contenedor fue detenido y vuelto a iniciar.

**Acceptance Scenarios**:

1. **Given** el contenedor de Shinobi está corriendo, **When** el usuario hace clic en "Reiniciar Shinobi", **Then** el sistema detiene el contenedor, lo vuelve a iniciar, y muestra el estado final como "En ejecución".
2. **Given** la detención falla durante el reinicio, **Then** el sistema aborta el reinicio, muestra el error, y no intenta el inicio.

---

### User Story 4 - Arranque seguro del servidor de la aplicación (Priority: P1)

Al iniciar la aplicación mediante `start.bat` (Windows) o `start.sh` (Linux), el servidor de la aplicación no debe arrancar hasta confirmar que el contenedor de Shinobi ya está en ejecución. Esto evita que el servidor crashee por intentar conectarse a Shinobi antes de que esté disponible.

**Why this priority**: Es igualmente crítico que la detención segura. Un servidor que arranca antes que Shinobi genera errores de inicio que requieren intervención manual.

**Independent Test**: Se puede probar ejecutando `start.bat` o `start.sh` con el contenedor detenido y verificando que el script espera o alerta antes de iniciar el servidor de la aplicación.

**Acceptance Scenarios**:

1. **Given** `start.bat` / `start.sh` es ejecutado y el contenedor de Shinobi está detenido, **When** el script inicia, **Then** el script espera (con reintentos y timeout configurable) hasta que el contenedor esté en ejecución antes de arrancar el servidor.
2. **Given** el contenedor de Shinobi arranca correctamente durante la espera, **When** el contenedor pasa a estado "En ejecución", **Then** el script procede a iniciar el servidor de la aplicación normalmente.
3. **Given** el contenedor no arranca dentro de los 120 segundos de espera, **When** se alcanza el timeout, **Then** el script muestra un mensaje claro de error, no inicia el servidor, y termina con código de salida no-cero.

---

### Edge Cases

- ¿Qué pasa si Docker Desktop no está instalado o no está corriendo en el sistema?
- ¿Qué pasa si el nombre del contenedor de Shinobi difiere del valor esperado?
- ¿Qué pasa si el usuario hace clic múltiples veces rápidamente en un botón de control?
- ¿Qué pasa si se pierde la conexión al servidor mientras una operación está en progreso?
- ¿Qué pasa si el sistema operativo es diferente a Windows o Linux (ej. macOS)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La aplicación DEBE exponer una sección de "Gestor de Shinobi" accesible únicamente desde la sección de administración de la interfaz web, restringida a usuarios con acceso admin.
- **FR-002**: La sección DEBE mostrar el estado actual del contenedor de Shinobi (En ejecución / Detenido / Desconocido) con actualización automática mediante polling periódico mientras la sección está abierta en el navegador.
- **FR-003**: La sección DEBE ofrecer acciones: Iniciar, Detener y Reiniciar el contenedor de Shinobi.
- **FR-004**: El sistema DEBE ejecutar los comandos de gestión del contenedor de forma compatible con Docker en Windows (Docker Desktop) y en Linux.
- **FR-005**: El sistema DEBE esperar confirmación del nuevo estado del contenedor (no solo disparar el comando) antes de actualizar la UI.
- **FR-006**: El sistema DEBE deshabilitar los botones de acción mientras una operación está en progreso para evitar ejecuciones duplicadas.
- **FR-007**: El sistema DEBE mostrar mensajes de error claros y accionables si una operación falla.
- **FR-008**: El script `start.bat` DEBE verificar que el contenedor de Shinobi está en ejecución antes de iniciar el servidor de la aplicación, con reintentos periódicos y un timeout máximo de 120 segundos.
- **FR-009**: El script `start.sh` DEBE verificar que el contenedor de Shinobi está en ejecución antes de iniciar el servidor de la aplicación, con reintentos periódicos y un timeout máximo de 120 segundos.
- **FR-010**: Si el contenedor no está en ejecución al alcanzar los 120 segundos de espera, los scripts DEBEN mostrar un mensaje descriptivo y terminar sin iniciar el servidor.
- **FR-011**: El nombre del contenedor de Shinobi DEBE ser configurable (sin hardcodear) para adaptarse a diferentes instalaciones.

### Key Entities

- **Contenedor Shinobi**: Instancia Docker que corre la aplicación Shinobi. Tiene un nombre identificador, un estado (running / stopped / error), y es gestionado por Docker runtime.
- **Estado del Gestor**: Representación en la UI del estado actual del contenedor y de cualquier operación en progreso.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un usuario puede detener el contenedor de Shinobi desde la interfaz web en menos de 30 segundos desde que hace clic hasta obtener confirmación visual del nuevo estado.
- **SC-002**: El servidor de la aplicación nunca crashea por intentar conectarse a Shinobi antes de que esté disponible cuando se usa `start.bat` o `start.sh`.
- **SC-003**: El gestor funciona correctamente en una instalación Windows con Docker Desktop y en una instalación Linux con Docker Engine sin modificaciones de código.
- **SC-004**: Las operaciones de inicio, detención y reinicio tienen una tasa de éxito del 100% cuando Docker está disponible y el contenedor existe.
- **SC-005**: En caso de error (Docker no disponible, contenedor inexistente), el usuario recibe un mensaje descriptivo sin que la aplicación quede en un estado inusable.

## Clarifications

### Session 2026-09-27

- Q: ¿Quién puede acceder y usar el Gestor de Shinobi dentro de la interfaz web? → A: Solo usuarios con acceso a la sección de administración de la app (misma sesión/credencial que el área admin existente).
- Q: ¿El estado del contenedor en la UI debe actualizarse automáticamente sin que el usuario recargue, o solo cuando el usuario presiona un botón de refresco? → A: Estado se refresca automáticamente con polling periódico mientras la sección está abierta.
- Q: ¿Cuánto tiempo máximo deben esperar `start.bat` y `start.sh` para que Shinobi arranque antes de abortar el inicio del servidor? → A: 120 segundos.

## Assumptions

- El runtime de Docker (Docker Desktop en Windows o Docker Engine en Linux) está instalado y accesible por el servidor de la aplicación.
- El contenedor de Shinobi fue creado con `docker run` o `docker-compose` y tiene un nombre o ID conocido configurable.
- La aplicación corre en el mismo sistema que el runtime de Docker (acceso local a Docker socket o CLI).
- El gestor es accesible únicamente desde la sección admin de la app, usando la misma sesión/credencial que ya protege esa sección. La implementación concreta de la gestión de sesión (cookies, tokens) es una decisión de la fase de plan.
- **Dependencia**: Si la app no tiene actualmente un mecanismo de acceso admin, crearlo es un prerequisito de esta feature.
- macOS está fuera del alcance de esta feature (el sistema objetivo es Windows + Linux).
- La configuración del nombre del contenedor se puede definir mediante variable de entorno o archivo de configuración existente del proyecto.
- Los scripts `start.bat` y `start.sh` ya existen en el proyecto y solo requieren modificación de la lógica de arranque, no una reescritura completa.
