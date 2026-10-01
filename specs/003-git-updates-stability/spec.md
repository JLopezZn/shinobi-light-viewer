# Feature Specification: Git Updates, Branch Switcher & App Stability

**Feature Branch**: `003-git-updates-stability`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "necesito que ahora la aplicacion pueda actualizarse con un boton que diga 'buscar actualizaciones' y lo que hara es hacer pull de la rama en la que esta situada, de igual forma, creo que seria util el poder switchear entre ramas y volver a ejecutar el programa en caso de que cambie de branch, por cierto, necesito que mejores el programa porque aveces cierra asi que necesito que siempre este corriendo, debe de haber como un try catch general en el cual si se corta la app entonces se reinicie."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-Restart After Crash (Priority: P1)

The application occasionally stops unexpectedly. As an operator, I need the app to recover on its own without requiring manual intervention, so the viewer remains available at all times.

**Why this priority**: This addresses an immediate pain point — the app going down means surveillance footage becomes inaccessible. Reliability is the foundation for everything else.

**Independent Test**: Can be fully tested by simulating an unexpected process termination and verifying the app comes back online automatically, delivering continuous uptime without manual restarts.

**Acceptance Scenarios**:

1. **Given** the app is running normally, **When** it crashes due to an unhandled error, **Then** it automatically restarts within 10 seconds without any manual intervention.
2. **Given** the app has crashed, **When** it restarts, **Then** it resumes normal operation with all features intact.
3. **Given** the app crashes repeatedly in a short period, **When** a restart threshold is reached, **Then** the system pauses restart attempts and logs the issue rather than looping indefinitely.
4. **Given** the app is in the crash-capped state, **When** the operator clicks the "Reiniciar App" button in the UI, **Then** the app resets the crash counter and attempts a fresh restart.

---

### User Story 2 - Check for Updates Button (Priority: P2)

As an operator, I want a "Buscar Actualizaciones" button in the app's interface that pulls the latest code from the current branch, so I can update the app without leaving the UI or touching the terminal.

**Why this priority**: Operators should be able to apply updates easily and safely. Without this, updates require terminal access and manual restarts, increasing friction and risk of error.

**Independent Test**: Can be fully tested by clicking the button and verifying the app fetches and applies the latest code from the repository, showing a clear result message.

**Acceptance Scenarios**:

1. **Given** there are new changes on the current branch, **When** the operator clicks "Buscar Actualizaciones", **Then** the app pulls the latest changes and displays a success message indicating what was updated.
2. **Given** the app is already up to date, **When** the operator clicks "Buscar Actualizaciones", **Then** the app confirms there are no new changes.
3. **Given** the update fails (e.g., network unavailable, merge conflicts), **When** the operator clicks "Buscar Actualizaciones", **Then** the app displays a clear error message and the running version remains unchanged.
4. **Given** an update was successfully pulled, **When** the pull completes, **Then** the app restarts automatically without requiring any additional operator action.

---

### User Story 3 - Branch Switcher (Priority: P3)

As an operator, I want to select a different branch from a list in the UI and have the app switch to it and restart automatically, so I can run different versions of the app (e.g., staging vs. production) without terminal access.

**Why this priority**: Useful for testing and version management, but it is not critical for day-to-day operation and depends on the update feature being reliable.

**Independent Test**: Can be fully tested by selecting a different branch from the UI dropdown, verifying the app switches to that branch and restarts running the new version.

**Acceptance Scenarios**:

1. **Given** the operator opens the branch selector, **When** it loads, **Then** it fetches the latest branch list from the remote and shows all available local and remote branches, with a loading indicator during the fetch.
2. **Given** the operator selects a different branch, **When** they confirm the switch, **Then** the app checks out the selected branch and restarts automatically.
3. **Given** a branch switch is in progress, **When** the checkout fails, **Then** the app reverts to the previous branch, restarts, and shows an error message.
4. **Given** the operator selects the currently active branch, **When** they confirm, **Then** the app informs them it is already on that branch and takes no action.

---

### Edge Cases

- What happens if the app crashes again immediately after auto-restarting (rapid crash loop)?
- What if the "Buscar Actualizaciones" pull introduces breaking changes that prevent the app from restarting?
- What if the branch switcher is used while an update pull is already in progress?
- What if there are uncommitted local changes that conflict with the pull or branch switch? → Handled: the system aborts and hard-resets to the pre-operation state (FR-006b, FR-009).
- What if the repository remote is unreachable when checking for updates?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST automatically restart the application process whenever it terminates unexpectedly due to an error.
- **FR-002**: The system MUST limit automatic restart attempts; after 5 consecutive crashes within a 2-minute window, it MUST pause restarts and record the failure state.
- **FR-002a**: When in the crash-capped state, the UI MUST display a "Reiniciar App" button that is only enabled in this state. Clicking it MUST reset the crash counter and trigger a fresh restart attempt.
- **FR-003**: The UI MUST include a "Buscar Actualizaciones" button accessible from the main interface.
- **FR-004**: Clicking "Buscar Actualizaciones" MUST pull the latest changes from the branch the app is currently running on.
- **FR-005**: The update operation MUST display its result (success with summary, already up to date, or failure with reason) to the operator.
- **FR-006**: After a successful update pull, the system MUST always restart the application automatically. No conditional detection of changed files is required.
- **FR-006b**: If the update pull results in merge conflicts or any git error, the system MUST abort the operation, hard-reset the repository to its pre-pull state, display a clear error message to the operator, and leave the running application version unchanged.
- **FR-007**: The UI MUST provide a branch selector that, when opened, first fetches the latest branch list from the remote and then displays all branches (local and remote). A loading indicator MUST be shown while the fetch is in progress.
- **FR-008**: Selecting a branch MUST switch the repository to that branch and trigger an automatic application restart.
- **FR-009**: If branch switching fails, the system MUST revert to the previously active branch, restart, and display the error reason.
- **FR-010**: Update and branch-switch operations MUST be mutually exclusive; attempting one while the other is in progress MUST be blocked with an informative message.
- **FR-011**: The system MUST log all crash events, restart attempts, update operations, and branch switches for diagnostic purposes.
- **FR-012**: A lightweight status page MUST remain accessible even when the main application is down. It MUST display the current app state (running, restarting, crash-capped) and, when crash-capped, MUST expose the "Reiniciar App" action so the operator can recover without needing terminal access.

### Key Entities

- **App Process**: The running application instance — has a status (running, crashed, restarting, crash-capped) and a current branch.
- **Status Page**: A separate lightweight process that stays alive independently of the main app, exposing the app's health state and recovery actions.
- **Branch**: A named version of the codebase — has a name, and may be local or remote.
- **Update Operation**: A pull action on the current branch — has a status (pending, success, up-to-date, failed) and a result summary.
- **Crash Event**: A record of an unexpected termination — has a timestamp, error reason, and restart outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The app recovers from an unexpected crash and is accessible again within 10 seconds in 95% of cases.
- **SC-002**: The "Buscar Actualizaciones" button completes an update check and presents a result within 30 seconds under normal network conditions.
- **SC-003**: Branch switching completes (checkout + restart) within 30 seconds for branches already available locally.
- **SC-004**: Operators can perform updates and branch switches without any terminal access, 100% of the time.
- **SC-005**: The app does not enter an infinite crash loop; restart attempts are capped, and the crash-capped state is visible to the operator via a status page that remains accessible even when the main app is offline.

## Assumptions

- The application is a single-process service running on a machine with git installed and a properly configured repository.
- The operator is the sole user of the app; no multi-user access control is required for update or branch-switch actions.
- Remote branches are accessible from the host machine (network connectivity to the git remote is available under normal conditions).
- "Restart" means stopping the current process and starting a new one; the mechanism for this is handled by the process supervisor (out of scope for UI spec).
- Uncommitted local changes on the host are not expected; the operator is assumed to work only via this UI and not modify files manually.
- The app always restarts automatically after a successful update pull, regardless of which files changed.
- Mobile/tablet support for the UI is out of scope for this feature.

## Clarifications

### Session 2026-10-01

- Q: When the app hits the crash cap and stops auto-restarting, how should the operator manually recover? → A: Show a "Reiniciar App" button in the UI that becomes active only when the crash cap is hit, allowing one-click manual recovery.
- Q: After a successful update pull, should the app always restart automatically or only when required by the changes? → A: Always restart automatically after a successful pull; no conditional detection needed.
- Q: When a git pull during "Buscar Actualizaciones" results in merge conflicts, what should the app do? → A: Abort and hard-reset to pre-pull state; display a conflict error and leave the running version unchanged.
- Q: Should the branch switcher show only local branches or fetch remote branches before listing? → A: Fetch remote branches first, then show all (local + remote); show a loading indicator during the fetch.
- Q: When the crash cap is hit and the main app is down, how should the operator be notified or able to recover? → A: A lightweight status page remains accessible independently of the main app and shows the crash state plus the "Reiniciar App" recovery action.
