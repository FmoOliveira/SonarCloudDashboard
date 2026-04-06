from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class SonarProject(BaseModel):
    model_config = ConfigDict(extra='ignore')
    key: str
    name: str

class SonarMeasure(BaseModel):
    model_config = ConfigDict(extra='ignore')
    metric: str
    value: str = '0'
    bestValue: Optional[bool] = None

    @computed_field
    @property
    def parsed_value(self) -> Union[float, int, str]:
        if self.metric in ['coverage', 'duplicated_lines_density', 'security_hotspots_reviewed']:
            try:
                return float(self.value)
            except ValueError:
                return 0.0
        elif self.metric in ['bugs', 'vulnerabilities', 'security_hotspots', 
                              'code_smells', 'major_violations', 'minor_violations', 'violations']:
            try:
                if '.' in self.value:
                    return int(float(self.value))
                return int(self.value)
            except (ValueError, TypeError):
                return 0
        return self.value

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
