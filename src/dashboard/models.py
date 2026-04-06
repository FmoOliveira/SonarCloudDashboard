from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class SonarProject(BaseModel):
    model_config = ConfigDict(extra='ignore')
    key: str
    name: str

class SonarMeasure(BaseModel):
    model_config = ConfigDict(extra='ignore')
    metric: str
    value: Optional[str] = None
    bestValue: Optional[bool] = None

class OrganizationMetrics(BaseModel):
    total_projects: int = 0
    total_bugs: int = 0
    total_vulnerabilities: int = 0
    total_code_smells: int = 0
    avg_coverage: float = 0.0
    projects_with_data: int = 0

class SonarBranch(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: str
    isMain: Optional[bool] = False
    status: Optional[Dict[str, Any]] = None
