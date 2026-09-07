# DocuSync AI — Implementation & Roadmap Tracker

**Project Goal:** Multi-Tenant CA Portal for automated document extraction, AI audit verification, multi-tenant client management, and accounting exports (Tally & Zoho Books).

---

## 📊 Quick Status Summary

- **Core Infrastructure & UI:** Completed ✅
- **Phase 3: AI Vision Extraction Engine:** Completed ✅[cite: 13]
- **Phase 4: AI Anomaly Engine & RAG Chat Assistant:** Completed ✅
- **Phase 5: MCP Accounting Agent Tooling:** Core complete ✅
- **Phase 1: Persistence & Supabase Storage:** Supabase-ready ✅
- **Phase 2: Multi-Tenant User Management:** Completed ✅

---

## Code Review Findings & Impacted Areas

Review date: 2026-09-06

Test baseline:

- `pytest` is not available directly on the shell path.
- `uv run --extra dev pytest` passes after connector, storage, diagnostics, and documentation coverage work: **101 passed, 0 warnings**.
- `uv run --extra dev ruff check app tests` passes.
- `uv run --extra dev ruff format --check app tests` passes.
- `git diff --check` passes.

### High Priority

* [x] **Secure upload endpoints and tenant ownership**
  * Impacted files: `app/api/v1/extraction.py`, `app/core/security.py`, `app/core/database.py`, `app/worker.py`, upload tests.
  * Current issue: `/api/v1/process-auto` and `/api/v1/upload` only validate filename extensions, do not enforce magic-byte validation, and build filesystem paths from raw uploaded filenames.
  * Current issue: async upload is unauthenticated and creates records without `client_id`, breaking tenant ownership and portal visibility.
  * Implemented outcome: upload/extraction endpoints authenticate users, sanitize filenames before disk writes, validate raw bytes before save/process, bind persisted records to the active tenant, and cover the real external endpoints with tests.

* [x] **Fix real FastAPI CORS configuration**
  * Impacted files: `app/main.py`, `app/config.py`, security header/CORS tests.
  * Current issue: the real app adds wildcard CORS before adding stricter security middleware, while tests validate only an isolated mock app.
  * Implemented outcome: wildcard production CORS was removed, allowed origins are configured through settings, and real app CORS behavior is covered by tests.

* [x] **Constrain Streamlit RAG SQL execution**
  * Impacted files: `app/dashboard.py`, RAG assistant tests, any shared RAG SQL helper introduced.
  * Current issue: the dashboard executes raw LLM-generated SQL after only checking that it starts with `SELECT`; tenant scoping is injected with brittle string replacement.
  * Implemented outcome: SQL validation/scoping is centralized, multi-statement and mutation attempts are rejected, tenant scope uses bound parameters, and admin/client SQL behavior is covered by tests.

### Medium Priority

* [x] **Normalize payment status contract**
  * Impacted files: `app/services/reconciliation.py`, `app/core/database.py`, `README.md`, dashboard filters/analytics, reconciliation tests.
  * Current issue: docs refer to `PARTIAL`, code emits `PARTIALLY_PAID`, and defaults use `UNPAID`.
  * Implemented outcome: reconciliation now emits `PARTIAL`, docs match the API contract, non-positive payments return `400`, duplicate invoice numbers return `409`, and payment tests cover these paths.

* [x] **Resolve duplicate Celery task implementations**
  * Impacted files: `app/worker.py`, `app/tasks/extraction_tasks.py`, deployment commands, Celery tests.
  * Current issue: two tasks named `process_document_task` exist with different call signatures and persistence behavior.
  * Implemented outcome: the stale `app/tasks/extraction_tasks.py` implementation was removed, leaving `app/worker.py` as the single task contract covered by Celery tests.

* [x] **Route export endpoints through exporter services**
  * Impacted files: `app/api/documents.py`, `app/services/zoho_exporter.py`, `app/services/tally_exporter.py`, export tests.
  * Current issue: API export endpoints hand-roll CSV/XML and bypass service-level escaping/mapping behavior.
  * Implemented outcome: export endpoints now call `zoho_exporter` and `tally_exporter`, and endpoint tests verify service-format output and CSV formula escaping.

* [x] **Harden config parsing and startup defaults**
  * Impacted files: `app/config.py`, `.env` handling, CI/deployment config, tests.
  * Current issue: unsupported boolean strings can fail app import before tests or startup begin.
  * Implemented outcome: `DEBUG` accepts deployment labels like `release`/`production` as false and `development` as true, with regression tests.

* [x] **Remove or gate default credentials and fallback secrets**
  * Impacted files: `app/core/security.py`, `app/config.py`, `app/core/database.py`, deployment docs.
  * Current issue: fallback JWT secrets and default seeded admin credentials are present in code.
  * Implemented outcome: JWT dev fallback is debug-only, production requires `SECRET_KEY` or `JWT_SECRET_KEY`, and default admin seeding is skipped in production unless explicit initial credentials are configured.

* [x] **Fix AI anomaly schema/consumer mismatch**
  * Impacted files: `app/schemas/verification.py`, `app/services/audit_engine.py`, AI audit tests.
  * Current issue: schema defines `detected_flags`, while audit engine checks `detected_anomalies`.
  * Implemented outcome: audit engine now consumes `detected_flags` and applies AI-generated flags to final review status.

### Low Priority / Hardcoding Cleanup

* [x] **Centralize paths, ports, dates, and model names**
  * Impacted files: `app/api/v1/extraction.py`, `app/worker.py`, `app/services/storage_service.py`, `app/services/tally_exporter.py`, `app/services/parser.py`, `Dockerfile`, `docker-compose.yml`, `start.sh`, `.devcontainer/devcontainer.json`.
  * Examples: `storage/uploads`, `20260101`, `gemini-2.5-flash`, local ports `8000`/`8501`/`10000`.
  * Implemented outcome: runtime code now reads upload paths, public storage prefix, vision model, Tally fallback date, API host/port, and deployment port defaults from settings/environment. Docker and compose port bindings are parameterized.
  * Remaining literal matches are intentional settings defaults, docs/deployment examples, or test assertions.

### Test Coverage Gaps

* [x] Real `/api/v1/upload` and `/api/v1/process-auto`: authentication, malicious filenames, magic bytes, file cleanup, Celery dispatch.
* [x] Real production CORS behavior from `app.main`.
* [x] Export endpoint parity with exporter service behavior, especially CSV formula escaping.
* [x] Streamlit dashboard workflows: auth, upload, audit edit, exports, RAG SQL, account management. RAG SQL guard is unit-tested, underlying upload/export/account APIs are covered, and a Streamlit `AppTest` smoke test verifies the dashboard auth entry workflow renders.
* [x] MCP tools in `app/mcp_server.py`.
* [x] Supabase storage mode and local fallback behavior.
* [x] Readiness endpoint `/ready`, including Redis unavailable/available paths.
* [x] Gemini parser module `app/services/parser.py`.
* [x] Negative payment scenarios: negative payments, overpayments, duplicate invoice numbers, authorization boundaries.
* [x] Additional document API forbidden/not-found edge cases.

---

## ✅ Phase 0: System Architecture & Core Engine (Completed)

* [x] **Database Schema Setup (`app/core/database.py`)**[cite: 13]
  * [x] `User` model with Bcrypt password hashing and roles (`CA_ADMIN`, `CLIENT`).
  * [x] `DocumentRecord` model with audit flags, raw JSON data, and `created_at` timestamp.
  * [x] Explicit bidirectional relationship mapping (`User.documents` ↔ `DocumentRecord.owner`).
* [x] **Core Accounting Exporters (`app/services/`)**[cite: 13]
  * [x] Tally Purchase Voucher XML exporter (`tally_exporter.py`).
  * [x] Zoho Books Bills CSV exporter (`zoho_exporter.py`).
* [x] **Audit & Validation Tools (`app/services/`)**[cite: 13]
  * [x] Modulus-36 GSTIN format, state code, and PAN validator (`gstin_validator.py`).
  * [x] Rule-based audit engine (`audit_engine.py`).
* [x] **UI & Role-Based Access Control (`app/dashboard.py`)**
  * [x] Streamlit authentication interface.
  * [x] Role-Based Scoping: `CA_ADMIN` views all tenant records; `CLIENT` views isolated account records.
  * [x] Auditor edit and override panel with manual status overrides (`VERIFIED`, `NEEDS_REVIEW`, `REJECTED`).
* [x] **Deployment Orchestration (`start.sh` & `streamlit_app.py`)**[cite: 12, 13]
  * [x] Dual-process launch: Background Celery worker + Foreground Uvicorn/Streamlit web server[cite: 12].
  * [x] Dynamic `$PORT` binding for cloud host compatibility (Render)[cite: 12].

---

## ✅ Phase 3: AI Vision Extraction Engine (Completed)

* [x] **Vision Processing Pipeline (`app/services/extractor_service.py`)**[cite: 13]
  * [x] PDF rendering pipeline via `pypdfium2` for scanned/multimodal document extraction[cite: 13].
  * [x] Structured vision prompt targeting key tax attributes (GSTIN, totals, line items, dates)[cite: 13].
  * [x] Fallback integration supporting both Groq text LLMs and Gemini vision models[cite: 12, 13].
* [x] **Structured Output Validation**[cite: 13]
  * [x] Output parsing enforced via Pydantic schemas (`TaxInvoiceSchema` & `BankStatementSchema`)[cite: 13].
  * [x] Key alignment and fallback confidence scoring for incomplete OCR outputs[cite: 13].

---

## ✅ Phase 4: AI Anomaly Engine & RAG Chat Assistant (Completed)

**Goal:** Elevate CA auditing with automated arithmetic checks and a natural-language ledger assistant.

* [x] **AI Anomaly Detection (`app/services/audit_engine.py`, `app/services/verification_service.py`)**[cite: 13]
  * [x] **Arithmetic Verification:** Auto-flags discrepancies where `Taxable + Tax != Total`.
  * [x] **Tax Structure Check:** Verifies Inter-state (IGST) vs. Intra-state (CGST + SGST) based on vendor/client GSTIN state codes.
  * [x] **Duplicate Billing Detection:** Scans the database for duplicate `(vendor_name, invoice_number)` combinations.
* [x] **"Ask DocuSync AI" (RAG Chat Assistant)**
  * [x] Interactive chat component exists in Streamlit.
  * [x] Natural-language tenant ledger queries are supported through LLM-generated SQL.
  * [x] SQL execution is constrained by `build_safe_ledger_query`, tenant scoped with bound parameters, and synthesized into direct answers.

---

## ✅ Phase 5: MCP Accounting Agent Tooling

**Goal:** Expose DocuSync accounting workflows as safe, structured tools that AI agents can call without raw database access.

* [x] **Stabilize Existing MCP Tools (`app/mcp_server.py`)**
  * [x] Return structured JSON for document lookup, flagged records, and financial summaries.
  * [x] Handle missing documents and malformed JSON without crashing the MCP server.
  * [x] Cover the MCP server surface with isolated database tests.
* [x] **Add AI-Useful Read/Export Tools**
  * [x] `validate_gstin(gstin)` for GSTIN format/checksum/state/PAN validation.
  * [x] `search_documents(...)` with client, status, vendor, invoice, date, and bounded limit filters.
  * [x] `explain_audit_flags(doc_id)` with severity counts and recommended review action.
  * [x] `find_duplicate_invoices(client_id)` to identify duplicate vendor/invoice combinations.
  * [x] `summarize_client_tax_position(...)` for totals, status counts, and estimated GST credit.
  * [x] `prepare_accounting_export(...)` for Tally XML and Zoho CSV export previews.
* [x] **Guarded Mutation Tools**
  * [x] Add explicit confirmation-token flow before mutating tools such as status override.
  * [x] Add audit logging for every MCP tool invocation, including actor, tool name, redacted arguments summary, and outcome.
* [x] **Replace Streamlit Raw SQL RAG Path**
  * [x] Route assistant answers through the MCP-style tool layer instead of direct database execution.
  * [x] Add tool-call orchestration tests for tenant-scoped accounting questions.
* [x] **External MCP/Connector Intake**
  * [x] Define a provider-neutral connector interface for Google Drive, Dropbox, and Gmail adapters.
  * [x] Implement Google Drive listing/download with service-account and access-token authentication constructors.
  * [x] Add deterministic Dropbox and Gmail mock adapters for development and tests.
  * [x] Enforce connector binding to the requested tenant and deduplicate by provider source ID and content hash.
  * [x] Add isolated ingestion, authentication, tenant-boundary, and duplicate-file tests.
  * [x] Keep Google Drive, Dropbox, and Gmail intake optional and disabled by default; production provider adapters remain deferred.

---

## ✅ Phase 1: Persistence & Storage Migration

* [x] Add Supabase Storage mode with local disk (`storage/uploads/`) fallback.
* [x] Generate bounded, time-limited signed URLs through `GET /api/documents/{id}/file-url`.
* [x] Supabase storage mode and local fallback behavior are centralized in `StorageService` and covered by tests.

---

## ✅ Phase 2: Dynamic User Management (Completed)

* [x] Add `👥 User Management` tab for `CA_ADMIN` to dynamically register CA & Client accounts.
* [x] Client account assignment dropdowns and account metrics.

---

## 🧹 Maintenance & Cleanup

* [x] Remove compiled `__pycache__` directories and temporary script dumps[cite: 13].
* [x] Verify directory tree structure and dependencies (`pyproject.toml`, `uv.lock`)[cite: 13].

## 🔍 Quality, Debugging & Documentation Review

* [x] Add configurable structured JSON logging with correlation IDs and replace startup `print()` diagnostics.
* [x] Add module-level purpose docstrings and public API docstrings to the runtime surfaces most likely to be extended or operated.
* [x] Document local setup, roles, uploads, extraction, audit review, payments, exports, MCP tools, connectors, storage, troubleshooting, and deployment in `USER_MANUAL.md`.
* [x] Add tests and lint checks to the documented development workflow.
* [x] Link the complete user manual from the primary project documentation.
* [x] Add a reusable development workflow checklist and pull-request template so the review criteria are repeated for every implementation.
* [x] Align pre-commit with the project Ruff version and add whitespace validation.
* [ ] Continue incremental docstring coverage for legacy internal helpers when those modules are next changed.
* [ ] Add production observability integration (central log sink, metrics, and alerting) before launch.

## ⚙️ Operations Follow-up

* [x] Add disabled-by-default Celery beat scheduling for registered connector sync.
* [x] Add Alembic migration for connector binding and imported-file tables.
* [x] Remove Passlib and deprecated SQLModel query warnings.
* [x] Add vendor-neutral request metrics, correlation-based trace context, and optional readiness alert webhook.
* [ ] Configure a production metrics/logging/tracing backend and alert routes during deployment.

## 🚀 Product Features: First Market Slice

**Agreed scope:** implement document categorization first; defer reminders and bank reconciliation until the categorization contract is stable. The first input scope is invoices and bank statements, with PDF, PNG, JPEG, and UTF-8 CSV support. Rules decide the initial classification; AI remains an optional suggestion layer.

* [x] Define initial categories: `TAX_INVOICE`, `BANK_STATEMENT`, and `UNKNOWN`.
* [x] Add explainable keyword classification with confidence score and reasoning.
* [x] Route unknown/low-confidence documents to `NEEDS_REVIEW`.
* [x] Accept UTF-8 CSV input for bank-statement workflows while retaining binary magic-byte checks for PDF/images.
* [x] Persist classification confidence and reasoning on `DocumentRecord`.
* [x] Normalize common bank CSV columns, dates, signed amounts, balances, references, and malformed-row reports.
* [x] Add a CA-admin review queue view for unknown/low-confidence documents.
* [x] Add a protected rerun-classification action; category correction is deferred by decision.
* [x] Add initial automated bank reconciliation using normalized uploaded bank statements, with tenant-scoped persistence, deterministic matching, ambiguity suggestions, and idempotent reruns.
* [x] Add reconciliation approval workflow and apply approved bank matches to invoice payment totals with idempotency and audit metadata.
* [x] Add tenant-scoped compliance calendar and unsent client reminder drafts with completion tracking and access controls.
* [x] Add reminder delivery channels and scheduled notifications with CA approval, mock/SMTP providers, Celery scheduling, retries, and delivery status tracking.
* [ ] Add official-source tax RAG assistant.
* [ ] Add explainable ITC anomaly/risk scoring.
