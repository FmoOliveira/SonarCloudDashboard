# Palette's Journal

Critical UX learnings and observations only.

*   A reusable UI pattern for handling table exports: `st.download_button` can utilize `use_container_width=True` to match the width of `st.dataframe(..., use_container_width=True)`, which prevents visual layout jumps when rendering tabular data alongside export actions. Adding `icon` and `help` tooltips further clarifies the context and maintains the UI consistency.
