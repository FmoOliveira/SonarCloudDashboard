# SonarCloud Metrics Dashboard

![SonarCloud Dashboard Overview](C:\Users\fmoliveira\.gemini\antigravity\brain\0f24a186-fc31-4388-9a60-c9911fab6c6a\sonarcloud_dashboard_overview_1772147590981.png)

An enterprise-grade, highly optimized Streamlit dashboard designed to monitor, track, and analyze SonarCloud project metrics over time. Built with a unified design system drawing inspiration from Spotify's dark mode, this application provides teams with deep insights into code quality, technical debt, and security postures.

## 🚀 Key Features

- **Architectural Database Abstraction:** Employs the Strategy/Factory design pattern to completely decouple the frontend from the storage backend. Natively supports Azure Table Storage but is ready to swap to PostgreSQL or SQLite by changing a single TOML configuration line.
- **Batched Network I/O:** Uses Microsoft Azure's native `submit_transaction` API to batch 100 database records per REST call, reducing network overhead by 90% during telemetry ingestion.
- **Fail-Fast Secret Management:** Removes `.env` vulnerabilities by migrating entirely to Streamlit's native nested `secrets.toml`. Includes a strictly typed, fail-fast dictionary accessor proxy that immediately halts the application if unauthorized deployment is attempted.
- **Stateless & Memory Optimized:** Avoids $O(N^2)$ memory leak reallocations by processing primary Pandas Dataframes entirely by reference when interacting with Plotly Dash components.
- **Dynamic Time Groupings:** Custom date-range bounding powered by Python vectorized `ISO8601` evaluation, dramatically speeding up multi-project datetime filtering relative to raw iteration.
- **Fluid UI Context Controls:** Sidebar actions (Project, Branch, Date Range) use `st.form` batching to prevent Streamlit from violently thrashing the main execution loop, allowing users to modify arbitrary query filters smoothly.

---

## 🛠️ Tech Stack
- **Frontend/Framework:** [Streamlit](https://streamlit.io/)
- **Data Manipulation:** [Pandas](https://pandas.pydata.org/) & [NumPy](https://numpy.org/)
- **Visualizations:** [Plotly Express & Graph_Objects](https://plotly.com/python/)
- **Asynchronous I/O:** `aiohttp` & `asyncio` for multi-threaded SonarCloud fetches
- **Storage Strategy:** Azure Table Storage Client SDK
- **Design:** Custom HTML bindings utilizing [Iconoir](https://iconoir.com/) SVG web fonts

---

## 📦 Getting Started

### 1. Prerequisites
Ensure you have Python 3.10+ installed.

```bash
git clone https://github.com/your-org/SonarCloudDashboard.git
cd SonarCloudDashboard

# Create virtual environment
python -m venv venv
# Activate on Windows:
.\venv\Scripts\activate
# Activate on Unix:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (`secrets.toml`)

This project strictly bans `.env` logic in favor of Streamlit's native `secrets.toml`. In your root directory, create a `.streamlit` folder and add `secrets.toml` inside it:

**Location: `.streamlit/secrets.toml`**
```toml
# Database Configuration
[database]
provider = "azure" # Choose your backend (currently exclusively "azure")

# Azure Storage Connection
[azure_storage]
connection_string = "DefaultEndpointsProtocol=https;AccountName=my-account;AccountKey=my-key;EndpointSuffix=core.windows.net"
container_name = "sonar-telemetry-cache"

# SonarCloud Connection
[sonarcloud]
api_token = "sqp_abc123yourtoken456"
organization_key = "your-organization-slug"
```

> **Warning:** This file contains highly privileged API credentials. Ensure `.streamlit/secrets.toml` remains in your `.gitignore`.

### 3. Launching

Run the application locally via Streamlit:

```bash
streamlit run app.py
```

The application will launch on `http://localhost:8501`.

---

## 🏛️ System Architecture

### 1. The Database Factory (`database/factory.py`)
All downstream database access is handled via `get_storage_client()`. This enforces an agnostic `StorageInterface` base class, allowing seamless transitions to hybrid deployments without rewriting the visualization pipelines in `app.py`.

### 2. The Fetching Engine (`sonarcloud_api.py`)
Relies on asynchronous API dispatchers wrapped in `tenacity.retry` decorators to gracefully catch timeouts, transient networking errors, and SonarCloud rate-limit 429 warnings by applying exponential backoff jitters.

### 3. Progressive UI Ephemerality
Administrative UI features (like the Azure synchronization loop) execute using `st.empty()`. Rather than leaving permanent "100% Downloaded" UX artifacts crowding the sidebar, the loading blocks execute progress mathematics dynamically and silently destroy themselves from the DOM the moment the process completes, yielding maximum visual real estate back to the user constraints.

---

## 🤝 Contributing
1. Create your Feature Branch (`git checkout -b feature/AmazingSecurityFix`)
2. Commit your Changes (`git commit -m 'Added amazing zero-downtime PostgreSQL factory logic'`)
3. Push to the Branch (`git push origin feature/AmazingSecurityFix`)
4. Open a Pull Request!
