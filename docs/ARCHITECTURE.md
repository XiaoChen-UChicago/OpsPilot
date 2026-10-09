# Architecture notes

OpsPilot is intentionally modular. Each component represents a business decision boundary rather than a technology layer.

## Components

### Intake and normalization

`models.py` defines the portable lead schema, normalizes URLs and emails, and removes duplicate records. The normalized table is the contract between the workflow stages.

### Public research

`enrichment.py` reads a supplied public homepage, extracts a page title and description, and infers a broad industry when the input is missing. It does not crawl other pages or collect personal data.

### Prioritization

`scoring.py` applies an adjustable ideal-customer-profile heuristic. It returns a score, a priority tier, positive evidence, and research gaps. The explanation is treated as a first-class output.

### Outreach preparation

`outreach.py` generates a compact draft from existing account evidence. It does not send or schedule a message.

### Local CRM

`storage.py` stores reviewed records in SQLite and supports explicit pipeline status changes. The database is excluded from source control.

## Design tradeoffs

- Deterministic rules improve inspectability but cannot capture every market nuance.
- SQLite reduces setup time but is not designed for multi-user production workloads.
- Streamlit accelerates product demonstration but a production system would likely separate the API and client.

