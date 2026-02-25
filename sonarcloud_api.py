import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from typing import List, Dict, Optional
import streamlit as st

class SonarCloudAPI:
    """SonarCloud API client for fetching organization and project metrics"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://sonarcloud.io/api"
        self.session = requests.Session()
        
        # Update to Bearer token per v2 API standard
        self.session.headers.update({'Authorization': f'Bearer {token}'})
        
        # Configure urllib3 Retry adapter to handle HTTP 429 and 5xx errors
        retries = Retry(
            total=5,
            backoff_factor=1, # 1s, 2s, 4s, 8s, 16s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
    def _make_request(self, endpoint: str, params: Dict = None, timeout: int = 30) -> Dict:
        """Make authenticated request to SonarCloud API"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def get_organization_projects(self, organization: str) -> List[Dict]:
        """Get all projects in the organization using pagination"""
        projects = []
        page = 1
        page_size = 500
        
        try:
            while True:
                response = self._make_request(
                    "projects/search",
                    params={
                        "organization": organization,
                        "qualifiers": "TRK",      # Only fetch actual projects
                        "f": "name,key",          # Optimize: Only fetch necessary fields
                        "ps": page_size,          # Page size
                        "p": page                 # Page number
                    }
                )
                
                components = response.get('components', [])
                projects.extend(components)
                
                # Check Pagination
                paging = response.get('paging', {})
                total = paging.get('total', 0)
                
                if page * page_size >= total:
                    break # We have fetched all projects
                    
                page += 1
                
            return projects
            
        except Exception as e:
            st.error(f"Failed to fetch projects: {str(e)}")
            return []
    
    def get_project_measures(self, project_key: str, branch: str = None) -> Optional[Dict]:
        """Get current measures for a project"""
        metrics = [
            'coverage',
            'duplicated_lines_density',
            'bugs',
            'reliability_rating',
            'vulnerabilities',
            'security_rating',
            'security_hotspots',
            'security_review_rating',
            'security_hotspots_reviewed',
            'code_smells',
            'sqale_rating',
            'major_violations',
            'minor_violations',
            'violations'
        ]
        
        try:
            params = {
                "component": project_key,
                "metricKeys": ",".join(metrics)
            }
            
            # Add branch parameter if specified
            if branch and branch.strip():
                params["branch"] = branch.strip()
            
            response = self._make_request("measures/component", params=params)
            
            # Parse measures into a dictionary
            measures = {}
            if 'component' in response and 'measures' in response['component']:
                for measure in response['component']['measures']:
                    metric = measure['metric']
                    value = measure.get('value', '0')
                    
                    # Convert to appropriate type
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
            st.warning(f"Failed to fetch measures for {project_key}: {str(e)}")
            return None
    
    def get_project_history(self, project_key: str, days: int, branch: str = None) -> List[Dict]:
        """Get historical measures for a project using pagination"""
        from datetime import datetime, timedelta
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        metrics = [
            'coverage',
            'duplicated_lines_density',
            'bugs',
            'reliability_rating',
            'vulnerabilities',
            'security_rating',
            'security_hotspots',
            'security_review_rating',
            'security_hotspots_reviewed',
            'code_smells',
            'sqale_rating',
            'major_violations',
            'minor_violations',
            'violations'
        ]
        
        try:
            history_data = {}
            page = 1
            page_size = 1000
            
            while True:
                params = {
                    "component": project_key,
                    "metrics": ",".join(metrics),
                    "from": start_date.strftime('%Y-%m-%d'),
                    "to": end_date.strftime('%Y-%m-%d'),
                    "ps": page_size,
                    "p": page
                }
                
                # Add branch parameter if specified
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
                            
                            # Convert to appropriate type
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
                
                # Check pagination bounds
                paging = response.get('paging', {})
                total = paging.get('total', 0)
                
                if page * page_size >= total:
                    break
                    
                page += 1
                
            return list(history_data.values())
            
        except Exception as e:
            st.warning(f"Failed to fetch history for {project_key}: {str(e)}")
            return []
    
    def get_organization_metrics(self, organization: str) -> Dict:
        """Get organization-level metrics summary"""
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
            st.error(f"Failed to fetch organization metrics: {str(e)}")
            return {}
    
    def get_project_branches(self, project_key: str) -> List[Dict]:
        """Get all branches for a project"""
        try:
            response = self._make_request(
                "project_branches/list",
                params={"project": project_key}
            )
            return response.get('branches', [])
        except Exception as e:
            st.warning(f"Failed to fetch branches for {project_key}: {str(e)}")
            return []
