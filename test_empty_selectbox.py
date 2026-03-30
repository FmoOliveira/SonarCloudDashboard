import streamlit as st
selected = st.selectbox("Project", [])
if not selected:
    st.info("No project selected")
