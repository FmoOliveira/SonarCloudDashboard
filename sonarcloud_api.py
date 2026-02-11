import requests
import os
from typing import List, Dict, Optional
import streamlit as st

class SonarCloudAPI:
    """SonarCloud API client for fetching organization and project metrics"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://sonarcloud.io/api"
        self.session = requests.Session()
        self.session.auth = (token, '')
        
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
        """Get all projects in the organization"""
        try:
            response = self._make_request(
                "projects/search",
                params={
                    "organization": organization,
                    "ps": 500  # Page size
                }
            )
            return response.get('components', [])
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
        """Get historical measures for a project"""
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
            params = {
                "component": project_key,
                "metrics": ",".join(metrics),
                "from": start_date.strftime('%Y-%m-%d'),
                "to": end_date.strftime('%Y-%m-%d'),
                "ps": 1000  # Page size to get all historical data points
            }
            
            # Add branch parameter if specified
            if branch and branch.strip():
                params["branch"] = branch.strip()
            
            response = self._make_request("measures/search_history", params=params)
            
            history = []
            if 'measures' in response:
                # Organize data by date
                dates_data = {}
                
                for measure in response['measures']:
                    metric = measure['metric']
                    for history_point in measure.get('history', []):
                        date = history_point['date']
                        value = history_point.get('value', '0')
                        
                        if date not in dates_data:
                            dates_data[date] = {'date': date}
                        
                        # Convert to appropriate type
                        if metric in ['coverage', 'duplicated_lines_density']:
                            try:
                                dates_data[date][metric] = float(value)
                            except ValueError:
                                dates_data[date][metric] = 0.0
                        elif metric in ['bugs', 'vulnerabilities', 'security_hotspots', 
                                      'code_smells', 'major_violations',
                                      'minor_violations', 'violations']:
                            try:
                                dates_data[date][metric] = int(value)
                            except ValueError:
                                dates_data[date][metric] = 0
                        elif metric in ['security_hotspots_reviewed']:
                            try:
                                # This metric can be a percentage, treat as float
                                dates_data[date][metric] = float(value)
                            except ValueError:
                                dates_data[date][metric] = 0.0
                        else:
                            dates_data[date][metric] = value
                
                history = list(dates_data.values())
            
            return history
            
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
