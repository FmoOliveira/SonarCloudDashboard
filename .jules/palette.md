# Palette's Journal

Critical UX learnings and observations only.

*   A reusable UI pattern for handling table exports: `st.download_button` can utilize `use_container_width=True` to match the width of `st.dataframe(..., use_container_width=True)`, which prevents visual layout jumps when rendering tabular data alongside export actions. Adding `icon` and `help` tooltips further clarifies the context and maintains the UI consistency.
# Palette's Journal - Critical Learnings Only

* Using `st.info` with custom icons rather than plain `st.write` or missing states is important for empty dataframes.
* Custom dates should be explicit.
* Date inputs should use explicit `format` strings to guide users and `help` tooltips.
* Empty search results (like returning no data for a timeframe) shouldn't be treated as critical application errors in `st.status`. Complete the status cleanly and render a helpful `st.info` block guiding the user to adjust filters.
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

* Using explicit icons on feedback widgets (`st.info`, `st.warning`, `st.error`) drastically improves visual hierarchy. Users can scan errors or warnings quickly. This was missing in several places in the dashboard which resulted in inconsistent visual state representations.
*   **Streamlit Form State-Loss Bug**: Input widgets (like `st.selectbox` and conditional `st.date_input`) must not be placed inside an `st.form` if selecting them needs to trigger a conditional UI re-render (like showing an extra date field for a "Custom range" option). The script rerun cycle will ignore these inputs until the whole form is submitted, destroying the intended interactive UX. Keep conditional trigger inputs OUTSIDE the form.

### Unintended Script Halting (st.stop Layout Bug)
*   **Observation**: Using `st.stop()` within a conditional flow (e.g. `if not selected_metrics: st.stop()`) to prevent rendering a specific chart effectively halts the entire script. This destroys any layout or interactive components that exist *below* that section (such as a detailed data table).
*   **Fix**: Never use `st.stop()` simply to hide a component. Instead, wrap the component's rendering logic in an explicit `if` condition (e.g., `if selected_metrics: render_chart()`), allowing the rest of the application layout to continue cascading naturally.

### st.pills Deselection Bug
*   **Observation**: Streamlit `st.pills` with `selection_mode="single"` allows the user to deselect the active option, resulting in the session state value becoming `None`. When using this state to look up dictionary keys (like preset configurations), it triggers a `KeyError` and crashes the application.
*   **Fix**: To resolve this state-loss bug during reruns, always add a fallback check (e.g., `if not selected_preset: selected_preset = "Default"`) in the `on_change` callback before accessing dictionaries, and optionally reset the state variable to the fallback so the UI visually resets.
* When a user selects a single date in `st.date_input` configured for a range, Streamlit temporarily returns a tuple of length 1 before returning length 2 when the second date is selected. To prevent partial state confusion and invalid data requests during these intermediate reruns, explicitly check `isinstance(date_vals, tuple) and len(date_vals) == 1`, render an `st.info` instructional message, and use this condition to set `disabled=True` on dependent form submit buttons.
