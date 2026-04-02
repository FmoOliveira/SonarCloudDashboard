import os
import base64
import logging
import requests
import streamlit as st
import msal

SCOPES = ["User.Read"]
AUTH_COOKIE_KEYS = ["auth_token", "user_info_name", "user_photo", "auth_state"]

def _get_config(key: str) -> str:
    """Helper to safely retrieve configuration from environment or Streamlit secrets."""
    value = os.environ.get(f"AZURE_AD_{key.upper()}")
    if value:
        return value
    try:
        return st.secrets["azure_ad"][key.lower()]
    except (KeyError, FileNotFoundError) as e:
        logging.error(f"Missing Azure AD config '{key}': {e}")
        st.error("Security Configuration Error: Missing identity provider configuration.", icon="🚨")
        st.stop()

@st.cache_resource(show_spinner=False)
def get_msal_client():
    """
    Initializes the MSAL Confidential Client Application as a cached singleton.
    ⚡ Bolt Optimization: This ensures thread safety across Streamlit sessions,
    allows MSAL to maintain its internal token cache, and completely eliminates
    blocking synchronous network calls to Azure AD's OpenID configuration
    endpoint on every unauthenticated page render.
    """
    tenant_id = _get_config("tenant_id")
    client_id = _get_config("client_id")
    client_secret = _get_config("client_secret")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    return msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

def get_auth_url(state=None):
    """Generates the authorization URL for the user to sign in."""
    client = get_msal_client()
    redirect_uri = _get_config("redirect_uri")
    
    kwargs = {"redirect_uri": redirect_uri}
    if state:
        kwargs["state"] = state

    auth_url = client.get_authorization_request_url(
        SCOPES,
        **kwargs
    )
    return auth_url

def acquire_token_by_auth_code(auth_code: str):
    """Exchanges the authorization code for an ID and Access token."""
    client = get_msal_client()
    redirect_uri = _get_config("redirect_uri")
    result = client.acquire_token_by_authorization_code(
        auth_code,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    if "error" in result:
        logging.error(f"MSAL Token Error: {result.get('error_description', result.get('error'))}")
        st.error("Authentication Error: Failed to acquire token.", icon="🚨")
        st.stop()
        
    return result

@st.cache_data(ttl=3600, show_spinner=False)
def get_user_photo(access_token: str) -> str:
    """Fetches the user's profile photo from Microsoft Graph API and returns it as a base64 string."""
    headers = {'Authorization': f'Bearer {access_token}'}
    photo_url = "https://graph.microsoft.com/v1.0/me/photo/$value"
    try:
        response = requests.get(photo_url, headers=headers, timeout=5)
        if response.status_code == 200:
            img_b64 = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/jpeg;base64,{img_b64}"
    except requests.exceptions.RequestException as e:
        logging.warning(f"Failed to fetch user photo due to network error: {e}")
    except Exception as e:
        logging.warning(f"Unexpected error fetching user photo: {e}")
    return ""

def logout(cookies=None):
    """Clears the authentication from cookies."""
    if cookies is not None:
        for key in AUTH_COOKIE_KEYS:
            if key in cookies:
                del cookies[key]
        cookies.save()
            
    st.info("You have been logged out.", icon="👋")
    st.rerun()
