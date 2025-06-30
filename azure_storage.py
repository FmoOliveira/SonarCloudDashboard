import os
from datetime import datetime
from azure.data.tables import TableServiceClient
import streamlit as st
import pandas as pd
from typing import Dict, List

class AzureTableStorage:
    """Azure Table Storage client for storing SonarCloud metrics"""
    
    def __init__(self, connection_string: str, table_name: str = "SonarCloudMetrics"):
        self.connection_string = connection_string
        self.table_name = table_name
        self.table_service_client = TableServiceClient.from_connection_string(connection_string)
        self.table_client = self.table_service_client.get_table_client(table_name)
        
        # Create table if it doesn't exist
        try:
            self.table_client.create_table()
        except Exception as e:
            # Table might already exist
            pass
    
    def store_metrics_data(self, metrics_data: pd.DataFrame, project_key: str, branch: str = None) -> bool:
        """Store metrics data in Azure Table Storage"""
        try:
            entities = []
            
            for _, row in metrics_data.iterrows():
                # Create partition key based on project and branch
                partition_key = f"{project_key}_{branch}" if branch else project_key
                
                # Create row key based on date and a timestamp for uniqueness
                date_str = str(row.get('date', datetime.now().strftime('%Y-%m-%d')))
                timestamp = datetime.now().strftime('%H%M%S%f')
                row_key = f"{date_str}_{timestamp}"
                
                # Create entity
                entity = {
                    "PartitionKey": partition_key,
                    "RowKey": row_key,
                    "ProjectKey": project_key,
                    "Branch": branch or "main",
                    "Date": date_str,
                    "Timestamp": datetime.now().isoformat(),
                }
                
                # Add all metrics to the entity
                metrics = [
                    'coverage', 'duplicated_lines_density', 'bugs', 'reliability_rating',
                    'vulnerabilities', 'security_rating', 'security_hotspots', 
                    'security_review_rating', 'security_hotspots_reviewed', 'code_smells', 
                    'sqale_rating', 'major_violations', 'minor_violations', 'violations'
                ]
                
                for metric in metrics:
                    if metric in row and pd.notna(row[metric]):
                        # Convert to appropriate type for Azure Table Storage
                        value = row[metric]
                        if isinstance(value, (int, float)):
                            entity[metric] = float(value)
                        else:
                            entity[metric] = str(value)
                    else:
                        entity[metric] = 0.0
                
                entities.append(entity)
            
            # Batch insert entities
            if entities:
                # Azure Table Storage supports batch operations for up to 100 entities
                batch_size = 100
                for i in range(0, len(entities), batch_size):
                    batch = entities[i:i + batch_size]
                    try:
                        # Use create_entity for individual inserts to handle duplicates
                        for entity in batch:
                            try:
                                self.table_client.create_entity(entity)
                            except Exception as e:
                                # If entity exists, update it
                                try:
                                    self.table_client.update_entity(entity, mode='replace')
                                except Exception as update_error:
                                    st.warning(f"Failed to store/update entity: {str(update_error)}")
                    except Exception as batch_error:
                        st.error(f"Failed to store batch: {str(batch_error)}")
                        return False
            
            return True
            
        except Exception as e:
            st.error(f"Failed to store metrics data: {str(e)}")
            return False
    
    def retrieve_metrics_data(self, project_key: str, branch: str = None, days: int = 30) -> List[Dict]:
        """Retrieve metrics data from Azure Table Storage"""
        try:
            partition_key = f"{project_key}_{branch}" if branch else project_key
            
            # Query entities for the specified partition
            filter_query = f"PartitionKey eq '{partition_key}'"
            
            # Add date filter for the last N days
            from datetime import timedelta
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            filter_query += f" and Date ge '{start_date}'"
            
            entities = self.table_client.query_entities(filter_query)
            
            # Convert entities to list of dictionaries
            results = []
            for entity in entities:
                # Convert entity to dictionary and clean up Azure metadata
                result = {}
                for key, value in entity.items():
                    if not key.startswith('_') and key not in ['PartitionKey', 'RowKey', 'Timestamp']:
                        if key == 'Date':
                            result['date'] = value
                        elif key == 'ProjectKey':
                            result['project_key'] = value
                        elif key == 'Branch':
                            result['branch'] = value
                        else:
                            result[key] = value
                
                results.append(result)
            
            return results
            
        except Exception as e:
            st.warning(f"Failed to retrieve metrics data: {str(e)}")
            return []
    
    def check_data_coverage(self, project_key: str, branch: str = None, days: int = 30) -> Dict[str, any]:
        """Check if we have sufficient data coverage for the requested period"""
        try:
            stored_data = self.retrieve_metrics_data(project_key, branch, days)
            
            if not stored_data:
                return {"has_coverage": False, "reason": "No stored data found"}
            
            import pandas as pd
            from datetime import datetime, timedelta
            
            df = pd.DataFrame(stored_data)
            if 'date' not in df.columns:
                return {"has_coverage": False, "reason": "No date column in stored data"}
            
            # Convert dates and check coverage
            df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce', utc=True)
            df['date'] = df['date'].dt.tz_localize(None)
            latest_stored = df['date'].max()
            oldest_stored = df['date'].min()

            now = datetime.now()  # Also naive
            
            # Make 100% sure both are naive
            def force_naive(dt):
                # Handles pd.Timestamp, datetime, or even np.datetime64
                if pd.isna(dt):
                    return dt
                if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                    # pandas Timestamp with tzinfo
                    return dt.tz_localize(None)
                return dt.replace(tzinfo=None) if hasattr(dt, 'replace') else pd.Timestamp(dt).to_pydatetime()

            latest_stored = force_naive(latest_stored)
            now = force_naive(now)

            # If latest_stored is NaT, handle gracefully
            if pd.isna(latest_stored):
                days_since_latest = float('inf')
            else:
                days_since_latest = (now - latest_stored).days
            
            # Check if we have sufficient data points
            required_min_records = max(1, days // 10)  # At least 1 record per 10 days requested
            has_sufficient_data = len(stored_data) >= required_min_records
            
            # Check required metrics are present
            required_metrics = ['vulnerabilities', 'security_hotspots', 'duplicated_lines_density', 
                              'security_rating', 'reliability_rating']
            missing_metrics = [m for m in required_metrics if m not in df.columns or df[m].isna().all()]
            
            has_coverage = (
                days_since_latest < 2 and  # Data is less than 2 days old
                has_sufficient_data and    # Sufficient number of records
                len(missing_metrics) == 0  # All required metrics present
            )
            
            return {
                "has_coverage": has_coverage,
                "record_count": len(stored_data),
                "latest_date": latest_stored.strftime('%Y-%m-%d'),
                "days_since_latest": days_since_latest,
                "missing_metrics": missing_metrics,
                "reason": f"Data coverage: {len(stored_data)} records, latest: {latest_stored.strftime('%Y-%m-%d')}"
            }
            
        except Exception as e:
            return {"has_coverage": False, "reason": f"Error checking coverage: {str(e)}"}
    
    def get_stored_projects(self) -> List[str]:
        """Get list of projects stored in Azure Table Storage"""
        try:
            # Query all entities and extract unique project keys
            entities = self.table_client.list_entities()
            projects = set()
            
            for entity in entities:
                if 'ProjectKey' in entity:
                    projects.add(entity['ProjectKey'])
            
            return list(projects)
            
        except Exception as e:
            st.warning(f"Failed to retrieve stored projects: {str(e)}")
            return []
    
    def delete_project_data(self, project_key: str, branch: str = None) -> bool:
        """Delete all data for a specific project and branch"""
        try:
            partition_key = f"{project_key}_{branch}" if branch else project_key
            filter_query = f"PartitionKey eq '{partition_key}'"
            
            entities = self.table_client.query_entities(filter_query)
            
            for entity in entities:
                self.table_client.delete_entity(
                    partition_key=entity['PartitionKey'],
                    row_key=entity['RowKey']
                )
            
            return True
            
        except Exception as e:
            st.error(f"Failed to delete project data: {str(e)}")
            return False