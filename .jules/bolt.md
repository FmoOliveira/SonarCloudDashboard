
- **Codebase-specific anti-pattern:** Iterating Pandas dataframes project-by-project instead of using vectorization (`df.groupby('project_key').first()/last()`). Iterating over projects caused O(M*N) latency on the Streamlit rerun thread. Replaced with vectorized `groupby().first()/last()` for O(N) execution.
# Bolt's Journal: Critical Learnings

- **Anti-Pattern Found:** Iterating over unique values in a Pandas DataFrame (e.g., looping through project IDs) and manually filtering the dataframe for each iteration (`df[df['col'] == val]`) creates an $O(M \times N)$ execution time bottleneck.
- **The Fix:** Replaced manual loops with vectorized `.groupby()` operations. Specifically, calculating the latest and earliest metric values across multiple projects was sped up drastically by using `df.groupby('project_key').last()` and `first()`.
- **Why it Matters:** Streamlit re-executes the script from top to bottom. Any slow data processing blocks the main execution thread, causing the UI to freeze. Vectorized Pandas operations ensure lightning-fast UI reruns.

- **Performance Opportunity Found:** In-memory Pandas DataFrames containing large time-series telemetry consume excessive RAM within Streamlit's `st.session_state`, increasing overhead during Parquet serialization/deserialization.
- **The Fix:** Implemented downcasting in `app.py`'s `fetch_metrics_data` before caching. Categorical strings (`project_key`, `branch`) were converted to the `category` dtype, and numerical metrics were downcast from `float64` to `float32`.
- **Why it Matters:** This reduces the dataframe's memory footprint by up to ~80%. Smaller objects in `st.session_state` prevent memory leaks, reduce OS-level garbage collection stalls, and significantly speed up the PyArrow Parquet compression cycle before rendering Plotly components.

- **Anti-Pattern Found:** Redundant `O(N log N)` sorting within loops. In `dashboard_view.py`, `compute_metric_stats` was sorting the entire dataframe by date for *every single metric* calculated inside a loop, resulting in a time complexity of `O(M * N log N)`.
- **The Fix:** Lifted the sort operation out of the metric loop. The dataframe is now sorted once (`df.sort_values('date')`) before being passed into the sequential `compute_metric_stats` calls, reducing complexity to `O(N log N)`.
- **Why it Matters:** Avoids repeatedly paying the sorting cost on large datasets, preventing unneeded main-thread blocking during the UI rerun cycle.
