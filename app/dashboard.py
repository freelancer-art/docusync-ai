import json
import os
import tempfile
import streamlit as st
from sqlmodel import Session, select

from app.core.database import engine, DocumentRecord, init_db
from app.services.extractor_service import extractor_service

# Page Configuration
st.set_page_config(
    page_title="DocuSync AI - CA Portal",
    page_icon="📄",
    layout="wide"
)

# Initialize DB tables on startup
init_db()

st.title("📄 DocuSync AI: Financial Document Extraction & Audit")
st.caption("AI-Powered Ingestion, Classification, and Mismatch Detection for CAs & Tax Practitioners")

# Sidebar - Quick Stats
with st.sidebar:
    st.header("📌 System Status")
    with Session(engine) as session:
        records = session.exec(select(DocumentRecord)).all()
        total_docs = len(records)
        rejected_count = len([r for r in records if r.overall_status == "REJECTED"])
        review_count = len([r for r in records if r.overall_status == "NEEDS_REVIEW"])
        verified_count = len([r for r in records if r.overall_status == "VERIFIED"])

    st.metric("Total Ingested Documents", total_docs)
    st.metric("Verified (Passed)", verified_count)
    st.metric("Needs Review", review_count)
    st.metric("Rejected (Critical Flags)", rejected_count)

    st.divider()
    st.markdown("---")
    st.markdown("**Engine Settings**")
    st.text(f"Model: Groq / Primary")
    st.text(f"Storage: SQLite Local")

# Navigation Tabs
tab_ingest, tab_audit, tab_analytics = st.tabs([
    "📤 Upload & Extract",
    "📋 CA Audit Ledger",
    "📊 Summary Analytics"
])

# ---------------------------------------------------------
# TAB 1: UPLOAD & EXTRACT
# ---------------------------------------------------------
with tab_ingest:
    st.header("Upload Document for Parsing")
    uploaded_file = st.file_uploader(
        "Choose a Tax Invoice or Bank Statement PDF",
        type=["pdf"]
    )

    if uploaded_file is not None:
        if st.button("Process Document", type="primary"):
            with st.spinner("Extracting text, running OCR fallback, and evaluating audit rules..."):
                # Save uploaded file temporarily for engine ingestion
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name

                try:
                    result = extractor_service.process_document(
                        file_path=tmp_path,
                        filename=uploaded_file.name
                    )

                    st.success(f"Processing Complete! Document classified as **{result['document_type']}**.")

                    # Status Banner
                    audit_status = result["audit_summary"]["overall_status"]
                    if audit_status == "VERIFIED":
                        st.success(f"Audit Status: {audit_status}")
                    elif audit_status == "NEEDS_REVIEW":
                        st.warning(f"Audit Status: {audit_status}")
                    else:
                        st.error(f"Audit Status: {audit_status}")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("Extracted JSON Payload")
                        st.json(result["data"])

                    with col2:
                        st.subheader("Audit & Compliance Flags")
                        flags = result["audit_summary"].get("flags", [])
                        if not flags:
                            st.info("No compliance or mathematical issues detected.")
                        else:
                            for flag in flags:
                                sev = flag.get("severity")
                                msg = f"**[{flag.get('code')}]** ({flag.get('field')}): {flag.get('message')}"
                                if sev == "CRITICAL":
                                    st.error(msg)
                                elif sev == "WARNING":
                                    st.warning(msg)
                                else:
                                    st.info(msg)

                except Exception as e:
                    st.error(f"Extraction Error: {str(e)}")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

# ---------------------------------------------------------
# TAB 2: CA AUDIT LEDGER
# ---------------------------------------------------------
with tab_audit:
    st.header("Client Document Audit Ledger")
    
    status_filter = st.selectbox(
        "Filter by Status",
        ["ALL", "REJECTED", "NEEDS_REVIEW", "VERIFIED"]
    )

    with Session(engine) as session:
        query = select(DocumentRecord)
        if status_filter != "ALL":
            query = query.where(DocumentRecord.overall_status == status_filter)
        records = session.exec(query).all()

    if not records:
        st.info("No records match the selected filter.")
    else:
        for rec in records:
            with st.expander(f"ID #{rec.id} | {rec.filename} | Status: {rec.overall_status} | Vendor: {rec.vendor_name or 'N/A'}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Document Type:** {rec.document_type}")
                c2.write(f"**Invoice Number:** {rec.invoice_number or 'N/A'}")
                c3.write(f"**Total Amount:** ₹{rec.total_amount:,.2f}" if rec.total_amount else "**Total Amount:** N/A")

                st.markdown("**Audit Flags:**")
                flags = json.loads(rec.audit_flags_json)
                if not flags:
                    st.write("✓ Zero flags reported")
                else:
                    for f in flags:
                        st.caption(f"⚠️ [{f.get('severity')}] {f.get('code')}: {f.get('message')}")

                st.markdown("**Raw Structured Data:**")
                st.json(json.loads(rec.raw_json_data))

# ---------------------------------------------------------
# TAB 3: SUMMARY ANALYTICS
# ---------------------------------------------------------
with tab_analytics:
    st.header("Executive Summary & Document Pipeline Metrics")
    
    with Session(engine) as session:
        all_records = session.exec(select(DocumentRecord)).all()

    if all_records:
        total_val = sum(r.total_amount or 0.0 for r in all_records)
        doc_types = {}
        for r in all_records:
            doc_types[r.document_type] = doc_types.get(r.document_type, 0) + 1

        m1, m2 = st.columns(2)
        m1.metric("Cumulative Value Processed", f"₹{total_val:,.2f}")
        m2.metric("Supported Document Types", len(doc_types))

        st.subheader("Processed Breakdown by Document Type")
        st.bar_chart(doc_types)
    else:
        st.info("No document data available for analytics yet.")