# Speckit Workflow

## 1 — Inicializar un proyecto nuevo

Ejecutar una sola vez por proyecto para establecer los principios, el stack y las restricciones que guiarán todos los features.

```mermaid
flowchart TD
    START([Proyecto nuevo]) --> CONST

    CONST["/speckit-constitution"]:::cmd
    CONST --> A1["📄 .specify/memory/constitution.md\nPrincipios · stack · compliance"]:::artifact
    CONST --> A2["📁 .specify/templates/\nspec · plan · tasks · checklist"]:::artifact
    CONST --> A3["📁 .specify/scripts/\nBash helpers de automatización"]:::artifact
    CONST --> A4["📁 .specify/workflows/\nRegistro de workflows de Speckit"]:::artifact
    CONST --> A5["⚙️ .specify/init-options.json\nConfiguración de numeración y AI"]:::artifact

    A1 & A2 & A3 & A4 & A5 --> READY([Proyecto listo para features])

    classDef cmd fill:#6366f1,color:#fff,stroke:none,rx:6
    classDef artifact fill:#1e293b,color:#94a3b8,stroke:#334155
```

---

## 2 — Ciclo de un feature nuevo

Repetir para cada feature. Los pasos marcados *(opcional)* se pueden saltear si el artefacto anterior ya está completo y sin ambigüedades.

```mermaid
flowchart TD
    DESC([Descripción del feature]) --> SPECIFY

    SPECIFY["/speckit-specify"]:::cmd
    SPECIFY --> S1["📄 specs/NNN-feature/spec.md\nEscenarios · requisitos · criterios de éxito"]:::artifact
    SPECIFY --> S2["📄 specs/NNN-feature/checklists/requirements.md\nValidación de calidad del spec"]:::artifact

    S1 & S2 --> CLARIFY_Q{¿Hay ambigüedades\nen el spec?}

    CLARIFY_Q -- Sí --> CLARIFY
    CLARIFY["/speckit-clarify *(opcional)*"]:::cmd_opt
    CLARIFY --> S1_UP["📄 spec.md actualizado\nMarcadores NEEDS CLARIFICATION resueltos"]:::artifact

    CLARIFY_Q -- No --> PLAN
    S1_UP --> PLAN

    PLAN["/speckit-plan"]:::cmd
    PLAN --> P1["📄 specs/NNN-feature/plan.md\nArquitectura · componentes · decisiones de diseño"]:::artifact

    P1 --> TASKS

    TASKS["/speckit-tasks"]:::cmd
    TASKS --> T1["📄 specs/NNN-feature/tasks.md\nTareas ordenadas por dependencias"]:::artifact

    T1 --> ANALYZE_Q{¿Validar\nconsistencia?}

    ANALYZE_Q -- Sí --> ANALYZE
    ANALYZE["/speckit-analyze *(opcional)*"]:::cmd_opt
    ANALYZE --> AN1["🔍 Reporte de consistencia\nspec ↔ plan ↔ tasks"]:::artifact

    ANALYZE_Q -- No --> IMPLEMENT
    AN1 --> IMPLEMENT

    IMPLEMENT["/speckit-implement"]:::cmd
    IMPLEMENT --> CODE["💻 Código generado\nSegún las tareas del tasks.md"]:::artifact

    CODE --> DONE_Q{¿Quedan tareas\nsin implementar?}

    DONE_Q -- Sí --> CONVERGE
    CONVERGE["/speckit-converge"]:::cmd
    CONVERGE --> T1_UP["📄 tasks.md actualizado\nNuevas tareas appendadas al final"]:::artifact
    T1_UP --> IMPLEMENT

    DONE_Q -- No --> END([Feature completo ✓])

    classDef cmd fill:#6366f1,color:#fff,stroke:none
    classDef cmd_opt fill:#7c3aed,color:#fff,stroke:none,stroke-dasharray:4 4
    classDef artifact fill:#1e293b,color:#94a3b8,stroke:#334155
```

---

## Resumen de comandos y artefactos

| Comando | Artefacto generado | Obligatorio |
|---|---|:---:|
| `/speckit-constitution` | `.specify/memory/constitution.md`, templates, scripts | Una vez |
| `/speckit-specify` | `specs/NNN/spec.md`, `checklists/requirements.md` | ✅ |
| `/speckit-clarify` | `spec.md` actualizado | Opcional |
| `/speckit-plan` | `specs/NNN/plan.md` | ✅ |
| `/speckit-tasks` | `specs/NNN/tasks.md` | ✅ |
| `/speckit-analyze` | Reporte de consistencia en consola | Opcional |
| `/speckit-implement` | Código fuente | ✅ |
| `/speckit-converge` | `tasks.md` con tareas faltantes appendadas | Si hay deuda |
