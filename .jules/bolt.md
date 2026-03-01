# Bolt's Journal: Critical Learnings

- **Anti-Pattern Found:** Iterating over unique values in a Pandas DataFrame (e.g., looping through project IDs) and manually filtering the dataframe for each iteration (`df[df['col'] == val]`) creates an $O(M \times N)$ execution time bottleneck.
- **The Fix:** Replaced manual loops with vectorized `.groupby()` operations. Specifically, calculating the latest and earliest metric values across multiple projects was sped up drastically by using `df.groupby('project_key').last()` and `first()`.
- **Why it Matters:** Streamlit re-executes the script from top to bottom. Any slow data processing blocks the main execution thread, causing the UI to freeze. Vectorized Pandas operations ensure lightning-fast UI reruns.
