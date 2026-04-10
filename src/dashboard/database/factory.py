import streamlit as st
import logging

logger = logging.getLogger(__name__)
import html
from database.base import StorageInterface
from config import config


def get_storage_client() -> StorageInterface | None:
    """
    Factory method to dynamically instantiate the correct database provider 
    based on the `.streamlit/secrets.toml` configuration.
    
    This enforces the Strategy Pattern, fully decoupling the main application 
    from explicit implementations like Azure or PostgreSQL.
    """
    try:
        provider = config.database_provider
        
        if provider == "azure":
            from database.azure_storage import AzureTableStorage
            
            # Unwrap SecretStr — the plain value is passed only to the constructor,
            # never stored in a variable that persists beyond this scope.
            connection_string = config.azure_storage_connection_string.get_secret_value()
            if not connection_string:
                logger.error("Security Configuration Error: Missing 'connection_string' in [azure_storage] or environment.")
                st.error("Security Configuration Error: A required configuration key is missing.", icon="🚨")
                st.stop()
            return AzureTableStorage(connection_string)
                
        elif provider == "postgres":
            # Future expansion
            # from database.postgres_storage import PostgresStorage
            # return PostgresStorage(...)
            st.error("PostgreSQL provider is not yet implemented.", icon="🚨")
            st.stop()
            
        else:
            safe_provider = html.escape(str(provider))
            st.error(f"Unsupported database provider: '{safe_provider}'", icon="🚨")
            st.stop()

    except RuntimeError as e:
        # RuntimeError is raised by get_msal_client() and _get_fernet() when a
        # required config key is missing. We catch it here (outside any
        # @st.cache_resource boundary) so we can safely call st.error/st.stop().
        logger.critical(f"Configuration Error: {e}")
        st.error(f"System configuration error: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        logger.critical(f"Database Factory Initialization Error: {str(e)}")
        st.error("Database Initialization Error: An internal system error occurred.", icon="🚨")
        st.stop()
        
    return None
