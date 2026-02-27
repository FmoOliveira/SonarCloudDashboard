import os
import pandas as pd
from unittest.mock import MagicMock, patch

# Mock the secrets
os.environ["STREAMLIT_SECRETS_SONARCLOUD_API_TOKEN"] = "mock_token"
os.environ["STREAMLIT_SECRETS_SONARCLOUD_ORGANIZATION_KEY"] = "mock_org"
os.environ["STREAMLIT_SECRETS_DATABASE_PROVIDER"] = "azure"

MOCK_METRICS = pd.DataFrame([{
    "date": "2023-01-01",
    "project_key": "test_project",
    "branch": "master",
    "vulnerabilities": 10,
    "bugs": 5,
    "security_hotspots": 2,
    "code_smells": 20,
    "coverage": 85.5,
    "duplicated_lines_density": 3.2,
    "security_rating": 1.0,
    "reliability_rating": 2.0,
    "sqale_rating": 1.0,
    "security_review_rating": 1.0,
    "violations": 5,
    "major_violations": 2,
    "minor_violations": 1,
}])

def test_dataframe_columns():
    """
    Since AppTest is struggling with the complex sidebar form, we will test
    the 'display_dashboard' function logic directly in isolation, as that
    is where the dataframe logic resides.
    """
    print("Testing display_dashboard logic directly...")

    from app import display_dashboard
    import streamlit as st

    # We need to mock st.dataframe to inspect the arguments passed to it
    with patch("streamlit.dataframe") as mock_dataframe, \
         patch("streamlit.columns") as mock_columns, \
         patch("streamlit.markdown"), \
         patch("streamlit.pills"), \
         patch("streamlit.multiselect"), \
         patch("streamlit.selectbox"), \
         patch("streamlit.toggle"):

        # Mock st.columns to return mocks
        # st.columns is called multiple times.
        # 1. 5 columns for overview stats
        # 2. 2 columns for metric selection
        mock_col = MagicMock()
        mock_columns.side_effect = [
            [mock_col] * 5, # For overview stats
            [mock_col] * 2  # For metric selection
        ]

        # Setup session state for the function
        if "metric_selector" not in st.session_state:
            st.session_state["metric_selector"] = ["vulnerabilities"]

        # Call the function
        projects = [{"key": "test_project", "name": "Test Project"}]
        display_dashboard(MOCK_METRICS.copy(), ["test_project"], projects, "master")

        # Verify st.dataframe was called
        # Note: st.dataframe might be called inside an expander (Debug info) too.
        # We need the one with column_config.

        found_call = False
        for call in mock_dataframe.call_args_list:
            args, kwargs = call
            column_config = kwargs.get("column_config")

            if column_config:
                found_call = True
                print("Found st.dataframe call with column_config!")

                # 1. Check Dataframe Content (Numeric Ratings)
                df_passed = args[0]
                # print("Dataframe passed:", df_passed)

                if pd.api.types.is_numeric_dtype(df_passed['security_rating']):
                    print("SUCCESS: security_rating is numeric!")
                else:
                    print(f"FAILURE: security_rating is {df_passed['security_rating'].dtype}")
                    exit(1)

                # 2. Check Column Config Keys
                if "coverage" in column_config:
                    print("SUCCESS: 'coverage' config found!")
                else:
                    print("FAILURE: 'coverage' config missing")
                    exit(1)

                if "security_rating" in column_config:
                     print("SUCCESS: 'security_rating' config found!")
                else:
                     print("FAILURE: 'security_rating' config missing")
                     exit(1)

                break

        if not found_call:
            print("FAILURE: st.dataframe call with column_config was NOT found.")
            exit(1)

if __name__ == "__main__":
    test_dataframe_columns()
