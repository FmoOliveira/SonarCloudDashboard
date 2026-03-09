import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_demo_data():
    """Synthesizes 90 days of realistic, randomized metrics across 3 mock projects."""
    print("Generating synthetic demo metrics...")
    
    projects = [
        {"key": "demo-project-alpha", "name": "Frontend Web Application"},
        {"key": "demo-project-beta", "name": "Backend Python API"},
        {"key": "demo-project-gamma", "name": "Mobile iOS App"}
    ]
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    all_data = []
    
    for project in projects:
        # Create a baseline that randomly drifts to simulate actual development cycles
        base_vulnerabilities = np.random.randint(5, 20)
        base_hotspots = np.random.randint(20, 50)
        base_bugs = np.random.randint(10, 30)
        base_duplication = np.random.uniform(2.0, 15.0)
        
        for i, current_date in enumerate(dates):
            # Introduce a slight random walk / trend
            drift = np.sin(i / 10.0) * 5 + np.random.normal(0, 2)
            
            # Simulate less activity on weekends
            if current_date.weekday() >= 5:
                drift *= 0.1
                
            vulnerabilities = max(0, int(base_vulnerabilities + drift))
            hotspots = max(0, int(base_hotspots + (drift * 2)))
            bugs = max(0, int(base_bugs + drift))
            duplication = max(0.0, base_duplication + (drift / 5.0))
            
            # Map SonarCloud ratings based on issue counts
            sec_rating = 1.0 if vulnerabilities == 0 else min(5.0, 1.0 + (vulnerabilities / 5))
            rel_rating = 1.0 if bugs == 0 else min(5.0, 1.0 + (bugs / 10))
            
            record = {
                "project_key": project["key"],
                "project_name": project["name"],
                "branch": "main",
                "date": current_date.strftime("%Y-%m-%d"),
                
                # Core Metrics
                "vulnerabilities": vulnerabilities,
                "security_hotspots": hotspots,
                "bugs": bugs,
                "duplicated_lines_density": round(duplication, 1),
                "coverage": round(max(50.0, min(100.0, 85.0 + np.random.normal(0, 3))), 1),
                
                # Ratings
                "security_rating": sec_rating,
                "reliability_rating": rel_rating,
                "sqale_rating": max(1.0, min(5.0, 1.0 + (duplication / 5))),
                
                # Code Smells & Violations
                "code_smells": max(0, int(100 + (drift * 10))),
                "violations": max(0, int(150 + (drift * 15))),
                "major_violations": max(0, int(30 + (drift * 5))),
                "minor_violations": max(0, int(120 + (drift * 10))),
            }
            all_data.append(record)
            
    df = pd.DataFrame(all_data)
    
    # Save to parquet
    output_path = os.path.join(os.path.dirname(__file__), "demo_metrics.parquet")
    df.to_parquet(output_path, engine="pyarrow", compression="snappy")
    print(f"Successfully generated {len(df)} records at {output_path}")

if __name__ == "__main__":
    generate_demo_data()
