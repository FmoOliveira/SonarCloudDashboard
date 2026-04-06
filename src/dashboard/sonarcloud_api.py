import logging
import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from constants import SONAR_METRICS
from models import SonarProject, SonarMeasure, OrganizationMetrics, SonarBranch


class SonarCloudAPIError(Exception):
    """Structured API error carrying the originating HTTP status code."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SonarCloudAPI:
    """SonarCloud API client for fetching organization and project metrics."""
    
    def __init__(self, token: str, session: aiohttp.ClientSession):
        self.token = token
        self.session = session
        self.base_url = "https://sonarcloud.io/api"
        self.headers = {'Authorization': f'Bearer {token}'}
        
    async def _make_async_request(self, endpoint: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        async with self.session.get(url, params=params, headers=self.headers) as response:
            if response.status == 200:
                return await response.json()
            error_msg = await response.text()
            raise SonarCloudAPIError(
                f"API request failed with status {response.status}: {error_msg}",
                status_code=response.status,
            )

    async def _fetch_page(self, url: str, params: dict) -> dict:
        async with self.session.get(url, params=params, headers=self.headers) as response:
            if response.status == 200:
                return await response.json()
            error_msg = await response.text()
            raise SonarCloudAPIError(
                f"API request failed with status {response.status}: {error_msg}",
                status_code=response.status,
            )

    async def get_organization_projects(self, organization: str) -> List[SonarProject]:
        projects = []
        page_size = 500
        url = f"{self.base_url}/projects/search"
        params = {"organization": organization, "qualifiers": "TRK", "f": "name,key", "ps": page_size, "p": 1}
        
        # Raises — caught by the caller in data_service
        first_page = await self._fetch_page(url, params)
        for comp in first_page.get('components', []):
            projects.append(SonarProject(**comp))
        
        total = first_page.get('paging', {}).get('total', 0)
        if total > page_size:
            total_pages = (total + page_size - 1) // page_size
            tasks = []
            for page in range(2, total_pages + 1):
                p = params.copy()
                p['p'] = page
                tasks.append(self._fetch_page(url, p))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    # Log individual page failures but continue — partial results are acceptable
                    logging.warning(f"Failed to fetch a projects page: {r}")
                else:
                    for comp in r.get('components', []):
                        projects.append(SonarProject(**comp))
                
        return projects
    
    async def get_project_measures(self, project_key: str, branch: Optional[str] = None) -> Optional[Dict[str, float]]:
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
                item['value'] = item.get('value', '0')
                measure = SonarMeasure(**item)
                measures[measure.metric] = measure.parsed_value
        
        return measures if measures else None

    async def get_project_history(self, project_key: str, days: int, branch: Optional[str] = None) -> List[Dict]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
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
            
            response = await self._fetch_page(url, params)
            
            if 'measures' in response:
                for item in response['measures']:
                    metric = item['metric']
                    for history_point in item.get('history', []):
                        date = history_point['date']
                        value = history_point.get('value', '0')
                        
                        if date not in history_data:
                            history_data[date] = {'date': date}
                        
                        measure = SonarMeasure(metric=metric, value=str(value))
                        history_data[date][metric] = measure.parsed_value
            
            paging = response.get('paging', {})
            total = paging.get('total', 0)
            if page * page_size >= total:
                break
            page += 1

        return list(history_data.values())
    
    async def get_organization_metrics(self, organization: str) -> OrganizationMetrics:
        """
        Fetches per-project measures concurrently using asyncio.gather.
        Replaces the previous O(N) sequential loop with O(1) concurrent network time.
        """
        projects = await self.get_organization_projects(organization)
        metrics = OrganizationMetrics(total_projects=len(projects))
        coverage_sum = 0.0
        
        # Fan out all measure requests concurrently
        tasks = [self.get_project_measures(p.key) for p in projects]
        all_measures = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in all_measures:
            if isinstance(result, Exception):
                logging.warning(f"Failed to fetch measures for a project: {result}")
                continue
            if result:
                metrics.projects_with_data += 1
                metrics.total_bugs += int(result.get('bugs', 0))
                metrics.total_vulnerabilities += int(result.get('vulnerabilities', 0))
                metrics.total_code_smells += int(result.get('code_smells', 0))
                if 'coverage' in result and result['coverage'] > 0:
                    coverage_sum += float(result['coverage'])
        
        if metrics.projects_with_data > 0:
            metrics.avg_coverage = coverage_sum / metrics.projects_with_data
        
        return metrics
    
    async def get_project_branches(self, project_key: str) -> List[SonarBranch]:
        response = await self._make_async_request("project_branches/list", params={"project": project_key})
        return [SonarBranch(**b) for b in response.get('branches', [])]
