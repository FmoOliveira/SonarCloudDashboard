import streamlit as st
import msal
import logging
import requests

import os

@st.cache_resource(show_spinner=False)
def get_msal_client():
    """
    Initializes the MSAL Confidential Client Application as a cached singleton.
    ⚡ Bolt Optimization: This ensures thread safety across Streamlit sessions,
    allows MSAL to maintain its internal token cache, and completely eliminates
    blocking synchronous network calls to Azure AD's OpenID configuration
    endpoint on every unauthenticated page render.
    """
    try:
        tenant_id = os.environ.get("AZURE_AD_TENANT_ID") or st.secrets["azure_ad"]["tenant_id"]
        client_id = os.environ.get("AZURE_AD_CLIENT_ID") or st.secrets["azure_ad"]["client_id"]
        client_secret = os.environ.get("AZURE_AD_CLIENT_SECRET") or st.secrets["azure_ad"]["client_secret"]
    except KeyError as e:
        logging.error(f"Missing Azure AD configuration in `.streamlit/secrets.toml`: {e}")
        st.error("Security Configuration Error: Missing identity provider configuration.", icon="🚨")
        st.stop()

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    return msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

def get_auth_url(state=None):
    """Generates the authorization URL for the user to sign in."""
    client = get_msal_client()
    try:
        redirect_uri = os.environ.get("AZURE_AD_REDIRECT_URI") or st.secrets["azure_ad"]["redirect_uri"]
    except KeyError:
        logging.error("Missing `redirect_uri` in environment or `.streamlit/secrets.toml`.")
        st.error("Security Configuration Error: Missing identity provider configuration.", icon="🚨")
        st.stop()
        
    # We request the basic profile scopes
    scopes = ["User.Read"]
    
    kwargs = {"redirect_uri": redirect_uri}
    if state:
        kwargs["state"] = state

    auth_url = client.get_authorization_request_url(
        scopes,
        **kwargs
    )
    return auth_url

def acquire_token_by_auth_code(auth_code: str):
    """Exchanges the authorization code for an ID and Access token."""
    client = get_msal_client()
    try:
        redirect_uri = os.environ.get("AZURE_AD_REDIRECT_URI") or st.secrets["azure_ad"]["redirect_uri"]
    except KeyError:
        logging.error("Missing `redirect_uri` in environment or `.streamlit/secrets.toml`.")
        st.error("Security Configuration Error: Missing identity provider configuration.", icon="🚨")
        st.stop()

    scopes = ["User.Read"]
    result = client.acquire_token_by_authorization_code(
        auth_code,
        scopes=scopes,
        redirect_uri=redirect_uri
    )
    return result

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

def logout(cookies=None):
    """Clears the authentication from cookies."""
    if cookies is not None:
        for key in ["auth_token", "user_info_name", "user_photo", "auth_state"]:
            if key in cookies:
                del cookies[key]
        cookies.save()
            
    st.info("You have been logged out.", icon="👋")
    st.rerun()
