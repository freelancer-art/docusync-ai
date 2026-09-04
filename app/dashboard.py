import io
import json
import os
import tempfile
from datetime import UTC, datetime

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.database import DocumentRecord, User, UserRole, engine, init_db
from app.core.groq_client import get_ai_client
from app.services.audit_engine import process_document_audit
from app.services.extractor_service import extractor_service
from app.services.gstin_validator import gstin_validator
from app.services.rag_sql import build_safe_ledger_query
from app.services.tally_exporter import tally_exporter
from app.services.zoho_exporter import zoho_exporter

# Streamlit Page Setup
st.set_page_config(
    page_title="DocuSync AI - Multi-Tenant Portal", page_icon="🔒", layout="wide"
)


@st.cache_resource
def run_db_initialization():
    init_db()


run_db_initialization()

# Session State Initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# ---------------------------------------------------------
# AUTHENTICATION & REGISTRATION SCREEN
# ---------------------------------------------------------
if not st.session_state.authenticated:
    st.title("🔒 DocuSync AI Portal")

    auth_mode = st.radio(
        "Select Action",
        ["Sign In", "Register New CA Firm", "Register Client"],
        horizontal=True,
    )

    col1, _ = st.columns([1, 2])

    with col1:
        if auth_mode == "Sign In":
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

        elif auth_mode == "Register New CA Firm":
            st.subheader("CA Firm Registration")
            new_username = st.text_input("Admin Username")
            new_fullname = st.text_input("CA Firm / Admin Name")
            new_password = st.text_input("Password", type="password")

            if st.button("Register CA Account", type="primary"):
                if not new_username or not new_fullname or not new_password:
                    st.error("Please fill out all fields.")
                else:
                    with Session(engine) as session:
                        existing_user = session.exec(
                            select(User).where(User.username == new_username)
                        ).first()
                        if existing_user:
                            st.error(f"Username '{new_username}' is already registered.")
                        else:
                            ca_user = User(
                                username=new_username,
                                full_name=new_fullname,
                                hashed_password=User.hash_password(new_password),
                                role=UserRole.CA_ADMIN,
                            )
                            session.add(ca_user)
                            session.commit()
                            st.success("CA Account created successfully! Please sign in.")

        elif auth_mode == "Register Client":
            st.subheader("Client Registration")
            client_username = st.text_input("Client Username")
            client_fullname = st.text_input("Client / Company Name")
            client_password = st.text_input("Password", type="password")

            if st.button("Register Client Account", type="primary"):
                if not client_username or not client_fullname or not client_password:
                    st.error("Please fill out all fields.")
                else:
                    with Session(engine) as session:
                        existing_user = session.exec(
                            select(User).where(User.username == client_username)
                        ).first()
                        if existing_user:
                            st.error(f"Username '{client_username}' is already registered.")
                        else:
                            client_user = User(
                                username=client_username,
                                full_name=client_fullname,
                                hashed_password=User.hash_password(client_password),
                                role=UserRole.CLIENT,
                            )
                            session.add(client_user)
                            session.commit()
                            st.success("Client Account created successfully! Please sign in.")

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
        st.session_state.chat_messages = []
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

tab_titles = ["📤 Upload & Extract", "📋 Audit Ledger", "💬 Ask DocuSync AI", "📊 Analytics"]
if is_admin:
    tab_titles.append("👥 Manage Accounts")

tabs = st.tabs(tab_titles)
tab_ingest, tab_audit, tab_rag, tab_analytics = tabs[0], tabs[1], tabs[2], tabs[3]

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
            st.warning("No client accounts found. Please onboard client accounts in the 'Manage Accounts' tab.")
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
        with st.spinner("Processing, extracting & auditing document..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            try:
                extraction_result = extractor_service.process_document(
                    file_input=tmp_path,
                    filename=uploaded_file.name,
                )

                vendor_name = extraction_result.get("vendor_name")
                total_amount = extraction_result.get("total_amount")

                new_record = DocumentRecord(
                    client_id=target_client_id,
                    filename=uploaded_file.name,
                    document_type=extraction_result.get("doc_type", "TAX_INVOICE"),
                    vendor_name=vendor_name,
                    invoice_number=extraction_result.get("invoice_number"),
                    total_amount=float(total_amount or 0.0),
                    payment_status="UNPAID",
                    overall_status="NEEDS_REVIEW",
                    raw_json_data=json.dumps(extraction_result),
                    audit_flags_json=json.dumps([]),
                    created_at=datetime.now(UTC),
                )

                with Session(engine) as session:
                    session.add(new_record)
                    session.commit()
                    session.refresh(new_record)

                    audited_record = process_document_audit(new_record, session)

                st.success(
                    f"Successfully processed Record ID #{audited_record.id} | Status: {audited_record.overall_status}!"
                )
                st.json(extraction_result)

            except Exception as e:  # noqa: BLE001
                st.error(f"Error processing document: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

# ---------------------------------------------------------
# TAB 2: AUDIT LEDGER
# ---------------------------------------------------------
with tab_audit:
    st.header("Document Audit Ledger")

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

    col_filter, col_export_csv, col_export_xlsx = st.columns([2, 1, 1])
    status_filter = col_filter.selectbox(
        "Filter by Status",
        ["ALL", "REJECTED", "NEEDS_REVIEW", "VERIFIED"],
        key="audit_status_filter",
    )

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

            csv_data = df_export.to_csv(index=False).encode("utf-8")
            col_export_csv.download_button(
                label="📥 Export CSV",
                data=csv_data,
                file_name=f"docusync_audit_report_{status_filter.lower()}.csv",
                mime="text/csv",
                key="download_csv",
            )

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
# TAB 3: RAG CHAT ASSISTANT ("Ask DocuSync AI")
# ---------------------------------------------------------
with tab_rag:
    st.header("💬 Ask DocuSync AI")
    st.caption("Execute SQL analytics across your tenant ledger using natural language.")

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_query = st.chat_input("e.g. What is the total invoice amount for all REJECTED documents?")

    if user_query:
        st.session_state.chat_messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        client, model = get_ai_client()
        if not client or model == "NONE":
            response_text = "AI assistant client is not configured. Please set GROQ_API_KEY or GEMINI_API_KEY."
        else:
            table_schema = """
            Table name: documentrecord
            Columns:
            - id (INTEGER PRIMARY KEY)
            - client_id (INTEGER)
            - filename (VARCHAR)
            - document_type (VARCHAR)
            - vendor_name (VARCHAR)
            - invoice_number (VARCHAR)
            - total_amount (FLOAT)
            - payment_status (VARCHAR)
            - overall_status (VARCHAR) -- 'VERIFIED', 'NEEDS_REVIEW', 'REJECTED'
            - audit_flags_json (TEXT)
            - created_at (DATETIME)
            """

            sql_gen_prompt = f"""
            You are an expert SQLite query generator for an accounting database.
            Generate a single SELECT SQL query to answer the user's request.
            
            {table_schema}
            
            Rules:
            1. Return ONLY raw executable SQL starting with SELECT inside standard text.
            2. Do NOT perform any INSERT, UPDATE, DELETE, or DROP operations.
            3. Do NOT include markdown code fences like ```sql.
            4. Query only the documentrecord table. Do not use JOIN, PRAGMA, comments, or semicolons.
            
            User Request: {user_query}
            """

            try:
                sql_res = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": sql_gen_prompt}],
                    temperature=0.0,
                )
                generated_sql = sql_res.choices[0].message.content.strip()

                with Session(engine) as session:
                    secure_sql, query_params = build_safe_ledger_query(
                        generated_sql,
                        is_admin=is_admin,
                        client_id=user.id,
                    )
                    result_proxy = session.execute(text(secure_sql), query_params)
                    query_results = [dict(row._mapping) for row in result_proxy]

                synthesis_prompt = f"""
                Synthesize a clear, concise accounting answer based on the SQL Query and Database Results below.
                
                Executed SQL: {secure_sql}
                Database Output: {json.dumps(query_results, default=str)}
                User Request: {user_query}
                """

                synth_res = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": synthesis_prompt}],
                    temperature=0.2,
                )
                response_text = synth_res.choices[0].message.content

            except Exception as e:  # noqa: BLE001
                response_text = f"Unable to execute SQL query cleanly: {e!s}"

        with st.chat_message("assistant"):
            st.markdown(response_text)

        st.session_state.chat_messages.append({"role": "assistant", "content": response_text})

# ---------------------------------------------------------
# TAB 4: ANALYTICS
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

# ---------------------------------------------------------
# TAB 5: MANAGE ACCOUNTS (CA ADMIN ONLY)
# ---------------------------------------------------------
if is_admin:
    tab_users = tabs[4]
    with tab_users:
        st.header("👥 Account Management")
        st.caption("Onboard new Client accounts or manage existing users in the system.")

        col_onboard, col_list = st.columns([1, 1])

        with col_onboard:
            st.subheader("➕ Onboard New Client Account")
            with st.form("onboard_client_form"):
                client_username = st.text_input("Username")
                client_fullname = st.text_input("Client / Company Name")
                client_password = st.text_input("Temporary Password", type="password")

                onboard_submitted = st.form_submit_button("Create Client Account", type="primary")

                if onboard_submitted:
                    if not client_username or not client_fullname or not client_password:
                        st.error("All fields are required.")
                    else:
                        with Session(engine) as session:
                            existing = session.exec(
                                select(User).where(User.username == client_username)
                            ).first()
                            if existing:
                                st.error(f"Username '{client_username}' already exists.")
                            else:
                                new_client = User(
                                    username=client_username,
                                    full_name=client_fullname,
                                    hashed_password=User.hash_password(client_password),
                                    role=UserRole.CLIENT,
                                )
                                session.add(new_client)
                                session.commit()
                                st.success(f"Successfully onboarded Client: '{client_fullname}'!")
                                st.rerun()

        with col_list:
            st.subheader("📜 Existing Accounts")
            with Session(engine) as session:
                users_list = session.exec(select(User)).all()
                if users_list:
                    user_table_data = [
                        {
                            "ID": u.id,
                            "Username": u.username,
                            "Full Name": u.full_name,
                            "Role": u.role,
                        }
                        for u in users_list
                    ]
                    st.dataframe(pd.DataFrame(user_table_data), width="stretch")
                else:
                    st.info("No users found.")
