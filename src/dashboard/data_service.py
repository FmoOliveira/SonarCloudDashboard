import pandas as pd
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from tenacity import retry, wait_exponential_jitter, stop_after_attempt, retry_if_exception
from sonarcloud_api import SonarCloudAPI
from dashboard_components import compress_to_parquet
import streamlit as st
from constants import SONAR_METRICS
from config import config

class DataServiceError(Exception): pass

@st.cache_data(ttl=300)
def fetch_projects(organization: str):
    async def _run():
        async with aiohttp.ClientSession() as session:
            api = SonarCloudAPI(config.sonarcloud_api_token, session)
            return await api.get_organization_projects(organization)
    
    try:
        return asyncio.run(_run())
    except Exception as e:
        logging.error(f"Error fetching projects: {str(e)}")
        raise DataServiceError("Error fetching projects. An internal error occurred.")

@st.cache_data(ttl=300)
def fetch_project_branches(project_key: str):
    async def _run():
        async with aiohttp.ClientSession() as session:
            api = SonarCloudAPI(config.sonarcloud_api_token, session)
            return await api.get_project_branches(project_key)
            
    try:
        return asyncio.run(_run())
    except Exception as e:
        logging.warning(f"Could not fetch branches for {project_key}: {str(e)}")
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
    
    params: dict[str, str | int] = {
        "component": project_key,
        "metrics": ",".join(SONAR_METRICS),
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
def fetch_metrics_data(project_keys: list, days: int, branch: str = "master", _storage=None) -> bytes:
    dfs_to_concat = []
    projects_to_fetch = []
    
    for project_key in project_keys:
        need_fresh_data = True
        
        if _storage:
            try:
                coverage_info = _storage.check_data_coverage(project_key, branch, days)
                
                if coverage_info["has_coverage"]:
                    stored_data = coverage_info.get("data", [])
                    if stored_data is not None and (isinstance(stored_data, pd.DataFrame) and not stored_data.empty or (isinstance(stored_data, list) and stored_data)):
                        logging.info(f"Using stored records for {project_key} (latest: {coverage_info['latest_date']})")
                        if len(stored_data) >= getattr(_storage, 'MAX_RETRIEVAL_LIMIT', 10000):
                            logging.warning(f"Data retrieval limit ({getattr(_storage, 'MAX_RETRIEVAL_LIMIT', 10000)}) reached.")

                        if isinstance(stored_data, pd.DataFrame):
                            dfs_to_concat.append(stored_data)
                        else:
                            dfs_to_concat.append(pd.DataFrame(stored_data))
                        need_fresh_data = False
                else:
                    logging.info(f"Fetching fresh data for {project_key}...")
                    
            except Exception as e:
                logging.warning(f"Storage check failed for {project_key}: {str(e)}")
        
        if need_fresh_data:
             projects_to_fetch.append(project_key)
    
    if projects_to_fetch:
        token = config.sonarcloud_api_token
        
        raw_results = asyncio.run(_fetch_all_projects_history(projects_to_fetch, token, days, branch))
        
        for project_key, result in raw_results.items():
            if isinstance(result, Exception):
                logging.error(f"Failed to fetch {project_key}: {str(result)}")
            else:
                if result:
                    df_to_store = pd.DataFrame(result)
                    dfs_to_concat.append(df_to_store)
                    if _storage:
                        try:
                            success = _storage.store_metrics_data(df_to_store, project_key, branch)
                            if success:
                                logging.info(f"Stored {len(result)} new records for {project_key}")
                            else:
                                logging.error("Failed to store metrics data internally.")
                        except Exception as e:
                            logging.warning(f"Could not store data for {project_key}: {str(e)}")
                else:
                    try:
                        async def _fallback_measure():
                            async with aiohttp.ClientSession() as sess:
                                api = SonarCloudAPI(token, sess)
                                return await api.get_project_measures(project_key, branch)
                        
                        measures = asyncio.run(_fallback_measure())
                        if measures:
                            measures['project_key'] = project_key
                            measures['date'] = datetime.now().replace(tzinfo=None).strftime('%Y-%m-%d')
                            df_to_store = pd.DataFrame([measures])
                            dfs_to_concat.append(df_to_store)
                            if _storage:
                                success = _storage.store_metrics_data(df_to_store, project_key, branch)
                    except Exception as e:
                        logging.error(f"Fallback fetch failed for {project_key}: {str(e)}")
    
    df = pd.concat(dfs_to_concat, ignore_index=True) if dfs_to_concat else pd.DataFrame()
    
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], format='ISO8601', errors='coerce', utc=True)
        df['date'] = df['date'].dt.tz_convert(None)
        
        available_numeric = [col for col in SONAR_METRICS if col in df.columns]
        if available_numeric:
            converted = {col: pd.to_numeric(df[col], errors='coerce') for col in available_numeric}
            df = df.assign(**converted)

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
    
    return compress_to_parquet(df) if dfs_to_concat else compress_to_parquet(pd.DataFrame())
