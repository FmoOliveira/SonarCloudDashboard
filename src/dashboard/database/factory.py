import streamlit as st
import logging
import html
from database.base import StorageInterface

def get_storage_client() -> StorageInterface | None:
    """
    Factory method to dynamically instantiate the correct database provider 
    based on the `.streamlit/secrets.toml` configuration.
    
    This enforces the Strategy Pattern, fully decoupling the main application 
    from explicit implementations like Azure or PostgreSQL.
    """
    try:
        import os
        # Default to azure if no explicit provider is set
        database_config = st.secrets.get("database", {}) if "DATABASE_PROVIDER" not in os.environ else {}
        provider = os.environ.get("DATABASE_PROVIDER") or database_config.get("provider", "azure")
        
        if provider == "azure":
            from database.azure_storage import AzureTableStorage
            
            # Fail-fast extraction for provider-specific secrets
            try:
                conn_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or st.secrets["azure_storage"]["connection_string"]
                return AzureTableStorage(conn_string)
            except KeyError:
                logging.error("Security Configuration Error: Missing 'connection_string' in [azure_storage] or environment.")
                st.error("Security Configuration Error: A required configuration key is missing.", icon="🚨")
                st.stop()
                
        elif provider == "postgres":
            # Future expansion
            # from database.postgres_storage import PostgresStorage
            # return PostgresStorage(...)
            st.error("PostgreSQL provider is not yet implemented.", icon="🚨")
            st.stop()
            
        else:
            safe_provider = html.escape(provider)
            st.error(f"Unsupported database provider: '{safe_provider}'", icon="🚨")
            st.stop()
            
    except FileNotFoundError:
        logging.error("Security Configuration Error: `secrets.toml` is missing.")
        st.error("Security Configuration Error: A required configuration file is missing.", icon="🚨")
        st.stop()
    except Exception as e:
        logging.critical(f"Database Factory Initialization Error: {str(e)}")
        st.error("Database Initialization Error: An internal system error occurred.", icon="🚨")
        st.stop()
        
    return None
