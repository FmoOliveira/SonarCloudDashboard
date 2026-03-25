import streamlit as st
import pandas as pd
import asyncio
import aiohttp
import logging
import os
from datetime import datetime, timedelta
from tenacity import retry, wait_exponential_jitter, stop_after_attempt, retry_if_exception
from sonarcloud_api import SonarCloudAPI
from dashboard_components import compress_to_parquet

def get_secret(domain: str, key: str) -> str:
    """
    Safely extracts secrets checking OS environment variables first, 
    enforcing strict validation before downstream API calls occur.
    """
    env_name = f"{domain.upper()}_{key.upper()}"
    if env_name in os.environ:
        return os.environ[env_name]
        
    try:
        return st.secrets[domain][key]
    except FileNotFoundError:
        logging.error("Security Configuration Error: `secrets.toml` is missing.")
        st.error("Security Configuration Error: A required configuration file is missing.", icon="🚨")
        st.stop()
        return ""
    except KeyError:
        error_msg = f"Security Configuration Error: Missing key '{key}' in domain '{domain}'."
        logging.critical(error_msg)
        st.error("Security Configuration Error: A required configuration key is missing.", icon="🚨")
        st.stop()
        return ""

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_projects(_api, organization):
    """Fetch projects from SonarCloud organization"""
    try:
        return _api.get_organization_projects(organization)
    except Exception as e:
        logging.error(f"Error fetching projects: {str(e)}")
        st.error("Error fetching projects. An internal error occurred.", icon="🚨")
        return []

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_project_branches(_api, project_key):
    """Fetch branches for a specific project"""
    try:
        return _api.get_project_branches(project_key)
    except Exception as e:
        logging.warning(f"Could not fetch branches for {project_key}: {str(e)}")
        st.warning("Could not fetch branches. An internal error occurred.")
        return []

def should_retry_api_call(exc: BaseException) -> bool:
    if isinstance(exc, aiohttp.ClientResponseError):
        return exc.status in [429, 500, 502, 503, 504]
    if isinstance(exc, (aiohttp.ClientError, asyncio.TimeoutError)):
        return True
    return False

@retry(
    wait=wait_exponential_jitter(initial=2, max=15), 
    stop=stop_after_attempt(5),
    retry=retry_if_exception(should_retry_api_call),
    reraise=True
)
async def fetch_sonar_history_async(session: aiohttp.ClientSession, project_key: str, token: str, days: int, branch: str | None = None) -> list:
    url = "https://sonarcloud.io/api/measures/search_history"
    start_date = datetime.now() - timedelta(days=days)
    end_date = datetime.now()
    
    metrics = [
        'coverage', 'duplicated_lines_density', 'bugs', 'reliability_rating',
        'vulnerabilities', 'security_rating', 'security_hotspots', 'security_review_rating',
        'security_hotspots_reviewed', 'code_smells', 'sqale_rating', 'major_violations',
        'minor_violations', 'violations'
    ]
    params: dict[str, str | int] = {
        "component": project_key,
        "metrics": ",".join(metrics),
        "from": start_date.strftime('%Y-%m-%d'),
        "to": end_date.strftime('%Y-%m-%d'),
        "ps": 1000
    }
    if branch and branch.strip():
        params["branch"] = branch.strip()
        
    headers = {"Authorization": f"Bearer {token}"}
    call_timeout = aiohttp.ClientTimeout(total=15, connect=5)
    
    async with session.get(url, params=params, headers=headers, timeout=call_timeout) as response:
        response.raise_for_status()
        data = await response.json()
        
        # ⚡ Bolt Optimization: Replaced O(N^2) list lookup `next((r for r in history...))`
        # with an O(1) dictionary lookup keyed by date. This prevents blocking the asyncio
        # event loop when processing thousands of historical data points per project.
        history_dict = {}
        if 'measures' in data:
            for measure in data['measures']:
                metric_name = measure['metric']
                for hist_item in measure.get('history', []):
                    date_val = hist_item.get('date')
                    value = hist_item.get('value')
                    
                    if date_val and value is not None:
                        if date_val not in history_dict:
                            record = {'date': date_val, 'project_key': project_key}
                            if branch:
                                record['branch'] = branch
                            history_dict[date_val] = record
                        else:
                            record = history_dict[date_val]
                        
                        if metric_name in ['coverage', 'duplicated_lines_density']:
                            record[metric_name] = float(value)
                        else:
                            record[metric_name] = int(float(value)) if '.' in value else int(value)
                            
        return list(history_dict.values())

async def _fetch_all_projects_history(project_keys: list, token: str, days: int, branch: str) -> dict:
    connector = aiohttp.TCPConnector(limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_sonar_history_async(session, pk, token, days, branch) for pk in project_keys]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return dict(zip(project_keys, results))

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_metrics_data(_api: SonarCloudAPI, project_keys: list, days: int, branch: str = "master", _storage=None) -> bytes:
    """Fetch historical metrics data using async endpoints and compress to Parquet bytes for caching"""
    all_data = []
    projects_to_fetch = []
    
    for project_key in project_keys:
        need_fresh_data = True
        
        if _storage:
            try:
                coverage_info = _storage.check_data_coverage(project_key, branch, days)
                
                if coverage_info["has_coverage"]:
                    stored_data = coverage_info.get("data", [])
                    if stored_data:
                        logging.info(f"Using stored records for {project_key} (latest: {coverage_info['latest_date']})")
                        if isinstance(stored_data, pd.DataFrame):
                            all_data.extend(stored_data.to_dict('records'))
                        else:
                            all_data.extend(stored_data)
                        need_fresh_data = False
                else:
                    logging.info(f"Fetching fresh data for {project_key}...")
                    
            except Exception as e:
                logging.warning(f"Storage check failed for {project_key}: {str(e)}")
        
        if need_fresh_data:
             projects_to_fetch.append(project_key)
    
    if projects_to_fetch:
        token = get_secret("sonarcloud", "api_token")
        raw_results = asyncio.run(_fetch_all_projects_history(projects_to_fetch, token, days, branch))
        
        for project_key, result in raw_results.items():
            if isinstance(result, Exception):
                logging.error(f"Failed to fetch {project_key}: {str(result)}")
            else:
                if result:
                    for r in result:
                        all_data.append(r)
                    if _storage:
                        try:
                            df_to_store = pd.DataFrame(result)
                            success = _storage.store_metrics_data(df_to_store, project_key, branch)
                            if success:
                                logging.info(f"Stored {len(result)} new records for {project_key}")
                        except Exception as e:
                            logging.warning(f"Could not store data for {project_key}: {str(e)}")
                else:
                    try:
                        measures = _api.get_project_measures(project_key, branch)
                        if measures:
                            measures['project_key'] = project_key
                            measures['date'] = datetime.now().replace(tzinfo=None).strftime('%Y-%m-%d')
                            all_data.append(measures)
                            if _storage:
                                df_to_store = pd.DataFrame([measures])
                                _storage.store_metrics_data(df_to_store, project_key, branch)
                    except Exception as e:
                        logging.error(f"Fallback fetch failed for {project_key}: {str(e)}")
    
    df = pd.DataFrame(all_data)
    
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], format='ISO8601', errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_convert(None)
        
        numeric_columns = ['coverage', 'duplicated_lines_density', 'bugs', 'reliability_rating',
                          'vulnerabilities', 'security_rating', 'security_hotspots', 
                          'security_review_rating', 'security_hotspots_reviewed', 'code_smells', 
                          'sqale_rating', 'major_violations', 'minor_violations', 'violations']
        
        available_numeric = []
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                available_numeric.append(col)

        if available_numeric:
            agg_dict = {col: 'mean' for col in available_numeric}
            other_cols = [col for col in df.columns if col not in available_numeric + ['date', 'project_key']]
            for col in other_cols:
                agg_dict[col] = 'first'
            
            df = df.groupby(['project_key', 'date'], observed=True).agg(agg_dict).reset_index()
            
            for col in available_numeric:
                if col in df.columns:
                    df[col] = df[col].round(2)

            if 'project_key' in df.columns:
                df['project_key'] = df['project_key'].astype('category')
            if 'branch' in df.columns:
                df['branch'] = df['branch'].astype('category')

            for col in available_numeric:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], downcast='float')
    
    return compress_to_parquet(df) if all_data else compress_to_parquet(pd.DataFrame())
