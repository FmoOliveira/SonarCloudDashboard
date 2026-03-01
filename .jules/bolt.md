
- **Codebase-specific anti-pattern:** Iterating Pandas dataframes project-by-project instead of using vectorization (`df.groupby('project_key').first()/last()`). Iterating over projects caused O(M*N) latency on the Streamlit rerun thread. Replaced with vectorized `groupby().first()/last()` for O(N) execution.
