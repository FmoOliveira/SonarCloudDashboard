import logging
import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from constants import SONAR_METRICS
from models import SonarProject, SonarMeasure, OrganizationMetrics, SonarBranch

class SonarCloudAPIError(Exception): 
    pass

class SonarCloudAPI:
    """SonarCloud API client for fetching organization and project metrics"""
    
    def __init__(self, token: str, session: aiohttp.ClientSession):
        self.token = token
        self.session = session
        self.base_url = "https://sonarcloud.io/api"
        # self.session should have the headers set already, but just in case
        self.headers = {'Authorization': f'Bearer {token}'}
        
    async def _make_async_request(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        async with self.session.get(url, params=params, headers=self.headers) as response:
            if response.status == 200:
                return await response.json()
            error_msg = await response.text()
            raise SonarCloudAPIError(f"API request failed with status {response.status}: {error_msg}")

    async def _fetch_page(self, session: aiohttp.ClientSession, url: str, params: dict) -> dict:
        async with session.get(url, params=params, headers=self.headers) as response:
            if response.status == 200:
                return await response.json()
            error_msg = await response.text()
            raise SonarCloudAPIError(f"Async API request failed with status {response.status}: {error_msg}")

    async def get_organization_projects(self, organization: str) -> List[SonarProject]:
        projects = []
        page_size = 500
        url = f"{self.base_url}/projects/search"
        params = {"organization": organization, "qualifiers": "TRK", "f": "name,key", "ps": page_size, "p": 1}
        
        try:
            first_page = await self._fetch_page(self.session, url, params)
            for comp in first_page.get('components', []):
                projects.append(SonarProject(**comp))
            
            total = first_page.get('paging', {}).get('total', 0)
            if total > page_size:
                tasks = []
                total_pages = (total + page_size - 1) // page_size
                for page in range(2, total_pages + 1):
                    p = params.copy()
                    p['p'] = page
                    tasks.append(self._fetch_page(self.session, url, p))
                
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception):
                            logging.error(f"Failed to fetch projects page: {r}")
                        else:
                            for comp in r.get('components', []):
                                projects.append(SonarProject(**comp))
        except Exception as e:
            logging.error(f"Failed to fetch initial projects: {e}")
            raise SonarCloudAPIError(f"Error fetching projects: {e}")
                
        return projects
    
    async def get_project_measures(self, project_key: str, branch: str = None) -> Optional[Dict[str, float]]:
        try:
            params = {
                "component": project_key,
                "metricKeys": ",".join(SONAR_METRICS)
            }
            if branch and branch.strip():
                params["branch"] = branch.strip()
            
            response = await self._make_async_request("measures/component", params=params)
            
            measures = {}
            if 'component' in response and 'measures' in response['component']:
                for item in response['component']['measures']:
                    measure = SonarMeasure(**item)
                    metric = measure.metric
                    value = measure.value or '0'
                    
                    if metric in ['coverage', 'duplicated_lines_density']:
                        try:
                            measures[metric] = float(value)
                        except ValueError:
                            measures[metric] = 0.0
                    elif metric in ['bugs', 'vulnerabilities', 'security_hotspots', 
                                  'code_smells', 'major_violations', 'minor_violations', 'violations']:
                        try:
                            measures[metric] = int(value)
                        except ValueError:
                            measures[metric] = 0
                    else:
                        measures[metric] = value
            
            return measures if measures else None
        except Exception as e:
            logging.warning(f"Failed to fetch measures for {project_key}: {str(e)}")
            raise SonarCloudAPIError(f"Failed to fetch measures: {e}")
    
    async def get_project_history(self, project_key: str, days: int, branch: str = None) -> List[Dict]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            history_data = {}
            page = 1
            page_size = 1000
            
            url = f"{self.base_url}/measures/search_history"
            
            while True:
                params = {
                    "component": project_key,
                    "metrics": ",".join(SONAR_METRICS),
                    "from": start_date.strftime('%Y-%m-%d'),
                    "to": end_date.strftime('%Y-%m-%d'),
                    "ps": page_size,
                    "p": page
                }
                if branch and branch.strip():
                    params["branch"] = branch.strip()
                
                response = await self._fetch_page(self.session, url, params)
                
                if 'measures' in response:
                    for item in response['measures']:
                        metric = item['metric']
                        for history_point in item.get('history', []):
                            date = history_point['date']
                            value = history_point.get('value', '0')
                            
                            if date not in history_data:
                                history_data[date] = {'date': date}
                            
                            if metric in ['coverage', 'duplicated_lines_density', 'security_hotspots_reviewed']:
                                try:
                                    history_data[date][metric] = float(value)
                                except ValueError:
                                    history_data[date][metric] = 0.0
                            elif metric in ['bugs', 'vulnerabilities', 'security_hotspots', 
                                          'code_smells', 'major_violations',
                                          'minor_violations', 'violations']:
                                try:
                                    history_data[date][metric] = int(float(value)) if '.' in value else int(value)
                                except ValueError:
                                    history_data[date][metric] = 0
                            else:
                                history_data[date][metric] = value
                
                paging = response.get('paging', {})
                total = paging.get('total', 0)
                if page * page_size >= total:
                    break
                page += 1
            return list(history_data.values())
        except Exception as e:
            logging.warning(f"Failed to fetch history for {project_key}: {str(e)}")
            raise SonarCloudAPIError(f"Failed to fetch history: {e}")
    
    async def get_organization_metrics(self, organization: str) -> OrganizationMetrics:
        try:
            projects = await self.get_organization_projects(organization)
            metrics = OrganizationMetrics(total_projects=len(projects))
            
            coverage_sum = 0
            
            for project in projects:
                measures = await self.get_project_measures(project.key)
                if measures:
                    metrics.projects_with_data += 1
                    metrics.total_bugs += measures.get('bugs', 0)
                    metrics.total_vulnerabilities += measures.get('vulnerabilities', 0)
                    metrics.total_code_smells += measures.get('code_smells', 0)
                    
                    if 'coverage' in measures and measures['coverage'] > 0:
                        coverage_sum += measures['coverage']
            
            if metrics.projects_with_data > 0:
                metrics.avg_coverage = coverage_sum / metrics.projects_with_data
            
            return metrics
        except Exception as e:
            logging.error(f"Failed to fetch organization metrics: {str(e)}")
            raise SonarCloudAPIError(f"Failed to fetch organization metrics: {e}")
    
    async def get_project_branches(self, project_key: str) -> List[SonarBranch]:
        try:
            response = await self._make_async_request("project_branches/list", params={"project": project_key})
            return [SonarBranch(**b) for b in response.get('branches', [])]
        except Exception as e:
            logging.warning(f"Failed to fetch branches for {project_key}: {str(e)}")
            raise SonarCloudAPIError(f"Failed to fetch branches: {e}")
