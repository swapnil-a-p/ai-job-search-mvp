# Operating Model

## Current Runtime Model

The workflow runs as a local batch job initiated by an operator. It uses:

- environment-based configuration
- local run-state tracking for LinkedIn throttling
- local cache for Vertex AI response reuse
- Google Sheets as the human review and control layer

## Operational Characteristics

- idempotent-ish reruns with preserved manual status fields
- partial feature toggles for discovery and enrichment
- cost control through shortlist-only LLM analysis
- low-friction operator control through sheet tabs instead of a custom UI

## Failure Modes

- actor execution failure from third-party scraping services
- credential or IAM failure for Sheets / Vertex AI
- schema drift in raw source inputs
- LLM call limits or latency spikes

## Practical Mitigations

- preserve deterministic scoring as fallback
- cache LLM responses locally
- allow selective feature disablement through env flags
- log each stage of the pipeline with summary counts

## Production-Oriented Next Steps

- externalized state store
- structured metrics and alerting
- retry policies around remote services
- dead-letter or failed-job tracking
- containerized scheduled execution
