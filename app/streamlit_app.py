import base64
import json
import os

import requests
import streamlit as st
from sqlmodel import Session, select

from app.core.database import DocumentRecord, engine

# Page configuration
st.set_page_config(
    page_title="DocuSync - Audit & Verification Portal",
    page_icon="📄",
    layout="wide",
)

UPLOAD_DIR = "storage/uploads"


def render_pdf_preview(filename: str):
    """Renders PDF directly inside Streamlit using base64 HTML embedding."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        st.warning(f"Source file `{filename}` not found on disk.")
        return

    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode("utf-8")

    pdf_display = f"""
        <iframe src="data:application/pdf;base64,{base64_pdf}" 
                width="100%" height="650px" type="application/pdf">
        </iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)


def main():
    st.title("📄 DocuSync Audit & Review Dashboard")
    st.caption("Human-in-the-loop review interface for financial document extractions.")

    # Top-level KPI Summary
    with Session(engine) as session:
        all_docs = session.exec(select(DocumentRecord)).all()
        total_count = len(all_docs)
        needs_review_count = sum(
            1 for d in all_docs if d.overall_status == "NEEDS_REVIEW"
        )
        verified_count = sum(1 for d in all_docs if d.overall_status == "VERIFIED")
        total_val = sum(d.total_amount or 0.0 for d in all_docs)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Documents", total_count)
    col2.metric("Needs Review", needs_review_count, delta_color="inverse")
    col3.metric("Verified", verified_count)
    col4.metric("Total Portfolio Value", f"₹{total_val:,.2f}")

    st.divider()

    # Document Selection Sidebar
    st.sidebar.header("Filter & Queue")
    status_filter = st.sidebar.selectbox(
        "Filter Status", ["NEEDS_REVIEW", "VERIFIED", "REJECTED", "ALL"]
    )

    with Session(engine) as session:
        query = select(DocumentRecord)
        if status_filter != "ALL":
            query = query.where(DocumentRecord.overall_status == status_filter)
        records = session.exec(query).all()

    if not records:
        st.info("No documents found for the selected status filter.")
        return

    doc_options = {
        f"ID #{d.id} | {d.vendor_name or 'Unassigned'} | {d.filename}": d.id
        for d in records
    }
    selected_label = st.sidebar.selectbox("Select Document", list(doc_options.keys()))
    selected_id = doc_options[selected_label]

    # Fetch fresh record details
    with Session(engine) as session:
        doc = session.get(DocumentRecord, selected_id)

        # Workstation Layout: 2 Columns (PDF View left, Audit Form right)
        left_col, right_col = st.columns([1, 1])

        with left_col:
            st.subheader("Source Document View")
            render_pdf_preview(doc.filename)

        with right_col:
            st.subheader("Extraction Audit & Corrections")

            # Status and Flags Alert Box
            if doc.overall_status == "NEEDS_REVIEW":
                st.error(f"Status: {doc.overall_status}")
            else:
                st.success(f"Status: {doc.overall_status}")

            flags = json.loads(doc.audit_flags_json) if doc.audit_flags_json else []
            if flags:
                st.warning(f"**Audit Flags Triggered ({len(flags)}):**")
                for flag in flags:
                    st.write(f"- ⚠️ `{flag}`")
            else:
                st.info("No audit flags raised for this record.")

            st.divider()

            # Manual Correction Form
            with st.form(key="audit_review_form"):
                vendor_name = st.text_input(
                    "Vendor Name", value=doc.vendor_name or ""
                )
                invoice_number = st.text_input(
                    "Invoice Number", value=doc.invoice_number or ""
                )
                total_amount = st.number_input(
                    "Total Amount (₹)",
                    value=float(doc.total_amount or 0.0),
                    step=0.01,
                )
                payment_status = st.selectbox(
                    "Payment Status",
                    ["UNPAID", "PAID", "PARTIAL"],
                    index=["UNPAID", "PAID", "PARTIAL"].index(doc.payment_status),
                )
                auditor_notes = st.text_area(
                    "Auditor Notes", value=doc.auditor_notes or ""
                )

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    approve_submit = st.form_submit_button("✅ Verify & Approve")
                with col_btn2:
                    reject_submit = st.form_submit_button("❌ Reject Document")

            # Form Action Handlers
            if approve_submit or reject_submit:
                doc.vendor_name = vendor_name
                doc.invoice_number = invoice_number
                doc.total_amount = total_amount
                doc.payment_status = payment_status
                doc.auditor_notes = auditor_notes

                if approve_submit:
                    doc.overall_status = "VERIFIED"
                    doc.audit_flags_json = json.dumps([])
                elif reject_submit:
                    doc.overall_status = "REJECTED"

                session.add(doc)
                session.commit()
                st.success("Document record updated successfully!")
                st.rerun()


if __name__ == "__main__":
    main()