import os
import runpy
import streamlit as st

# Inject Streamlit secrets into os.environ for Pydantic/SQLAlchemy compatibility
if hasattr(st, "secrets"):
    for key, val in st.secrets.items():
        if isinstance(val, str):
            os.environ[key] = val

# Force reset SQLite DB file if requested or stale (uncomment below if needed on cloud shell)
# DB_PATH = "docusync.db"
# if os.path.exists(DB_PATH):
#     os.remove(DB_PATH)

# Execute app/dashboard.py as the primary application entry script
runpy.run_path("app/dashboard.py", run_name="__main__")