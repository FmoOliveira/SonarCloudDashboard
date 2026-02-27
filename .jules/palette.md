# Palette's Design Journal 🎨

## Critical Learnings

### Streamlit Layout Quirk: Stacking Order
*   **Observation**: When using `st.columns`, if the total width of elements exceeds the viewport width on mobile, they stack vertically. However, `st.expander` inside columns can behave unpredictably if not carefully sized.
*   **Fix**: Always test layout responsiveness. Use `use_container_width=True` on charts and dataframes to ensure they resize gracefully within their parent containers.

### State Persistence during Reruns
*   **Observation**: Input widgets (like `st.selectbox` or `st.text_input`) reset their state if they are conditionally rendered and the condition changes (removing them from the widget tree).
*   **Fix**: To preserve state across conditional renders, use `st.session_state` explicitly or ensure the widget key remains stable and present in the widget tree.

### Feedback Loop Importance
*   **Observation**: Long-running operations (like API fetches) without visual feedback lead to user frustration and "is it broken?" thoughts.
*   **Fix**: Always wrap blocking calls in `st.spinner` or `st.status`. Use `st.toast` for non-blocking notifications upon completion.

### Visual Hierarchy
*   **Observation**: Too many primary buttons or high-contrast elements compete for attention.
*   **Fix**: Use `type="primary"` sparingly for the main action. Use `type="secondary"` (default) for auxiliary actions. Use `st.divider()` or whitespace to separate logical sections.

### Empty States
*   **Observation**: An empty dataframe or chart looks like a bug.
*   **Fix**: Always check for `if df.empty:` and render a helpful `st.info` or `st.warning` message explaining why no data is shown (e.g., "No data found for the selected time range.").
