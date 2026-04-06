import os
import streamlit as st
import logging
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_AD_", extra="ignore")

    # Authentication (Azure AD)
    tenant_id: str = Field(default="")
    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    redirect_uri: str = Field(default="")
    cookie_encryption_key: str = Field(default="")
    
    # Storage
    database_provider: str = Field(default="azure", alias="DATABASE_PROVIDER")
    azure_storage_connection_string: str = Field(default="", alias="AZURE_STORAGE_CONNECTION_STRING")
    
    # SonarCloud
    sonarcloud_api_token: str = Field(default="", alias="SONARCLOUD_API_TOKEN")
    sonarcloud_organization_key: str = Field(default="", alias="SONARCLOUD_ORGANIZATION_KEY")
    
    @classmethod
    def load(cls) -> "AppConfig":
        """Loads secrets from Streamlit and cascades to expected environment variables prior to Pydantic parsing."""
        try:
            if "azure_ad" in st.secrets:
                for k, v in st.secrets["azure_ad"].items():
                    env_key = f"AZURE_AD_{k.upper()}"
                    if env_key not in os.environ:
                        os.environ[env_key] = str(v)
            
            if "database" in st.secrets:
                if "DATABASE_PROVIDER" not in os.environ:
                    os.environ["DATABASE_PROVIDER"] = str(st.secrets["database"].get("provider", "azure"))
            
            if "azure_storage" in st.secrets:
                if "AZURE_STORAGE_CONNECTION_STRING" not in os.environ:
                    os.environ["AZURE_STORAGE_CONNECTION_STRING"] = str(st.secrets["azure_storage"].get("connection_string", ""))
            
            if "sonarcloud" in st.secrets:
                for k, v in st.secrets["sonarcloud"].items():
                    env_key = f"SONARCLOUD_{k.upper()}"
                    if env_key not in os.environ:
                        os.environ[env_key] = str(v)
                        
            if "cookie_encryption_key" in st.secrets and "AZURE_AD_COOKIE_ENCRYPTION_KEY" not in os.environ:
                os.environ["AZURE_AD_COOKIE_ENCRYPTION_KEY"] = str(st.secrets["cookie_encryption_key"])
                
        except (FileNotFoundError, Exception) as e:
            logging.debug(f"Streamlit secrets extraction skipped or partially failed: {e}")
            
        return cls()

config = AppConfig.load()
