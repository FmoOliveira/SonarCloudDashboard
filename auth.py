import streamlit as st
import msal
import logging

def get_msal_client():
    """Initializes the MSAL Confidential Client Application using st.secrets."""
    try:
        tenant_id = st.secrets["azure_ad"]["tenant_id"]
        client_id = st.secrets["azure_ad"]["client_id"]
        client_secret = st.secrets["azure_ad"]["client_secret"]
    except KeyError as e:
        st.error(f"Missing Azure AD configuration in `.streamlit/secrets.toml`: {e}", icon="🚨")
        st.stop()

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    return msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

def get_auth_url():
    """Generates the authorization URL for the user to sign in."""
    client = get_msal_client()
    try:
        redirect_uri = st.secrets["azure_ad"]["redirect_uri"]
    except KeyError:
        st.error("Missing `redirect_uri` in `.streamlit/secrets.toml` under `azure_ad`.", icon="🚨")
        st.stop()
        
    # We request the basic profile scopes
    scopes = ["User.Read"]
    
    auth_url = client.get_authorization_request_url(
        scopes,
        redirect_uri=redirect_uri
    )
    return auth_url

def acquire_token_by_auth_code(auth_code: str):
    """Exchanges the authorization code for an ID and Access token."""
    client = get_msal_client()
    try:
        redirect_uri = st.secrets["azure_ad"]["redirect_uri"]
    except KeyError:
        st.error("Missing `redirect_uri` in `.streamlit/secrets.toml` under `azure_ad`.", icon="🚨")
        st.stop()

    scopes = ["User.Read"]
    result = client.acquire_token_by_authorization_code(
        auth_code,
        scopes=scopes,
        redirect_uri=redirect_uri
    )
    return result

import requests

def get_user_photo(access_token: str) -> str:
    """Fetches the user's profile photo from Microsoft Graph API and returns it as a base64 string."""
    headers = {'Authorization': f'Bearer {access_token}'}
    photo_url = "https://graph.microsoft.com/v1.0/me/photo/$value"
    try:
        response = requests.get(photo_url, headers=headers, timeout=5)
        if response.status_code == 200:
            import base64
            img_b64 = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/jpeg;base64,{img_b64}"
    except Exception as e:
        logging.warning(f"Failed to fetch user photo: {e}")
    return ""

def logout():
    """Clears the authentication from the session state and browser cookies."""
    for key in ["auth_token", "user_info", "user_photo"]:
        if key in st.session_state:
            del st.session_state[key]
            
    import extra_streamlit_components as stx
    cookie_manager = stx.CookieManager()
    cookie_manager.delete("auth_token")
    cookie_manager.delete("user_info")
    cookie_manager.delete("user_photo")
    
    st.info("You have been logged out.")
    st.rerun()
