
**Core Application (`app/`)**

* `app/main.py`: Main FastAPI entrypoint; configures middle-ware, instantiates the app, and mounts API routers (`/api/v1` and `/api/documents`).


* `app/dashboard.py`: Streamlit-based Web UI providing drag-and-drop document upload, real-time audit views, CA review ledgers, and export triggers.


* `app/config.py`: Loads environment configurations (Pydantic `BaseSettings`), API keys (Groq/OpenRouter), and global model flags from `.env`.



**API Layer (`app/api/`)**

* `app/api/documents.py`: Document upload controller handling magic-byte file validation, SQLModel persistence, and multi-tenant RBAC access controls (`GET /api/documents/{id}`, `POST /api/documents/upload`).


* `app/api/v1/extraction.py`: Extraction router exposing end-to-end PDF processing (`POST /api/v1/process-auto`).


* `app/api/v1/router.py`: Aggregator router for grouping v1 endpoints.



**Core Infrastructure (`app/core/`)**

* `app/core/database.py`: SQLModel database engine configuration, table schemas (`User`, `DocumentRecord`), input sanitization validators, and DB initialization logic.


* `app/core/security.py`: File upload security module enforcing MIME-type checks and magic-byte signature validation for PDFs, PNGs, and JPEGs.


* `app/core/ocr_engine.py`: PDF text extractor fallback utility using `pdfplumber` for digital PDFs and `pytesseract`/`poppler` for scanned images.


* `app/core/groq_client.py`: Client wrapper for structured LLM extraction using Groq/Instructor APIs.



**Domain Schemas (`app/schemas/`)**

* `app/schemas/tax_invoice.py`: Pydantic schema enforcing structured outputs for tax invoices (GSTIN, vendor info, line items, totals).


* `app/schemas/bank_statement.py`: Pydantic schema for bank statement transactions, opening/closing balances, and account metadata.


* `app/schemas/verification.py`: Pydantic model for audit rule results, compliance flags, and severity status (`VERIFIED`, `NEEDS_REVIEW`, `REJECTED`).


* `app/schemas/document_type.py`: Enum definitions for supported document schemas (`TAX_INVOICE`, `BANK_STATEMENT`).


* `app/schemas/document.py` & `app/schemas/base.py`: Base generic Pydantic request/response schemas.



**Services & Business Logic (`app/services/`)**

* `app/services/extractor_service.py`: High-level extraction orchestrator combining OCR extraction, LLM parsing, and schema mapping.


* `app/services/verification_service.py`: Rule-based audit engine performing line-item sum verifications, GST cross-checks, and flag assignments.


* `app/services/gstin_validator.py`: Regex validator verifying Indian GSTIN structure and state code checksums.


* `app/services/zoho_exporter.py`: Exporter service transforming `DocumentRecord` objects into Zoho Books compatible CSV streams with formula injection escaping.


* `app/services/tally_exporter.py`: Exporter service generating Tally XML accounting voucher imports.


* `app/services/parser.py`: Document text parser utilities.



**Test Suite & Tools (`tests/`, root)**

* `tests/test_security_hardening.py`: Unit and resilience tests covering SQL injection prevention, path traversal stripping, CSV formula escaping, floating-point precision, and malformed JSON payloads.


* `tests/test_api_endpoints.py`: Integration tests for file upload endpoints, magic-byte checks, database record creation, and RBAC isolation.


* `tests/test_audit_engine.py`: Test suite for deterministic audit rules and mathematical validation logic.


* `conftest.py`: Global Pytest configuration and shared test database fixtures.


* `mcp_server.py`: FastMCP server exposing document metrics and flagged document status tools for AI assistants (Claude Desktop/Cursor).


* `seed_test_data.py`: CLI script to populate the local database with sample client users and document records.


* `generate_test_pdf.py`: Helper utility generating sample synthetic PDFs for local development and manual testing.