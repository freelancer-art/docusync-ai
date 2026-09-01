import io
import json
import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from app.core.database import DocumentRecord, User, UserRole, engine, init_db
from app.services.extractor_service import extractor_service
from app.services.gstin_validator import gstin_validator
from app.services.tally_exporter import tally_exporter
from app.services.zoho_exporter import zoho_exporter

# Streamlit Page Setup
st.set_page_config(
    page_title="DocuSync AI - Multi-Tenant Portal", page_icon="🔒", layout="wide"
)

# Ensure database tables are created
init_db()

# Session State Initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

# ---------------------------------------------------------
# AUTHENTICATION SCREEN
# ---------------------------------------------------------
if not st.session_state.authenticated:
    st.title("🔒 DocuSync AI Sign In")
    col1, col2 = st.columns([1, 2])

    with col1:
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")

        if st.button("Login", type="primary"):
            with Session(engine) as session:
                user = session.exec(
                    select(User).where(User.username == username_input)
                ).first()
                if user and user.verify_password(password_input):
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

        st.info(
            "Demo Logins:\n- CA Admin: `ca_admin` / `admin123`\n- Client 1: `acme_corp` / `client123`\n- Client 2: `apex_tech` / `client123`"
        )
    st.stop()

# ---------------------------------------------------------
# AUTHENTICATED CONTEXT & RBAC SCOPING
# ---------------------------------------------------------
user: User = st.session_state.user
is_admin: bool = user.role == UserRole.CA_ADMIN

# Sidebar & RBAC Scoped Metrics
with st.sidebar:
    st.markdown(f"### 👤 Logged in: **{user.full_name}**")
    st.caption(f"Role: `{user.role}`")

    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.rerun()

    st.divider()

    with Session(engine) as session:
        query = select(DocumentRecord)
        if not is_admin:
            query = query.where(DocumentRecord.client_id == user.id)

        records = session.exec(query).all()

        total_docs = len(records)
        rejected_count = len([r for r in records if r.overall_status == "REJECTED"])
        review_count = len([r for r in records if r.overall_status == "NEEDS_REVIEW"])
        verified_count = len([r for r in records if r.overall_status == "VERIFIED"])

    st.metric("Visible Documents", total_docs)
    st.metric("Verified", verified_count)
    st.metric("Needs Review", review_count)
    st.metric("Rejected Flags", rejected_count)

st.title(
    f"📄 DocuSync AI: {'CA Master Ledger' if is_admin else 'Client Document Portal'}"
)

tab_ingest, tab_audit, tab_analytics = st.tabs(
    ["📤 Upload & Extract", "📋 Audit Ledger", "📊 Analytics"]
)

# ---------------------------------------------------------
# TAB 1: UPLOAD & EXTRACT
# ---------------------------------------------------------
with tab_ingest:
    st.header("Upload Document")

    if is_admin:
        with Session(engine) as session:
            clients = session.exec(
                select(User).where(User.role == UserRole.CLIENT)
            ).all()
            client_options = {c.full_name: c.id for c in clients}

        if client_options:
            selected_client_name = st.selectbox(
                "Assign Upload to Client Account", list(client_options.keys())
            )
            target_client_id = client_options[selected_client_name]
        else:
            st.warning("No client accounts found. Please seed client users.")
            target_client_id = None
    else:
        target_client_id = user.id
        st.caption(f"Target Account: **{user.full_name}** (ID: {user.id})")

    uploaded_file = st.file_uploader(
        "Choose a Tax Invoice or Bank Statement PDF", type=["pdf"]
    )

    if (
        uploaded_file is not None and target_client_id is not None
    ) and st.button("Process & Save", type="primary"):
        with st.spinner("Processing & auditing document..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            try:
                # 1. Run extraction service
                extraction_result = extractor_service.process_document(
                    file_input=tmp_path,
                    filename=uploaded_file.name,
                )

                # 2. Derive audit flags & default status
                flags = []
                confidence = extraction_result.get("confidence_score", 1.0)
                if confidence < 0.7:
                    flags.append(
                        {
                            "code": "LOW_CONFIDENCE",
                            "severity": "MEDIUM",
                            "message": f"Extraction confidence score low: {confidence}",
                        }
                    )

                vendor_name = extraction_result.get("vendor_name")
                total_amount = extraction_result.get("total_amount")

                if not vendor_name or vendor_name == "Extracted Vendor":
                    flags.append(
                        {
                            "code": "MISSING_VENDOR",
                            "severity": "HIGH",
                            "message": "Vendor name requires manual verification.",
                        }
                    )

                initial_status = "NEEDS_REVIEW" if flags else "VERIFIED"

                # 3. Create and persist DocumentRecord in SQLModel session
                new_record = DocumentRecord(
                    client_id=target_client_id,
                    filename=uploaded_file.name,
                    document_type=extraction_result.get("doc_type", "TAX_INVOICE"),
                    vendor_name=vendor_name,
                    invoice_number=extraction_result.get("invoice_number"),
                    total_amount=float(total_amount or 0.0),
                    payment_status="UNPAID",
                    overall_status=initial_status,
                    raw_json_data=json.dumps(extraction_result),
                    audit_flags_json=json.dumps(flags),
                    created_at=datetime.utcnow(),
                )

                with Session(engine) as session:
                    session.add(new_record)
                    session.commit()
                    session.refresh(new_record)

                st.success(
                    f"Successfully processed and saved Record ID #{new_record.id} for Tenant ID #{target_client_id}!"
                )
                st.json(extraction_result)

            except Exception as e:
                st.error(f"Error processing document: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

# ---------------------------------------------------------
# TAB 2: AUDIT LEDGER
# ---------------------------------------------------------
with tab_audit:
    st.header("Document Audit Ledger")

    # 1. GSTIN VERIFICATION TOOL
    with st.expander("🔍 Quick GSTIN Verification Tool"):
        st.caption(
            "Verify any Vendor GSTIN format, state code, PAN extraction, and Modulus 36 checksum validity."
        )
        col_gst_in, col_gst_btn = st.columns([3, 1])
        input_gstin = col_gst_in.text_input(
            "Enter GSTIN to Verify", value="27AAACT2727Q1ZW", key="quick_gstin_input"
        )

        if col_gst_btn.button("Verify GSTIN", type="secondary", key="quick_gstin_btn"):
            res = gstin_validator.verify_gstin(input_gstin)
            if res["valid"]:
                st.success(
                    f"✅ **Valid GSTIN** | State: **{res['state_name']} ({res['state_code']})** | "
                    f"PAN: **{res['extracted_pan']}** | Status: **{res['registration_status']}**"
                )
            else:
                st.error(f"❌ **Invalid GSTIN**: {res['error']}")

    st.divider()

    # 2. FILTER & EXPORT LAYOUT
    col_filter, col_export_csv, col_export_xlsx = st.columns([2, 1, 1])
    status_filter = col_filter.selectbox(
        "Filter by Status",
        ["ALL", "REJECTED", "NEEDS_REVIEW", "VERIFIED"],
        key="audit_status_filter",
    )

    # 3. DATABASE QUERY & AUDIT LEDGER RENDER
    with Session(engine) as session:
        query = select(DocumentRecord)

        if not is_admin:
            query = query.where(DocumentRecord.client_id == user.id)

        if status_filter != "ALL":
            query = query.where(DocumentRecord.overall_status == status_filter)

        records = session.exec(query).all()

        if not records:
            st.info("No document records accessible under current filter/account.")
        else:
            export_rows = []
            for r in records:
                flags = json.loads(r.audit_flags_json) if r.audit_flags_json else []
                flag_codes = ", ".join([f.get("code", "") for f in flags])

                # Fetch Client User directly
                owner_user = session.get(User, r.client_id) if r.client_id else None
                client_name = owner_user.full_name if owner_user else "Unassigned"

                created_str = (
                    r.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if getattr(r, "created_at", None)
                    else ""
                )

                export_rows.append(
                    {
                        "Record ID": r.id,
                        "Client Name": client_name,
                        "Filename": r.filename,
                        "Document Type": r.document_type,
                        "Invoice Number": r.invoice_number or "N/A",
                        "Vendor Name": r.vendor_name or "N/A",
                        "Total Amount (INR)": r.total_amount or 0.0,
                        "Audit Status": r.overall_status,
                        "Audit Flags": flag_codes or "None",
                        "Auditor Notes": r.auditor_notes or "",
                        "Created At": created_str,
                    }
                )

            df_export = pd.DataFrame(export_rows)

            # CSV Stream
            csv_data = df_export.to_csv(index=False).encode("utf-8")
            col_export_csv.download_button(
                label="📥 Export CSV",
                data=csv_data,
                file_name=f"docusync_audit_report_{status_filter.lower()}.csv",
                mime="text/csv",
                key="download_csv",
            )

            # Excel Stream
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Audit Ledger")
            excel_data = excel_buffer.getvalue()

            col_export_xlsx.download_button(
                label="📊 Export Excel",
                data=excel_data,
                file_name=f"docusync_audit_report_{status_filter.lower()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_xlsx",
            )

            st.divider()

            # RECORD EXPANDERS & CA AUDIT CONTROLS
            for rec in records:
                owner_user = session.get(User, rec.client_id) if rec.client_id else None
                owner_name = owner_user.full_name if owner_user else "Unassigned"
                owner_label = f" | Client: {owner_name}" if is_admin else ""

                with st.expander(
                    f"ID #{rec.id}{owner_label} | {rec.filename} | Status: {rec.overall_status}"
                ):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Type:** {rec.document_type}")
                    c2.write(f"**Invoice #:** {rec.invoice_number or 'N/A'}")
                    c3.write(
                        f"**Total:** ₹{rec.total_amount:,.2f}"
                        if rec.total_amount
                        else "**Total:** N/A"
                    )

                    st.markdown("**Audit Flags:**")
                    flags = (
                        json.loads(rec.audit_flags_json) if rec.audit_flags_json else []
                    )
                    if not flags:
                        st.write("✓ Zero flags reported")
                    else:
                        for f in flags:
                            st.caption(
                                f"⚠️ [{f.get('severity')}] {f.get('code')}: {f.get('message')}"
                            )

                    st.markdown("**Structured Data:**")
                    raw_json = (
                        json.loads(rec.raw_json_data) if rec.raw_json_data else {}
                    )
                    st.json(raw_json)

                    if rec.overall_status == "VERIFIED":
                        st.divider()
                        col_tally, col_zoho = st.columns(2)

                        tally_xml = tally_exporter.generate_purchase_voucher_xml(rec)
                        col_tally.download_button(
                            label="🏷️ Export to Tally XML",
                            data=tally_xml,
                            file_name=f"Tally_Voucher_ID_{rec.id}.xml",
                            mime="application/xml",
                            key=f"tally_btn_{rec.id}",
                        )

                        zoho_csv = zoho_exporter.generate_bills_csv([rec])
                        col_zoho.download_button(
                            label="📑 Export to Zoho Books CSV",
                            data=zoho_csv,
                            file_name=f"Zoho_Bill_ID_{rec.id}.csv",
                            mime="text/csv",
                            key=f"zoho_btn_{rec.id}",
                        )

                    if is_admin:
                        st.divider()
                        st.subheader("🛠️ Auditor Review & Edit")

                        with st.form(key=f"audit_form_{rec.id}"):
                            v_name = st.text_input(
                                "Vendor Name", value=rec.vendor_name or ""
                            )
                            inv_num = st.text_input(
                                "Invoice Number", value=rec.invoice_number or ""
                            )
                            tot_amt = st.number_input(
                                "Total Amount (₹)",
                                value=float(rec.total_amount or 0.0),
                                step=0.01,
                            )
                            
                            status_options = ["VERIFIED", "NEEDS_REVIEW", "REJECTED"]
                            current_idx = (
                                status_options.index(rec.overall_status)
                                if rec.overall_status in status_options
                                else 0
                            )
                            new_status = st.selectbox(
                                "Override Status",
                                options=status_options,
                                index=current_idx,
                            )
                            
                            notes = st.text_area(
                                "Auditor Notes", value=rec.auditor_notes or ""
                            )
                            
                            save_btn = st.form_submit_button("Save Audit Decision", type="primary")

                        if save_btn:
                            db_rec = session.get(DocumentRecord, rec.id)
                            if db_rec:
                                db_rec.vendor_name = v_name
                                db_rec.invoice_number = inv_num
                                db_rec.total_amount = tot_amt
                                db_rec.overall_status = new_status
                                db_rec.auditor_notes = notes
                                session.add(db_rec)
                                session.commit()
                                st.success(f"Updated Record #{rec.id} successfully!")
                                st.rerun()
                    elif rec.auditor_notes:
                        st.divider()
                        st.info(f"**CA Auditor Note:** {rec.auditor_notes}")

# ---------------------------------------------------------
# TAB 3: ANALYTICS
# ---------------------------------------------------------
with tab_analytics:
    st.header("Pipeline Metrics")
    with Session(engine) as session:
        query = select(DocumentRecord)
        if not is_admin:
            query = query.where(DocumentRecord.client_id == user.id)

        all_records = session.exec(query).all()

    if all_records:
        total_val = sum(r.total_amount or 0.0 for r in all_records)
        col1, col2 = st.columns(2)
        col1.metric("Total Processed Volume", len(all_records))
        col2.metric("Total Invoice Value", f"₹{total_val:,.2f}")
    else:
        st.info("No transaction data available for analytics.")