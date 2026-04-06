import streamlit as st
import os
import secrets
import logging
import base64
import requests
import msal
from cryptography.fernet import Fernet, InvalidToken

SCOPES = ["User.Read"]
AUTH_COOKIE_KEYS = ["auth_token", "user_info_name", "user_photo", "auth_state"]

def _get_config(key: str) -> str:
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
    tenant_id = _get_config("tenant_id")
    client_id = _get_config("client_id")
    client_secret = _get_config("client_secret")
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    return msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

def _get_auth_url(state=None):
    client = get_msal_client()
    kwargs = {"redirect_uri": _get_config("redirect_uri")}
    if state:
        kwargs["state"] = state
    return client.get_authorization_request_url(SCOPES, **kwargs)

def _acquire_token_by_auth_code(auth_code: str):
    client = get_msal_client()
    result = client.acquire_token_by_authorization_code(
        auth_code,
        scopes=SCOPES,
        redirect_uri=_get_config("redirect_uri")
    )
    if "error" in result:
        logging.error(f"MSAL Token Error: {result.get('error_description', result.get('error'))}")
        st.error("Authentication Error: Failed to acquire token.", icon="🚨")
        st.stop()
    return result

@st.cache_data(ttl=3600, show_spinner=False)
def _get_user_photo(access_token: str) -> str:
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get("https://graph.microsoft.com/v1.0/me/photo/$value", headers=headers, timeout=5)
        if response.status_code == 200:
            img_b64 = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/jpeg;base64,{img_b64}"
    except Exception as e:
        logging.warning(f"Failed to fetch user photo: {e}")
    return ""

def _get_fernet():
    try:
        if "cookie_encryption_key" in st.secrets:
            key = st.secrets["cookie_encryption_key"]
            return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        pass
    fallback_dev_key = b'_B-G0rLQ89Q4uXfJpI3E4L2XQ78X4L9B0rLQ89Q4uXf=' 
    logging.warning("No `cookie_encryption_key` set in .streamlit/secrets.toml! Using insecure DEV fallback key.")
    return Fernet(fallback_dev_key)

def encrypt_val(val: str) -> str:
    if not val: return val
    try:
        return _get_fernet().encrypt(val.encode()).decode()
    except Exception:
        return val

def decrypt_val(val: str) -> str:
    if not val: return val
    try:
        return _get_fernet().decrypt(val.encode()).decode()
    except InvalidToken:
        return val
    except Exception:
        return val

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
    auth_token = get_auth_token(cookies)
    
    if not auth_token and "code" in st.query_params:
        auth_code = st.query_params["code"]
        returned_state = st.query_params.get("state")
        st.query_params.clear()

        expected_state = cookies.get("auth_state")
        needs_save = False
        if "auth_state" in cookies:
            del cookies["auth_state"]
            needs_save = True

        if not expected_state or returned_state != expected_state:
            if needs_save:
                cookies.save()
            logging.warning("Authentication state mismatch (potential CSRF or navigation issue). Continuing exchange.")

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
                    if needs_save: 
                        cookies.save()
                    st.rerun()
                else:
                    logging.error(f"Authentication failed: {error_desc}")
                    if needs_save: 
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
    for key in AUTH_COOKIE_KEYS:
        if key in cookies:
            del cookies[key]
    cookies.save()
    st.info("You have been logged out.", icon="👋")
    st.rerun()
