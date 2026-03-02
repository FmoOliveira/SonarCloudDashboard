# SonarCloud Metrics Dashboard

![SonarCloud Dashboard Overview](docs/pic1.png)

An enterprise-ready Streamlit dashboard for monitoring SonarCloud project metrics over time. It provides a fast, responsive UI with metric cards, interactive charts, and a storage abstraction that supports Azure Table Storage today and can be extended to PostgreSQL.

## ✨ Features
- **Multi-project insights** with cached historical metrics and trend charts.
- **Storage abstraction** via a factory/strategy pattern (`database/`) to keep the UI decoupled from the backend.
- **Async SonarCloud ingestion** with retry logic and batching.
- **Light/Dark mode toggle** with a modern UI theme.
- **Offline demo mode** using synthetic data (`demo/`).

## 🧱 Architecture Overview
```
app.py                  # Streamlit UI, orchestration, and session flow
sonarcloud_api.py        # SonarCloud API client + retry/backoff
dashboard_components.py  # Plotly charts, cards, layout helpers
database/                # Storage interfaces + Azure Table Storage backend
auth.py                  # Entra ID (MSAL) auth + user profile
styles.css               # UI styling
.streamlit/config.toml   # Theme configuration
demo/                    # Synthetic data generator for offline mode
```

### Key Design Choices
1. **Storage Factory (`database/factory.py`)**  
   The UI uses `get_storage_client()` to resolve the backend. This keeps `app.py` free of storage-specific concerns.
2. **Batched writes**  
   Azure Table Storage writes are batched to reduce network overhead and improve ingestion throughput.
3. **Memory-aware rendering**  
   Heavy data is compressed and cached in session state, and Plotly rendering is optimized to avoid unnecessary copies.

## ✅ Requirements & Prerequisites
- **Python 3.10+**
- **pip** (or `uv`)
- **SonarCloud API token**
- **Storage backend**:
  - Azure Table Storage (production) or
  - **Azurite** for local development (via Docker)

Install dependencies:
```bash
pip install -r requirements.txt
```

## 🔐 Configuration
Create `.streamlit/secrets.toml`:
```toml
[database]
provider = "azure"

[azure_storage]
connection_string = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=...;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
container_name = "sonar-telemetry-cache"

[sonarcloud]
api_token = "sqp_your_token"
organization_key = "your-organization-slug"
```

> **Security note:** `secrets.toml` contains sensitive keys. Keep it out of version control.

## ▶️ Running the App

### Option A — Standard Local Run
```bash
streamlit run app.py
```

### Option B — Offline Demo Mode
```bash
python demo/demo_generator.py
streamlit run app.py -- --demo-mode
```

### Option C — Docker + Azurite
```bash
docker-compose up -d
```
Open `http://localhost:8501`.

## 🧪 Testing
```bash
python -m unittest discover -s tests
```

Some API tests use pytest:
```bash
pytest test_sonar_api.py
```

## 📦 Requirements (Summary)
Main packages (see `requirements.txt` for full list):
- streamlit
- pandas, numpy
- plotly
- azure-data-tables
- aiohttp, tenacity, urllib3
- msal, streamlit-cookies-manager

## 🗺️ Future Improvements
- **PostgreSQL backend** using the existing storage interface (`database/`) for scalable persistence.
- Caching improvements for large multi-project dashboards.
- Role-based access controls for enterprise environments.

## 🤝 Contributing
1. Create a feature branch: `git checkout -b feature/my-change`
2. Commit your changes: `git commit -m "Describe change"`
3. Push and open a PR.
