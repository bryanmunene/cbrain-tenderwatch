# TenderWatch Streamlit Deployment Guide

This is the recommended free hosting path for TenderWatch.

## Local Run

```powershell
cd tenderwatch_app
pip install -r requirements.txt
python init_sources.py
streamlit run streamlit_app.py
```

Local URL: `http://localhost:8501`

## Deploy On Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to `https://share.streamlit.io` and sign in with GitHub.
3. Choose **Create app**.
4. Select this repository and branch.
5. Set the main file path to:

```text
streamlit_cloud/app.py
```

6. In **Advanced settings**, paste secrets based on:

```text
streamlit_cloud/secrets.toml.example
```

At minimum, set `SECRET_KEY`. For durable storage, also set `DATABASE_URL` to a hosted Postgres URL such as Neon.

7. Click **Deploy**.

## Why Use `streamlit_cloud/app.py`?

The main app still lives at `tenderwatch_app/streamlit_app.py`. The cloud wrapper points Streamlit Cloud to the real app while using `streamlit_cloud/requirements.txt`, which avoids installing heavy optional ML packages during the free cloud build.

## Recommended Secrets

```toml
SECRET_KEY = "replace-with-a-long-random-secret"
TW_ENV = "production"
DATABASE_URL = "postgresql://user:password@host/database?sslmode=require"
```

Discovery keys are optional:

```toml
GOOGLE_API_KEY = ""
GOOGLE_CX = ""
BING_API_KEY = ""
SERPAPI_API_KEY = ""
```

## Free-Tier Notes

Streamlit Community Cloud is suitable for a public pilot or demo. Apps can sleep after inactivity, and the local filesystem is not a reliable database. Use an external Postgres database if scan results and favorites need to persist across restarts.
