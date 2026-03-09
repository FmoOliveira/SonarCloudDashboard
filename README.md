# SonarCloud Metrics Dashboard

![SonarCloud Dashboard Overview](docs/pic1.png)

An enterprise-ready Streamlit dashboard for monitoring SonarCloud project metrics over time. It provides a fast, responsive UI with metric cards, interactive charts, and a storage abstraction that supports Azure Table Storage today and can be extended to PostgreSQL.

## ✨ Features
- **Enterprise Authentication**: Integrated with **Microsoft Entra ID (Azure AD)** via MSAL for secure, single sign-on access.
- **Multi-project insights**: Cached historical metrics and trend charts for a comprehensive view of your SonarCloud organization.
- **Professional UI Design**: Modern "Flat Enterprise" aesthetic with status-coded metric cards, optimized for both **Light and Dark modes**.
- **Storage abstraction**: Factory/strategy pattern (`database/`) decouples UI from the backend (Azure Table Storage supported).
- **High-Performance Ingestion**: Async SonarCloud API fetching with exponential backoff and memory-efficient Parquet compression.
- **Offline demo mode**: View the dashboard instantly using synthetic data (`demo/`).

## 🧱 Architecture Overview
```
src/dashboard/
├── app.py                  # Main entry point: Orchestration and session flow
├── data_service.py         # Data fetching, async API, and memory-aware caching
├── dashboard_view.py       # Metrics calculations and UI rendering logic
├── ui_styles.py            # Unified UI styling and theme management
├── sonarcloud_api.py       # SonarCloud API client + retry/backoff
├── dashboard_components.py # Reusable Plotly charts and card helpers
├── database/               # Storage interfaces + Azure Table Storage backend
├── demo/                   # Synthetic data generator for offline mode
└── styles.css              # Custom global CSS
```

### Key Design Choices
1. **Source Code Separation (`src/` layout)**  
   The application logic is isolated from deployment and configuration files, following modern Python best practices.
2. **Modular UI & Data Services**  
   The entry point (`app.py`) is decoupled from data processing (`data_service.py`) and visualization logic (`dashboard_view.py`), making the codebase easier to maintain and test.
3. **Storage Factory (`database/factory.py`)**  
   The UI uses `get_storage_client()` to resolve the backend. This keeps the application free of storage-specific concerns.
4. **Memory-aware rendering**  
   Heavy data is compressed and cached in session state using Parquet, and Plotly rendering is optimized to avoid unnecessary copies.
5. **Unified Theme Management**  
   A centralized styling system ensures visual consistency for buttons, inputs, and custom components across theme transitions.

## 🎨 UI Themes
The dashboard features a professional, high-contrast theme system:
- **Dark Mode**: Deep navy backgrounds with subtle borders and vibrant status accents.
- **Light Mode**: Clean, minimal "borderless" aesthetic with soft off-white backgrounds and professional corporate blue controls.
- **Switching**: Accessible via the User Profile popover in the sidebar.

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

[sonarcloud]
api_token = "sqp_your_token"
organization_key = "your-organization-slug"
```

> **Security note:** `secrets.toml` contains sensitive keys. Keep it out of version control.

## ▶️ Running the App

### Option A — Standard Local Run
```bash
streamlit run src/dashboard/app.py
```

### Option B — Offline Demo Mode
```bash
python src/dashboard/demo/demo_generator.py
streamlit run src/dashboard/app.py -- --demo-mode
```

### Option C — Docker + Azurite
```bash
docker-compose up -d
```
Open `http://localhost:8501`.

## 🧪 Testing
```bash
python -m pytest tests
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
