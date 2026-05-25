# Architecture

## Purpose

The system is a decision-support workflow for job search operations, not just a scraper. It combines discovery, normalization, scoring, enrichment, and spreadsheet-driven task management.

## Architecture Diagram

```mermaid
flowchart LR
    classDef actor fill:#eef6ff,stroke:#4d8dff,color:#133768,stroke-width:2px;
    classDef orchestrator fill:#102840,stroke:#5bc0ff,color:#eefaff,stroke-width:2px;
    classDef process fill:#173a2f,stroke:#68d4a5,color:#effff7,stroke-width:2px;
    classDef ai fill:#331b45,stroke:#cc8cff,color:#fff3ff,stroke-width:2px;
    classDef storage fill:#2b3547,stroke:#9ebdff,color:#f3f7ff;
    classDef output fill:#3b2d16,stroke:#ffca6b,color:#fff8eb,stroke-width:2px;

    OP[Operator / scheduler]
    CFG[Env config +<br/>local state]

    subgraph PIPE[Execution Pipeline]
        ORCH[Python orchestrator<br/>main.py]
        APIFY[Apify actors<br/>job + employee discovery]
        NORM[Normalization layer]
        SCORE[Rules engine]
        LLM[Vertex AI enrichment]
    end

    subgraph STATE[State + Operational Plane]
        CACHE[Local LLM cache]
        SHEETS[Google Sheets<br/>control plane]
    end

    OUT[Shortlist / referral /<br/>employee outputs]

    OP --> ORCH
    CFG --> ORCH
    ORCH --> APIFY
    APIFY --> NORM
    NORM --> SCORE
    SCORE --> LLM
    LLM <--> CACHE
    SCORE --> OUT
    LLM --> OUT
    OUT --> SHEETS
    SHEETS --> ORCH

    class OP actor;
    class CFG,CACHE,SHEETS storage;
    class ORCH orchestrator;
    class APIFY,NORM,SCORE process;
    class LLM ai;
    class OUT output;
```

## Service Components

- Apify actors for search execution and external data retrieval
- Python orchestration layer for workflow sequencing
- rules engine for deterministic prioritization
- Vertex AI for semantic enrichment and resume guidance
- Google Sheets as the operational control plane and output workspace

## Data Flow

1. Read config and initialize runtime dependencies.
2. Seed or load `Target_Companies`.
3. Execute Google and optional LinkedIn discovery.
4. Normalize all discovered jobs into a unified internal schema.
5. Deduplicate and score jobs with rule-based heuristics.
6. Select top candidate pool for LLM enrichment.
7. Enrich selected jobs with Vertex AI.
8. Build shortlist, referral targets, and employee targets.
9. Persist outputs to Google Sheets while preserving manual workflow fields.

## Design Choices

- Google Sheets is used as an operator-facing control plane because it supports rapid iteration and manual overrides.
- LLM enrichment is selectively applied to control cost and reduce unnecessary calls.
- Local cache and run-state files keep the MVP simple while still allowing throttling and repeatability.
- Deterministic scoring remains in place even when LLM enrichment is disabled.

## Evolution Path

The current design can evolve into a more production-style architecture by:

- replacing local state with cloud storage or a database
- splitting discovery and enrichment into separate scheduled jobs
- moving execution into Cloud Run jobs, ECS scheduled tasks, or an Airflow-like orchestrator
- instrumenting cost, latency, and quality metrics centrally
