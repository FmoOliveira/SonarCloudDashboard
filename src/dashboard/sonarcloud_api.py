import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Optional
import asyncio
import aiohttp
from constants import SONAR_METRICS

class SonarCloudAPIError(Exception): 
    pass

class SonarCloudAPI:
    """SonarCloud API client for fetching organization and project metrics"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://sonarcloud.io/api"
        self.session = requests.Session()
        
        self.session.headers.update({'Authorization': f'Bearer {token}'})
        
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
    def _make_request(self, endpoint: str, params: Dict = None, timeout: int = 30) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise SonarCloudAPIError(f"API request failed: {str(e)}")
            
    async def _fetch_projects_page(self, session, url, params) -> Dict:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                return await response.json()
            raise SonarCloudAPIError(f"Async API request failed with status {response.status}")

    async def _get_organization_projects_async(self, organization: str) -> List[Dict]:
        projects = []
        page_size = 500
        url = f"{self.base_url}/projects/search"
        params = {"organization": organization, "qualifiers": "TRK", "f": "name,key", "ps": page_size, "p": 1}
        headers = {'Authorization': f'Bearer {self.token}'}
        
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                first_page = await self._fetch_projects_page(session, url, params)
                projects.extend(first_page.get('components', []))
                
                total = first_page.get('paging', {}).get('total', 0)
                if total > page_size:
                    tasks = []
                    total_pages = (total + page_size - 1) // page_size
                    for page in range(2, total_pages + 1):
                        p = params.copy()
                        p['p'] = page
                        tasks.append(self._fetch_projects_page(session, url, p))
                    
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for r in results:
                            if isinstance(r, Exception):
                                logging.error(f"Failed to fetch projects page: {r}")
                            else:
                                projects.extend(r.get('components', []))
            except Exception as e:
                logging.error(f"Failed to fetch initial projects: {e}")
                raise SonarCloudAPIError(f"Error fetching projects: {e}")
                
        return projects

    def get_organization_projects(self, organization: str) -> List[Dict]:
        """Get all projects in the organization using concurrent asynchronous fetching"""
        # If there's an existing loop, use it; otherwise create a new one via run()
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self._get_organization_projects_async(organization))
        except RuntimeError:
            return asyncio.run(self._get_organization_projects_async(organization))
    
    def get_project_measures(self, project_key: str, branch: str = None) -> Optional[Dict]:
        try:
            params = {
                "component": project_key,
                "metricKeys": ",".join(SONAR_METRICS)
            }
            if branch and branch.strip():
                params["branch"] = branch.strip()
            
            response = self._make_request("measures/component", params=params)
            
            measures = {}
            if 'component' in response and 'measures' in response['component']:
                for measure in response['component']['measures']:
                    metric = measure['metric']
                    value = measure.get('value', '0')
                    
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
    
    def get_project_history(self, project_key: str, days: int, branch: str = None) -> List[Dict]:
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            history_data = {}
            page = 1
            page_size = 1000
            
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
                
                response = self._make_request("measures/search_history", params=params)
                
                if 'measures' in response:
                    for measure in response['measures']:
                        metric = measure['metric']
                        for history_point in measure.get('history', []):
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
    
    def get_organization_metrics(self, organization: str) -> Dict:
        try:
            projects = self.get_organization_projects(organization)
            
            total_metrics = {
                'total_projects': len(projects),
                'total_bugs': 0,
                'total_vulnerabilities': 0,
                'total_code_smells': 0,
                'avg_coverage': 0,
                'projects_with_data': 0
            }
            
            coverage_sum = 0
            projects_with_coverage = 0
            
            for project in projects:
                measures = self.get_project_measures(project['key'])
                if measures:
                    total_metrics['projects_with_data'] += 1
                    total_metrics['total_bugs'] += measures.get('bugs', 0)
                    total_metrics['total_vulnerabilities'] += measures.get('vulnerabilities', 0)
                    total_metrics['total_code_smells'] += measures.get('code_smells', 0)
                    
                    if 'coverage' in measures and measures['coverage'] > 0:
                        coverage_sum += measures['coverage']
                        projects_with_coverage += 1
            
            if projects_with_coverage > 0:
                total_metrics['avg_coverage'] = coverage_sum / projects_with_coverage
            
            return total_metrics
            
        except Exception as e:
            logging.error(f"Failed to fetch organization metrics: {str(e)}")
            raise SonarCloudAPIError(f"Failed to fetch organization metrics: {e}")
    
    def get_project_branches(self, project_key: str) -> List[Dict]:
        try:
            response = self._make_request(
                "project_branches/list",
                params={"project": project_key}
            )
            return response.get('branches', [])
        except Exception as e:
            logging.warning(f"Failed to fetch branches for {project_key}: {str(e)}")
            raise SonarCloudAPIError(f"Failed to fetch branches: {e}")
