# File Usage & Module Reference 📚

This document outlines the responsibility and integration role of every file in the **DocuSync AI** repository[cite: 14].

---

### Core Application (`app/`)

* **`app/main.py`**[cite: 14]
  Main FastAPI application entrypoint. Configures CORS, sets up global middleware, initializes database tables on boot, and mounts API routers (`/api/documents` and `/api/v1`)[cite: 14].

* **`app/dashboard.py`**[cite: 14]
  Streamlit web interface for CAs and clients. Features file upload widgets, multi-tenant document ledgers, status filters, payment reconciliation controls, and instant export download triggers[cite: 14].

* **`app/config.py`**[cite: 14]
  Pydantic `BaseSettings` manager. Loads environment variables from `.env` or system environment (API keys, DB connection strings, JWT secret keys) with safe fallbacks for CI runner environments[cite: 14].

---

### API Layer (`app/api/`)

* **`app/api/documents.py`**[cite: 14]
  Document management and upload controller. Handles magic-byte file signature verification, path traversal sanitization, SQLModel record creation, thread-safe background processing dispatch, RBAC controls, and accounting export endpoints (`/export/zoho`, `/export/tally`)[cite: 10, 14].

* **`app/api/v1/extraction.py`**[cite: 14]
  Extraction router exposing direct processing endpoints (`POST /api/v1/process-auto`) for raw document text extraction, classification, and auditing[cite: 14].

* **`app/api/v1/router.py`**[cite: 14]
  Aggregator router responsible for mounting versioned v1 sub-routers[cite: 14].

---

### Core Infrastructure (`app/core/`)

* **`app/core/database.py`**[cite: 14]
  Database layer setup. Defines SQLModel entities (`User`, `DocumentRecord`), database engine connections, default seed users, and field sanitization validators[cite: 10, 14].

* **`app/core/security.py`**[cite: 14]
  Security validation engine. Enforces strict magic-byte file signature validation (PDF, PNG, JPEG) and password hashing/verification via `bcrypt`[cite: 10, 14].

* **`app/core/ocr_engine.py`**[cite: 14]
  Document text extraction engine using `pdfplumber` for digital PDFs with fallback to `pytesseract` and `poppler` for scanned images[cite: 14].

* **`app/core/groq_client.py`**[cite: 14]
  LLM client wrapper utilizing `instructor` to enforce structured JSON schema extractions via Groq or Google Gemini APIs[cite: 14].

---

### Domain Schemas (`app/schemas/`)

* **`app/schemas/tax_invoice.py`**[cite: 14]
  Pydantic schema defining structured output format for GST tax invoices (GSTIN, vendor, line items, CGST/SGST/IGST, total amounts)[cite: 14].

* **`app/schemas/bank_statement.py`**[cite: 14]
  Pydantic schema for bank statements (account metadata, transaction entries, opening/closing balances)[cite: 14].

* **`app/schemas/verification.py`**[cite: 14]
  Schema for compliance flags, audit rule check results, and document verification states (`VERIFIED`, `NEEDS_REVIEW`, `REJECTED`)[cite: 14].

* **`app/schemas/document_type.py`**[cite: 14]
  Enumerations for supported document categories (`TAX_INVOICE`, `BANK_STATEMENT`)[cite: 14].

* **`app/schemas/document.py` & `app/schemas/base.py`**[cite: 14]
  Base request and response structures used across API payloads[cite: 14].

---

### Services & Business Logic (`app/services/`)

* **`app/services/audit_engine.py`**
  Background worker service responsible for triggering document validation rules and saving updated flags and status to the database[cite: 10].

* **`app/services/verification_service.py`**[cite: 14]
  Deterministic audit engine that validates line-item math, cross-checks GST totals, validates GSTIN patterns, and computes severity levels[cite: 14].

* **`app/services/extractor_service.py`**[cite: 14]
  High-level extraction orchestrator coordinating OCR parsing, image-to-PDF rendering (`pypdfium2`), auto-classification, and vision-enabled LLM schema extractions[cite: 13, 14].

* **`app/services/gstin_validator.py`**[cite: 14]
  Regex pattern and state-code checksum validator for Indian GSTINs[cite: 14].

* **`app/services/zoho_exporter.py`**[cite: 14]
  CSV generator converting `DocumentRecord` lists into Zoho Books import formats with automatic CSV injection formula escaping[cite: 14].

* **`app/services/tally_exporter.py`**[cite: 14]
  XML voucher generator transforming processed documents into Tally ERP/Prime importable structures[cite: 14].

* **`app/services/parser.py`**[cite: 14]
  Utility functions for cleaning and parsing raw extracted document text[cite: 14].

---

### Test Suite & Utilities (`tests/`, root)

* **`tests/test_api_endpoints.py`**[cite: 14]
  Tests for upload endpoints, file signature validation, DB creation, and multi-tenant RBAC policies[cite: 10, 14].

* **`tests/test_audit_engine.py`**[cite: 14]
  Unit tests verifying deterministic mathematical audit rules and GST checks[cite: 14].

* **`tests/test_extractor_service.py`**
  Unit tests verifying image rendering, fallback mechanisms, confidence scoring, and structured extraction models.

* **`tests/test_reconciliation.py`**
  Tests validating payment reconciliation field calculations and database persistence[cite: 10].

* **`tests/test_security_hardening.py`**[cite: 14]
  Resilience tests for path traversal stripping, magic byte validation, formula injection escaping, and malformed inputs[cite: 10, 14].

* **`tests/test_auth_and_exports.py`** & **`tests/test_client_portal.py`**
  Tests verifying export stream formats (Zoho CSV/Tally XML) and portal filtering logic.

* **`conftest.py`**[cite: 14]
  Pytest configuration providing isolated in-memory database fixtures and TestClient overrides[cite: 10, 14].

* **`mcp_server.py`**[cite: 14]
  FastMCP server exposing document metrics and flagged document queries to AI hosts like Claude Desktop[cite: 14].

* **`seed_test_data.py`**[cite: 14]
  CLI utility to seed local SQLite databases with sample clients and document records[cite: 14].

* **`generate_test_pdf.py`**[cite: 14]
  Utility script to generate synthetic test PDFs for local manual testing[cite: 14].
