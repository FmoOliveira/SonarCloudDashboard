import streamlit as st
import logging
from database.base import StorageInterface

def get_storage_client() -> StorageInterface | None:
    """
    Factory method to dynamically instantiate the correct database provider 
    based on the `.streamlit/secrets.toml` configuration.
    
    This enforces the Strategy Pattern, fully decoupling the main application 
    from explicit implementations like Azure or PostgreSQL.
    """
    try:
        # Default to azure if no explicit provider is set but database section exists
        database_config = st.secrets.get("database", {})
        provider = database_config.get("provider", "azure")
        
        if provider == "azure":
            from database.azure_storage import AzureTableStorage
            
            # Fail-fast extraction for provider-specific secrets
            try:
                conn_string = st.secrets["azure_storage"]["connection_string"]
                return AzureTableStorage(conn_string)
            except KeyError:
                st.error("Security Configuration Error: Missing 'connection_string' in [azure_storage].", icon="🚨")
                st.stop()
                
        elif provider == "postgres":
            # Future expansion
            # from database.postgres_storage import PostgresStorage
            # return PostgresStorage(...)
            st.error("PostgreSQL provider is not yet implemented.")
            st.stop()
            
        else:
            st.error(f"Unsupported database provider: '{provider}'", icon="🚨")
            st.stop()
            
    except FileNotFoundError:
        st.error("Security Configuration Error: `secrets.toml` is missing.", icon="🚨")
        st.stop()
    except Exception as e:
        logging.critical(f"Database Factory Initialization Error: {str(e)}")
        st.error(f"Database Initialization Error: {str(e)}", icon="🚨")
        st.stop()
        
    return None
