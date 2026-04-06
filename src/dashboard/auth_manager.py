import streamlit as st
import secrets
import logging
import base64
import requests
import msal
import asyncio
import aiohttp
from cryptography.fernet import Fernet, InvalidToken
from config import config

SCOPES = ["User.Read"]
AUTH_COOKIE_KEYS = ["auth_token", "user_info_name", "user_photo", "auth_state"]

@st.cache_resource(show_spinner=False)
def get_msal_client():
    if not config.tenant_id or not config.client_id:
        st.error("Security Configuration Error: Missing Azure AD (Entra) identity provider configuration.", icon="🚨")
        st.stop()
        
    authority = f"https://login.microsoftonline.com/{config.tenant_id}"
    return msal.ConfidentialClientApplication(
        config.client_id,
        authority=authority,
        client_credential=config.client_secret
    )

def _get_auth_url(state=None):
    client = get_msal_client()
    kwargs = {"redirect_uri": config.redirect_uri}
    if state:
        kwargs["state"] = state
    return client.get_authorization_request_url(SCOPES, **kwargs)

def _acquire_token_by_auth_code(auth_code: str):
    client = get_msal_client()
    result = client.acquire_token_by_authorization_code(
        auth_code,
        scopes=SCOPES,
        redirect_uri=config.redirect_uri
    )
    if "error" in result:
        logging.error(f"MSAL Token Error: {result.get('error_description', result.get('error'))}")
        st.error("Authentication Error: Failed to acquire token.", icon="🚨")
        st.stop()
    return result

async def _get_user_photo_async(access_token: str) -> str:
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get("https://graph.microsoft.com/v1.0/me/photo/$value", timeout=5) as response:
                if response.status == 200:
                    img_data = await response.read()
                    img_b64 = base64.b64encode(img_data).decode('utf-8')
                    return f"data:image/jpeg;base64,{img_b64}"
    except Exception as e:
        logging.warning(f"Failed to fetch user photo asynchronously: {e}")
    return ""

def _get_user_photo(access_token: str) -> str:
    try:
        return asyncio.run(_get_user_photo_async(access_token))
    except Exception:
        return ""

def _get_fernet():
    if not config.cookie_encryption_key:
        logging.critical("CRITICAL VULNERABILITY: Cookie encryption key is missing!")
        st.error("System configuration error: secure encryption key is not set. Halting for security purposes.", icon="🚨")
        st.stop()
    return Fernet(config.cookie_encryption_key.encode())

def encrypt_val(val: str) -> str:
    if not val: return val
    try:
        return _get_fernet().encrypt(val.encode()).decode()
    except Exception:
        return ""

def decrypt_val(val: str) -> str:
    if not val: return val
    try:
        return _get_fernet().decrypt(val.encode()).decode()
    except Exception:
        # Security critical: Never return the original raw value on failure
        return ""

def get_auth_token(cookies) -> str:
    token = cookies.get("auth_token")
    if token:
        return decrypt_val(token)
    return ""

def get_user_info(cookies) -> tuple[str, str]:
    name = cookies.get("user_info_name")
    photo = cookies.get("user_photo")
    return decrypt_val(name) if name else None, decrypt_val(photo) if photo else None

def handle_auth(cookies) -> str:
    # Safely digest pending complete logout directives at the absolute start of a run
    if st.session_state.get("pending_logout"):
        for key in AUTH_COOKIE_KEYS:
            if key in cookies:
                del cookies[key]
        st.session_state["pending_logout"] = False

    auth_token = get_auth_token(cookies)
    
    if not auth_token and "code" in st.query_params:
        auth_code = st.query_params["code"]
        returned_state = st.query_params.get("state")
        st.query_params.clear()

        expected_state = cookies.get("auth_state")
        if "auth_state" in cookies:
            del cookies["auth_state"]

        if not expected_state or returned_state != expected_state:
            # We defer cookie saving to get_login_url to prevent StreamlitDuplicateElementKey
            # crashes since returning "" enforces an automatic login page redraw.
            logging.error("CSRF attack thwarted: authentication state mismatch!")
            st.error("Authentication invalid: State mismatch (did you refresh an old link?). Clearing session automatically...", icon="🔐")
            # If the user refreshed the callback URL, just ignore the stale code 
            # and let the app render the default login screen naturally.
            return ""

        with st.spinner("Authenticating..."):
            token_result = _acquire_token_by_auth_code(auth_code)

            if "access_token" in token_result:
                auth_token = token_result["access_token"]
                cookies["auth_token"] = encrypt_val(auth_token)
                
                user_info = token_result.get("id_token_claims", {})
                name = user_info.get("name", "User")
                cookies["user_info_name"] = encrypt_val(name)
                
                photo_b64 = _get_user_photo(auth_token)
                if photo_b64:
                    cookies["user_photo"] = encrypt_val(photo_b64)
                
                cookies.save()
            else:
                error_desc = token_result.get("error_description", "Unknown error")
                if "AADSTS54005" in error_desc:
                    cookies.save()
                    st.rerun()
                else:
                    logging.error(f"Authentication failed: {error_desc}")
                    cookies.save()
                    st.error("Authentication failed: An internal error occurred.", icon="🚨")
                    st.stop()
                    
    return auth_token

def get_login_url(cookies) -> str:
    state_plain = secrets.token_urlsafe(32)
    cookies["auth_state"] = state_plain
    cookies.save()
    return _get_auth_url(state=state_plain)

def do_logout(cookies):
    # Offload the structural cleanup and component re-render to the next cycle explicitly.
    st.session_state["pending_logout"] = True
    st.info("You have been logged out.", icon="👋")
    st.rerun()
