# DocuSync AI 📄🤖

**DocuSync AI** is an intelligent, multi-document extraction, classification, and verification platform designed for Chartered Accountants (CAs), tax consultants, and financial advisory practices.

It automates the ingestion, document type classification, OCR fallback processing, structured JSON extraction, and rule-based verification auditing for financial documents (Tax Invoices, Bank Statements, etc.)—flagging discrepancies before compliance filings.

---

## 🌟 Key Features

* **Multi-Document Auto-Routing:** Automatically classifies incoming uploads into supported document schemas (`tax_invoice`, `bank_statement`).
* **Hybrid OCR Fallback Engine:** Digital PDF extraction via `pdfplumber` with automatic fallback to **Tesseract OCR** for scanned images and low-quality PDFs.
* **Deterministic Rule-Based Auditor:** Evaluates extracted metadata against Indian GSTIN regex rules, line-item mathematical sums, and tax balance logic to assign severity flags (`VERIFIED`, `NEEDS_REVIEW`, `REJECTED`).
* **Database Persistence:** Saves all processed files, structured JSON data, and audit summaries into a local SQLite database powered by **SQLModel**.
* **Streamlit CA & Client Web Portal:** Interactive drag-and-drop file uploader, JSON visualizer, compliance flag viewer, and CA audit ledger.
* **Model Context Protocol (MCP) Server:** Native `FastMCP` tools enabling AI hosts (like Claude Desktop or Cursor) to query client document statuses and metrics using natural language.

---

## 🏗️ Architecture & Stack

* **Language Runtime:** Python 3.10+ (managed via `uv`)
* **Web Framework:** FastAPI (API) & Streamlit (UI Dashboard)
* **LLM Engine & Schemas:** Groq API / OpenRouter API with `instructor` for strict Pydantic JSON schema generation
* **Document Processing:** `pdfplumber` (native PDFs) & `pytesseract` / `poppler-utils` (scanned PDFs)
* **Database ORM:** SQLModel (SQLite)
* **Agentic Protocol:** Model Context Protocol (`mcp` / `fastmcp`)

---

## 📁 Project Structure

```text
docusync-ai/
├── app/
│   ├── api/v1/                # FastAPI REST router endpoints
│   ├── core/                  # Database engine & Tesseract OCR wrapper
│   │   ├── database.py
│   │   └── ocr_engine.py
│   ├── schemas/               # Pydantic JSON schemas
│   │   ├── bank_statement.py
│   │   ├── document_type.py
│   │   ├── tax_invoice.py
│   │   └── verification.py
│   ├── services/              # Business logic services
│   │   ├── extractor_service.py
│   │   └── verification_service.py
│   ├── config.py              # Environment configuration loader
│   ├── dashboard.py           # Streamlit Web UI application
│   └── main.py                # FastAPI entrypoint
├── storage/                   # Local database & temp upload store
│   └── docusync.db
├── mcp_server.py              # Model Context Protocol server entrypoint
├── pyproject.toml             # Project dependencies and settings
├── .env                       # Environment variables (secrets)
└── README.md

```

---

## 🚀 Quickstart & Installation

### 1. System Prerequisites (WSL2 / Ubuntu)

Install system packages required for PDF rendering and OCR extraction:

```bash
sudo apt update && sudo apt install -y poppler-utils tesseract-ocr

```

### 2. Environment Setup

Clone the repository, install `uv`, and sync all project dependencies:

```bash
# Install uv package manager if not already installed
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

# Sync dependencies into virtual environment
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

## 📖 How to Use

### Option 1: Streamlit Web Dashboard (Recommended for Users & CAs)

Launch the interactive web portal to drag and drop PDFs, inspect structured outputs, and view CA audit ledgers:

```bash
uv run streamlit run app/dashboard.py

```

Open your browser at **`http://localhost:8501`**.

#### Dashboard Features:

* **Upload & Extract Tab:** Drag-and-drop a PDF. View auto-classification, extracted JSON, and real-time audit flags.
* **CA Audit Ledger Tab:** Filter historical client submissions by status (`REJECTED`, `NEEDS_REVIEW`, `VERIFIED`).
* **Summary Analytics Tab:** View aggregate metrics on processed document values and type distributions.

---

### Option 2: FastAPI REST API

Start the backend server for programmatic integration:

```bash
uv run uvicorn app.main:app --reload

```

Access the interactive OpenAPI / Swagger documentation at **`http://127.0.0.1:8000/docs`**.

#### Primary Endpoint:

* **`POST /api/v1/process-auto`**: Upload a PDF file. Automatically classifies the document, applies OCR fallback if needed, audits rules, persists data to SQLite, and returns the full JSON response.

---

### Option 3: Model Context Protocol (MCP) Server

To expose your document database to AI tools like Claude Desktop or Cursor:

#### Running the MCP Server (STDIO Mode)

```bash
uv run python mcp_server.py

```

#### Available MCP Tools:

* **`get_client_summary()`**: Returns aggregate financial and document volume metrics.
* **`get_flagged_documents(status="REJECTED")`**: Fetches all client documents matching an audit status (`REJECTED` or `NEEDS_REVIEW`) along with specific failure reasons.

#### Claude Desktop Integration Example (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "docusync": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/docusync-ai",
        "python",
        "mcp_server.py"
      ]
    }
  }
}

```

---

## 📋 Roadmap

* [x] **Phase 1:** Core FastAPI architecture, Pydantic schemas, and Groq/Instructor extraction engine.
* [x] **Phase 2:** OCR Fallback Pipeline (Tesseract) & Auto-Classification Router.
* [x] **Phase 3:** Deterministic Rule Audit Engine (GSTIN regex & mathematical verification).
* [x] **Phase 4:** SQLModel Database Persistence & FastMCP Server for natural language queries.
* [x] **Phase 5:** Interactive Streamlit Dashboard for Clients & CAs.
* [ ] **Phase 6:** Multi-Tenant Authentication & Client Isolation.
* [ ] **Phase 7:** Tally / Zoho Books XML/CSV Exports & GST Portal Cross-Checks.
* [ ] **Phase 8:** Async Queue Processing (Celery/Redis) & Docker Containerization.