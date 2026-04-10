import pandas as pd
from abc import ABC, abstractmethod
from typing import TypedDict, Union, Optional
from typing_extensions import NotRequired


class DataCoverage(TypedDict):
    """
    Typed contract for the return value of StorageInterface.check_data_coverage().
    Replaces the opaque 'dict' annotation to enable static analysis and IDE completion.
    """
    has_coverage: bool
    data: Union[pd.DataFrame, list]
    latest_date: Union[str, None]
    record_count: NotRequired[Optional[int]]
    days_since_latest: NotRequired[Optional[int]]
    missing_metrics: NotRequired[Optional[list[str]]]


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
    def check_data_coverage(self, project_key: str, branch: str, days: int) -> DataCoverage:
        """
        Checks if the database has sufficient historical data for the requested project
        and time window.
        
        Args:
            project_key (str): The unique identifier for the project.
            branch (str): The branch name.
            days (int): The number of days of history required.
            
        Returns:
            DataCoverage: A typed dict containing has_coverage, data, and latest_date.
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
