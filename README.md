# mockexchange‑deck

One‑user Streamlit dashboard for `mockexchange_api` (paper‑trading PoC).

```bash
# dev run – hot reload using Poetry
cp .env.example .env
poetry install
poetry run streamlit run app/main.py

# Docker (host network)
docker compose up --build
```

---

## app/__init__.py
```python
"""Top‑level package; sets global Streamlit config."""
import streamlit as st
st.set_page_config(page_title="mockexchange‑deck", page_icon="📊", layout="wide")
```