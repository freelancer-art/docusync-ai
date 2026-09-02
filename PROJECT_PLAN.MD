# DocuSync AI — Implementation & Roadmap Tracker

**Project Goal:** Multi-Tenant CA Portal for automated document extraction, AI audit verification, multi-tenant client management, and accounting exports (Tally & Zoho Books).

---

## 📊 Quick Status Summary

- **Core Infrastructure & UI:** Completed ✅
- **Phase 3: AI Vision Extraction Engine:** Completed ✅[cite: 13]
- **Phase 4: AI Anomaly Engine & RAG Chat Assistant:** NEXT FOCUS 🚀
- **Phase 1: Persistence & Supabase Storage:** Deferred ⏸️
- **Phase 2: Multi-Tenant User Management:** Deferred ⏸️

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

## 🎯 Phase 4: AI Anomaly Engine & RAG Chat Assistant (Next Steps)

**Goal:** Elevate CA auditing with automated arithmetic checks and a natural-language ledger assistant.

* [ ] **AI Anomaly Detection (`app/services/audit_engine.py`)**[cite: 13]
  * [ ] **Arithmetic Verification:** Auto-flag discrepancies where `Taxable + Tax != Total`.
  * [ ] **Tax Structure Check:** Verify Inter-state (IGST) vs. Intra-state (CGST + SGST) based on vendor/client GSTIN state codes.
  * [ ] **Duplicate Billing Detection:** Scan database for duplicate `(vendor_name, invoice_number)` combinations.
* [ ] **"Ask DocuSync AI" (RAG Chat Assistant)**
  * [ ] Add interactive chat component in Streamlit.
  * [ ] Support natural language queries over tenant ledgers (e.g., *"What is the total GST credit available for Q2?"*).
  * [ ] Synthesize direct answers from structured SQL queries over `DocumentRecord` database.

---

## ⏸️ Phase 1: Persistence & Storage Migration (Deferred)

* [ ] Migrate from local disk (`storage/uploads/`) to Supabase Bucket (`docusync-documents`)[cite: 10, 13].
* [ ] Generate time-limited signed URLs for secure PDF view/download in UI.

---

## ⏸️ Phase 2: Dynamic User Management (Deferred)

* [ ] Add `👥 User Management` tab for `CA_ADMIN` to dynamically register CA & Client accounts.
* [ ] Client account assignment dropdowns and account metrics.

---

## 🧹 Maintenance & Cleanup

* [x] Remove compiled `__pycache__` directories and temporary script dumps[cite: 13].
* [x] Verify directory tree structure and dependencies (`pyproject.toml`, `uv.lock`)[cite: 13].