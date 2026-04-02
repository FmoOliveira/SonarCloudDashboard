import streamlit as st
import secrets
from cryptography.fernet import Fernet, InvalidToken
import logging
from auth import get_auth_url, acquire_token_by_auth_code, get_user_photo, logout

def _get_fernet():
    try:
        if "cookie_encryption_key" in st.secrets:
            key = st.secrets["cookie_encryption_key"]
            return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        pass
    # Fallback to a consistent DEV key if no secret is configured.
    # Without this, refreshing the browser wipes st.session_state and makes the cookies undecryptable.
    fallback_dev_key = b'_B-G0rLQ89Q4uXfJpI3E4L2XQ78X4L9B0rLQ89Q4uXf=' # Dummy dev key
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
            token_result = acquire_token_by_auth_code(auth_code)

            if "access_token" in token_result:
                auth_token = token_result["access_token"]
                cookies["auth_token"] = encrypt_val(auth_token)
                
                user_info = token_result.get("id_token_claims", {})
                name = user_info.get("name", "User")
                cookies["user_info_name"] = encrypt_val(name)
                
                photo_b64 = get_user_photo(auth_token)
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
    return get_auth_url(state=state_plain)

def do_logout(cookies):
    # Pass cookies down to original auth.logout which clears the keys
    logout(cookies)
