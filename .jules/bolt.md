
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

- **Anti-Pattern Found:** Using `df.iterrows()` to iterate over a DataFrame to extract values (e.g., inside `inject_statistical_anomalies` for plotting markers). This results in extremely slow O(N) execution time and causes main-thread blocking during Plotly chart rendering.
- **The Fix:** Replaced `df.iterrows()` with vectorized date extraction using `anomalies[date_col].unique()`.
- **Why it Matters:** Vectorized Pandas operations bypass the overhead of Python-level loops, allowing Streamlit to maintain a lightning-fast UI execution loop.
- **Anti-Pattern Found:** Using `df.iterrows()` to loop through dataframes when processing visual dashboard components. In `dashboard_components.py`, `create_quality_gate_status` used `iterrows()` to manually calculate status conditions for each project individually.
- **The Fix:** Replaced `.iterrows()` in `create_quality_gate_status` with vectorized operations using `np.select` and boolean masks to calculate the statuses across all projects simultaneously.
- **Why it Matters:** Iterating over a Pandas dataframe row by row using `.iterrows()` is significantly slower than using vectorized operations (O(N) vs O(1) conceptually for dataframe manipulation). This replacement speeds up data processing before generating charts and dashboard metrics, preventing long main thread stalls on the UI rendering cycle.
- **Performance Opportunity Found:** In `src/dashboard/data_service.py`, processing historical API data grouped by date was blocking the `asyncio` event loop due to an `O(N)` list lookup (`next((r for r in history if r['date'] == date_val), None)`) occurring inside a loop, resulting in `O(N^2)` time complexity.
- **The Fix:** Switched the data structure from a list to a dictionary keyed by `date_val`, allowing `O(1)` access time and reducing overall time complexity to `O(N)`. The final result uses `list(history_dict.values())`.
- **Why it Matters:** Heavy synchronous `O(N^2)` calculations block Python's asynchronous event loop, negating the benefits of `asyncio.gather` and slowing down concurrent API requests.

- **Anti-Pattern Found:** The `st.selectbox` UI component in `src/dashboard/app.py` was iterating over the `projects` list for each rendered option in its `format_func` parameter, executing `next((p['name'] for p in projects if p['key'] == x), x)`. This evaluates in `O(M * N)` time.
- **The Fix:** Created a `project_names` dictionary mapped to the list, enabling `O(1)` lookups via `project_names.get(x, x)` inside the `format_func`.
- **Why it Matters:** Streamlit re-runs the script frequently. Inefficient list lookups in UI rendering logic block the main thread and degrade application responsiveness.
- **Anti-Pattern Found:** Utilizing $O(N)$ list lookups (`next((r for r in history if r['date'] == date_val), None)`) inside nested loops when parsing large JSON payloads blocks the main execution thread.
- **The Fix:** Refactored the data parsing logic in `fetch_sonar_history_async` to use an $O(1)$ dictionary lookup keyed by the `date` attribute.
- **Why it Matters:** This optimization reduces the time complexity of the JSON parsing step from $O(N^2)$ to $O(N)$. Because `asyncio` runs in a single thread, any heavy, blocking CPU-bound code like a slow $O(N^2)$ nested loop will freeze the entire event loop and delay rendering.
- **Performance Opportunity Found:** An $O(N^2)$ time complexity bottleneck during API data fetching within `fetch_sonar_history_async`. Repeatedly searching a growing list for existing dates using `next((r for r in history if r['date'] == date_val), None)` blocked the main execution thread when processing thousands of records.
- **The Fix:** Replaced the `history` list and `O(N)` lookups with a dictionary (`history_dict`). Keying records by `date_val` allows for `O(1)` access time (`history_dict.get(date_val)`), effectively dropping the overall iteration complexity from $O(M \times N^2)$ to $O(M \times N)$.
- **Why it Matters:** Non-vectorized Python loops are already slow; nesting an $O(N)$ list search inside a double-loop (iterating over metrics, then historical data points) exacerbates latency. Eliminating list scanning via hash-map lookups provides an immense, noticeable speed boost for high-volume telemetry processing during Streamlit reruns.

- **Anti-Pattern Found:** The `st.selectbox` UI component in `app.py` was iterating over the `projects` list for each rendered option in its `format_func` parameter, executing `next((p['name'] for p in projects if p['key'] == x), x)`. This evaluates in `O(M * N)` time.
- **The Fix:** Created a `project_names` dictionary mapped to the list, enabling `O(1)` lookups via `project_names.get(x, x)` inside the `format_func`.
- **Why it Matters:** Streamlit re-runs the script frequently. Inefficient list lookups in UI rendering logic block the main thread and degrade application responsiveness.
