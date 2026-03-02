import pandas as pd
from abc import ABC, abstractmethod


class StorageInterface(ABC):
    """
    Abstract Base Class defining the contract for any metrics database backend.
    """

    @abstractmethod
    def get_stored_projects(self) -> list:
        """
        Retrieves a list of project keys currently stored in the database.
        
        Returns:
            list: A list of strings representing project keys.
        """
        pass

    @abstractmethod
    def check_data_coverage(self, project_key: str, branch: str, days: int) -> dict:
        """
        Checks if the database has sufficient historical data for the requested project
        and time window.
        
        Args:
            project_key (str): The unique identifier for the project.
            branch (str): The branch name.
            days (int): The number of days of history required.
            
        Returns:
            dict: Expected to contain boolean 'has_coverage', list/DataFrame 'data',
                  and string 'latest_date'.
        """
        pass

    @abstractmethod
    def store_metrics_data(self, df: pd.DataFrame, project_key: str, branch: str) -> bool:
        """
        Persists a block of metrics data (represented as a Pandas DataFrame) into the database.
        
        Args:
            df (pd.DataFrame): The metrics data to store.
            project_key (str): The specific project this data belongs to.
            branch (str): The corresponding branch.
            
        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        pass
