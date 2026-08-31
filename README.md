# DocuSync AI 📄🤖

**DocuSync AI** is an enterprise-grade, multi-document extraction, classification, and verification platform designed for Chartered Accountants (CAs), tax consultants, and financial advisory practices.

It automates file ingestion, document type classification, OCR fallback processing, structured JSON extraction, and rule-based verification auditing for financial documents (Tax Invoices, Bank Statements, etc.)—flagging compliance discrepancies before tax filings.

---

## 🌟 Key Features & Hardening

* **Multi-Document Auto-Routing:** Automatically classifies incoming uploads into supported document schemas (`tax_invoice`, `bank_statement`).
* **Hybrid OCR Fallback Engine:** Digital PDF extraction via `pdfplumber` with automatic fallback to **Tesseract OCR** for scanned images and low-quality PDFs.
* **Deterministic Rule-Based Auditor:** Evaluates extracted metadata against Indian GSTIN regex rules, line-item mathematical sums, and tax balance logic to assign severity flags (`VERIFIED`, `NEEDS_REVIEW`, `REJECTED`).
* **Multi-Tenant Database Persistence:** Saves processed files, structured JSON data, and audit summaries into SQLite via **SQLModel** with role-based access control (RBAC) separating `CA_ADMIN` and `CLIENT` access.
* **Security Hardened File Uploads:** 
  * **Magic Byte Validation:** Validates raw file headers (`b"%PDF"`, `b"\x89PNG"`, `b"\xff\xd8\xff"`) to block executable payloads disguised as PDFs.
  * **Path Traversal Protection:** Strips directory traversal sequences (`../../`) using model-level field validators.
  * **CSV Injection Prevention:** Sanitizes export fields by escaping formula prefixes (`=`, `+`, `-`, `@`) before generating Zoho Books CSV outputs.
* **Model Context Protocol (MCP) Server:** Native `FastMCP` tools enabling AI hosts (like Claude Desktop or Cursor) to query client document statuses and metrics using natural language.

---

## 🏗️ Architecture & Stack

* **Language Runtime:** Python 3.12 (managed via `uv`)
* **Web Framework:** FastAPI (API) & Streamlit (UI Dashboard)
* **LLM Engine & Schemas:** Groq API / OpenRouter API with `instructor` for strict Pydantic JSON schema generation
* **Document Processing:** `pdfplumber` (native PDFs) & `pytesseract` / `poppler-utils` (scanned PDFs)
* **Database ORM:** SQLModel (SQLite)
* **Testing & Quality Gates:** Pytest & GitHub Actions CI

---

## 📁 Project Structure

```text
docusync-ai/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI workflow for pytest
├── app/
│   ├── api/                   # REST API routes
│   │   ├── v1/                # Extraction engine endpoints
│   │   └── documents.py       # Hardened document upload & multi-tenant routes
│   ├── core/                  # Core infrastructure & engines
│   │   ├── database.py        # SQLModel ORM models (User, DocumentRecord)
│   │   ├── ocr_engine.py      # Tesseract & pdfplumber extraction engine
│   │   ├── security.py        # Magic byte file validation & security rules
│   │   └── groq_client.py    # Structured LLM extractor wrapper
│   ├── schemas/               # Pydantic JSON schemas (Invoice, Bank Statement, Verification)
│   ├── services/              # Business logic & export services
│   │   ├── verification_service.py # Deterministic audit rule engine
│   │   ├── gstin_validator.py      # GSTIN checksum & regex validator
│   │   ├── zoho_exporter.py       # CSV injection-safe Zoho exporter
│   │   └── tally_exporter.py      # Tally XML exporter
│   ├── config.py              # Pydantic environment configuration
│   ├── dashboard.py           # Streamlit CA & Client Web Portal
│   └── main.py                # FastAPI entrypoint
├── storage/                   # Local DB and upload persistence directory
├── tests/                     # Automated test suite (20+ unit/integration tests)
│   ├── test_api_endpoints.py     # API, upload security, and RBAC tests
│   ├── test_audit_engine.py      # Audit verification rule tests
│   └── test_security_hardening.py# Security & boundary resilience tests
├── mcp_server.py              # Model Context Protocol server entrypoint
├── pyproject.toml             # Project configuration & dependencies
└── README.md

```

---

## 🚀 Quickstart & Installation

### 1. System Prerequisites (Ubuntu / WSL2)

Install system dependencies required for PDF rendering and OCR extraction:

```bash
sudo apt update && sudo apt install -y poppler-utils tesseract-ocr

```

### 2. Environment Setup

Clone the repository and sync dependencies using `uv`:

```bash
# Sync virtual environment and dependencies
uv sync

```

### 3. Configure `.env` File

Create a `.env` file in the root project directory:

```env
APP_NAME="DocuSync AI"
DEBUG=True
GROQ_API_KEY="your_actual_groq_api_key_here"
PRIMARY_EXTRACTION_MODEL="openai/gpt-oss-20b"

```

---

## 🧪 Running Tests & Quality Gates

Run the automated test suite locally:

```bash
uv run pytest -v

```

### Test Coverage Highlights:

* **Upload Security:** Tests rejection of executable binaries disguised as `.pdf` files via header signatures.
* **Path Traversal:** Verifies stripping of `../` sequences in filenames upon model assignment.
* **Multi-Tenant Isolation:** Asserts `403 Forbidden` errors when clients attempt to view documents belonging to other users.
* **CSV Formula Escaping:** Confirms prefix escaping (`'`) for cells starting with `=, +, -, @`.
* **Resilience:** Checks edge-case handling for `null`, sparse JSON payloads, and floating-point numeric precision.

---

## 📖 How to Use

### Option 1: FastAPI REST API

Start the backend server:

```bash
uv run uvicorn app.main:app --reload

```

Access Swagger UI documentation at **`http://127.0.0.1:8000/docs`**.

#### Primary Endpoints:

* **`POST /api/documents/upload`**: Validates magic bytes, sanitizes filename, and persists `DocumentRecord`.
* **`GET /api/documents/{id}`**: Multi-tenant RBAC protected document detail retrieval.
* **`POST /api/v1/process-auto`**: Ingests PDF, performs OCR fallback, runs audit rules, and returns structured JSON output.

---

### Option 2: Streamlit Web Dashboard

Launch the interactive web portal for drag-and-drop document uploads and CA review ledgers:

```bash
uv run streamlit run app/dashboard.py

```

Open your browser at **`http://localhost:8501`**.

---

### Option 3: Model Context Protocol (MCP) Server

To connect your database to AI hosts like Claude Desktop or Cursor:

```bash
uv run python mcp_server.py

```

#### Available Tools:

* **`get_client_summary()`**: Aggregates processing metrics and financial sums.
* **`get_flagged_documents(status="REJECTED")`**: Queries non-compliant client documents and audit failure reasons.

---

## 📋 Project Roadmap

* [x] **Phase 1:** Core FastAPI architecture, Pydantic schemas, and LLM extraction engine.
* [x] **Phase 2:** OCR Fallback Pipeline (Tesseract) & Auto-Classification Router.
* [x] **Phase 3:** Deterministic Rule Audit Engine (GSTIN regex & mathematical verification).
* [x] **Phase 4:** SQLModel Database Persistence & FastMCP Server integration.
* [x] **Phase 5:** Interactive Streamlit Dashboard for Clients & CAs.
* [x] **Phase 6:** API Security Hardening (Magic Bytes, Path Traversal, CSV Injection Escaping, and Pytest CI Quality Gates).
* [ ] **Phase 7:** JWT Auth Middleware Integration & Exporter Endpoint Streaming.
* [ ] **Phase 8:** Async Queue Processing (Celery/Redis) & Docker Containerization.

```