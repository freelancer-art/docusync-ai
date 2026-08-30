# DocuSync AI 📄🤖

An AI-powered client document extraction and verification platform designed for Chartered Accountants, tax consultants, and financial advisory practices. 

DocuSync AI automates the ingestion, classification, data extraction, and rule-based verification of unstructured financial documents (Invoices, Bank Statements, Form 16) into validated, structured JSON schema outputs.

---

## 🏗️ Architecture & Stack

* **Language & Runtime:** Python 3.10+ (managed via `uv`)
* **Framework:** FastAPI & Pydantic v2
* **LLM Engine & Schemas:** Groq API / OpenRouter API with `instructor` for guaranteed JSON output parsing
* **Document Processing:** `pdfplumber` (native digital PDFs) & Tesseract OCR / Vision models (scanned documents)
* **Testing & Deployment:** WSL2 (Ubuntu), Google Colab (heavy model evaluation)

---

## 🛠️ Project Directory Layout

```text
docusync-ai/
├── app/
│   ├── api/v1/         # FastAPI router endpoints
│   ├── core/           # SDK configurations & engine wrappers
│   ├── schemas/        # Pydantic JSON schemas (Tax Invoices, Bank Statements)
│   ├── services/       # OCR & LLM extraction services
│   ├── config.py       # Pydantic environment configurations
│   └── main.py         # FastAPI application entrypoint
├── storage/            # Local test document store
├── pyproject.toml      # Dependency definitions
└── .env                # Local environment configuration

🚀 Quickstart Guide
1. Prerequisites (WSL Ubuntu)
Install system dependencies for PDF parsing:

Bash
sudo apt update && sudo apt install -y poppler-utils tesseract-ocr
2. Environment Setup
Install uv and sync dependencies:

Bash
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
uv sync
Configure your .env file in the root directory:

Code snippet
APP_NAME="DocuSync AI"
DEBUG=True
GROQ_API_KEY="your_groq_api_key_here"
PRIMARY_EXTRACTION_MODEL="openai/gpt-oss-20b"
3. Running the Application
Start the dev server:

Bash
uv run uvicorn app.main:app --reload
Open http://127.0.0.1:8000/docs in your browser to access the interactive Swagger API documentation.

📋 Roadmap
[x] Phase 1: Core FastAPI architecture, Pydantic schemas, and Groq/Instructor extraction engine.

[ ] Phase 2: OCR Fallback Pipeline (Tesseract / Vision) for scanned documents & multi-document router.

[ ] Phase 3: Mismatch detection engine (GSTIN verification, mathematical tax cross-checks).

[ ] Phase 4: Model Context Protocol (MCP) server integration for natural language database querying.

[ ] Phase 5: Client & CA web dashboard (Streamlit / Next.js).