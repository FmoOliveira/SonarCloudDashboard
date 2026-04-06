import streamlit as st
import secrets
import logging
import base64
import msal
import asyncio
import aiohttp
from cryptography.fernet import Fernet, InvalidToken
from config import config

SCOPES = ["User.Read"]

# All session-persistent cookie keys (restored on every page load)
AUTH_COOKIE_KEYS = ["auth_token", "user_info_name", "user_photo", "auth_state"]

# Fast in-memory cache key — populated from cookie on first run per session
_SESSION_TOKEN_CACHE = "_auth_token_cache"


@st.cache_resource(show_spinner=False)
def get_msal_client() -> msal.ConfidentialClientApplication:
    """
    Returns a cached MSAL ConfidentialClientApplication.
    Raises RuntimeError on misconfiguration (do NOT call st.stop() inside
    a @st.cache_resource function — it prevents the resource from ever caching).
    """
    if not config.tenant_id or not config.client_id:
        raise RuntimeError(
            "Missing Azure AD (Entra) configuration: AZURE_AD_TENANT_ID and AZURE_AD_CLIENT_ID are required."
        )
    authority = f"https://login.microsoftonline.com/{config.tenant_id}"
    return msal.ConfidentialClientApplication(
        config.client_id,
        authority=authority,
        client_credential=config.client_secret
    )


@st.cache_resource(show_spinner=False)
def _get_fernet() -> Fernet:
    """
    Returns a cached Fernet instance — created once per server process,
    not once per encrypt/decrypt call.
    Raises RuntimeError on misconfiguration (avoids st.stop() inside cache).
    """
    key = config.cookie_encryption_key.get_secret_value()
    if not key:
        raise RuntimeError(
            "Missing cookie encryption key: AZURE_AD_COOKIE_ENCRYPTION_KEY is required."
        )
    return Fernet(key.encode())


def _get_auth_url(state: str | None = None) -> str:
    try:
        client = get_msal_client()
    except RuntimeError as e:
        logging.critical(f"MSAL configuration error: {e}")
        st.error(f"Security Configuration Error: {e}", icon="🚨")
        st.stop()
    kwargs = {"redirect_uri": config.redirect_uri}
    if state:
        kwargs["state"] = state
    return client.get_authorization_request_url(SCOPES, **kwargs)


def _acquire_token_by_auth_code(auth_code: str) -> dict:
    try:
        client = get_msal_client()
    except RuntimeError as e:
        logging.critical(f"MSAL configuration error: {e}")
        st.error(f"Security Configuration Error: {e}", icon="🚨")
        st.stop()
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
            async with session.get(
                "https://graph.microsoft.com/v1.0/me/photo/$value",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    img_data = await response.read()
                    img_b64 = base64.b64encode(img_data).decode('utf-8')
                    return f"data:image/jpeg;base64,{img_b64}"
    except Exception as e:
        logging.warning(f"Failed to fetch user photo: {e}")
    return ""


def _get_user_photo(access_token: str) -> str:
    try:
        return asyncio.run(_get_user_photo_async(access_token))
    except Exception:
        return ""


def encrypt_val(val: str) -> str:
    if not val:
        return val
    try:
        return _get_fernet().encrypt(val.encode()).decode()
    except RuntimeError as e:
        logging.critical(f"Fernet configuration error during encryption: {e}")
        st.error(f"System configuration error: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        logging.error(f"Encryption failed unexpectedly: {e}")
        return ""


def decrypt_val(val: str, *, invalidate_on_failure: bool = False) -> str:
    """
    Decrypts a Fernet-encrypted cookie value.
    Detects tampered ciphertext via InvalidToken and logs a security warning.
    If invalidate_on_failure=True, flags the session for teardown.
    """
    if not val:
        return val
    try:
        return _get_fernet().decrypt(val.encode()).decode()
    except InvalidToken:
        logging.warning("SECURITY: Fernet decryption failed — cookie may have been tampered with.")
        if invalidate_on_failure:
            st.session_state["pending_logout"] = True
        return ""
    except Exception as e:
        logging.error(f"Unexpected decryption error: {e}")
        return ""


def _get_token_from_cookie(cookies) -> str:
    """
    Restores the auth token from the encrypted cookie into session_state.
    Called when session_state is empty (e.g. page refresh / session reconnect).
    Returns the plain-text token or "" if none found.
    """
    raw = cookies.get("auth_token")
    if not raw:
        return ""
    token = decrypt_val(raw, invalidate_on_failure=True)
    if token:
        # Warm the in-memory cache for subsequent calls this session
        st.session_state[_SESSION_TOKEN_CACHE] = token
    return token


def get_auth_token(cookies) -> str:
    """
    Returns the auth token using a two-level lookup:
    1. In-memory session_state (fast — avoids decryption on every render)
    2. Encrypted cookie (persistence across page refreshes / WebSocket reconnects)
    """
    cached = st.session_state.get(_SESSION_TOKEN_CACHE, "")
    if cached:
        return cached
    return _get_token_from_cookie(cookies)


def get_user_info(cookies) -> tuple[str, str]:
    name = cookies.get("user_info_name")
    photo = cookies.get("user_photo")
    # Tampered cookies trigger session invalidation
    decrypted_name = decrypt_val(name, invalidate_on_failure=True) if name else None
    decrypted_photo = decrypt_val(photo, invalidate_on_failure=True) if photo else None
    return decrypted_name, decrypted_photo


def _single_save(cookies) -> None:
    """
    Central save gate — ensures cookies.save() is called at most ONCE per 
    Streamlit script run. CookieManager registers its 'save' action as a 
    Streamlit component with a fixed key; calling save() twice in the same  
    run causes StreamlitDuplicateElementKey.
    
    Callers should mutate cookies freely, then call this exactly once before
    returning or calling st.rerun().
    """
    if not st.session_state.get("_cookies_saved_this_run"):
        st.session_state["_cookies_saved_this_run"] = True
        cookies.save()


def handle_auth(cookies) -> str:
    # Reset the per-run save gate at the start of every execution cycle
    st.session_state["_cookies_saved_this_run"] = False

    # 1. Digest pending logout directive
    if st.session_state.get("pending_logout"):
        for key in AUTH_COOKIE_KEYS:
            if key in cookies:
                cookies[key] = None
        _single_save(cookies)
        st.session_state.pop(_SESSION_TOKEN_CACHE, None)
        st.session_state["pending_logout"] = False
        st.rerun()

    # 2. Fast path — return cached in-memory token (avoids cookie decryption)
    auth_token = get_auth_token(cookies)
    if auth_token:
        return auth_token

    # 3. Process OAuth callback if code is present in query params
    if "code" in st.query_params:
        auth_code = st.query_params["code"]
        returned_state = st.query_params.get("state")
        st.query_params.clear()

        # Batch: read CSRF state AND mark it for deletion before any save() call
        expected_state = cookies.get("auth_state")
        cookies["auth_state"] = None  # queued for deletion

        if not expected_state or returned_state != expected_state:
            _single_save(cookies)  # save the auth_state deletion
            logging.error(f"CSRF thwarted: Expected [{expected_state}] vs Returned [{returned_state}]")
            st.error("Authentication invalid: State mismatch. Clearing session automatically...", icon="🔐")
            return ""

        with st.spinner("Authenticating..."):
            token_result = _acquire_token_by_auth_code(auth_code)

            if "access_token" in token_result:
                auth_token = token_result["access_token"]

                # Store in session_state for fast in-memory access this session
                st.session_state[_SESSION_TOKEN_CACHE] = auth_token
                # Store encrypted in cookie so it survives page refresh
                cookies["auth_token"] = encrypt_val(auth_token)

                user_info = token_result.get("id_token_claims", {})
                name = user_info.get("name", "User")
                cookies["user_info_name"] = encrypt_val(name)

                photo_b64 = _get_user_photo(auth_token)
                if photo_b64:
                    cookies["user_photo"] = encrypt_val(photo_b64)

                # ✅ Single batched save — covers auth_state removal + all session cookies
                _single_save(cookies)
            else:
                error_desc = token_result.get("error_description", "Unknown error")
                if "AADSTS54005" in error_desc:
                    _single_save(cookies)
                    st.rerun()
                else:
                    logging.error(f"Authentication failed: {error_desc}")
                    _single_save(cookies)
                    st.error("Authentication failed: An internal error occurred.", icon="🚨")
                    st.stop()

    return auth_token


def get_login_url(cookies) -> str:
    """
    Generates an OAuth login URL.
    Persists the CSRF state token in a cookie — guarded by _single_save to 
    ensure only one save() happens per Streamlit script run.
    """
    current_state = cookies.get("auth_state")
    if not current_state:
        state_plain = secrets.token_urlsafe(32)
        cookies["auth_state"] = state_plain
        _single_save(cookies)
    else:
        state_plain = current_state

    return _get_auth_url(state=state_plain)


def do_logout(cookies) -> None:
    """
    Initiates a clean logout: clears all encrypted browser cookies and 
    marks the session for teardown on the next rerun cycle.
    """
    if cookies is None:
        raise ValueError("do_logout requires a valid cookies context — received None.")

    for key in AUTH_COOKIE_KEYS:
        if key in cookies:
            cookies[key] = None
    _single_save(cookies)

    st.session_state.pop(_SESSION_TOKEN_CACHE, None)
    st.session_state["pending_logout"] = True
    st.info("Logging out, clearing session...", icon="👋")
    st.rerun()
