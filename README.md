# Product Maintenance App

A simple web application that provides trustworthy, step-by-step user and maintenance information for specific products.

## What it does
- Collects public manuals and user guides
- Parses and indexes content per product
- Lets users ask questions and get precise answers grounded in the original documents with page/section citations
- If a product isn’t covered yet, captures a request (brand/model/email), queues ingestion, and notifies the user when available

## Repository Layout
- `frontend/` – Web UI (Next.js + TypeScript)
- `backend/` – API layer (FastAPI, Python)
- `db/` – Database migrations & schema (Postgres + pgvector)
- `docs/` – Design notes & diagrams

## Roadmap (Milestones)
1. Foundation Setup (this week)
2. Ingestion Pipeline MVP
3. QA Experience MVP
4. Product Requests & Routing
5. Evaluation & Monitoring
6. Beta Launch
7. Post-Launch Iteration
