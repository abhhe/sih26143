import os
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Load .env if it exists
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    # Also attempt loading from .env.example as fallback defaults in demo mode
    example_path = BASE_DIR / ".env.example"
    if example_path.exists():
        load_dotenv(example_path)


class Settings(BaseModel):
    """
    Centralized configuration management for SIH PS 26143.
    Zero hardcoded URLs or credentials.
    Supports dual execution modes: DEMO and REAL.
    """
    # Execution Mode: "DEMO" uses local sample files; "REAL" queries configured external APIs
    app_mode: Literal["DEMO", "REAL"] = Field(
        default_factory=lambda: os.getenv("APP_MODE", "DEMO").upper()  # type: ignore
    )

    # Local storage paths
    data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
    )
    sar_data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("SAR_DATA_DIR", str(BASE_DIR / "data" / "sample_sar")))
    )
    csiro_data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("CSIRO_DATA_DIR", str(BASE_DIR / "data" / "sample_sar" / "csiro")))
    )
    metocean_data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("METOCEAN_DATA_DIR", str(BASE_DIR / "data" / "sample_metocean")))
    )
    ais_data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("AIS_DATA_DIR", str(BASE_DIR / "data" / "sample_ais")))
    )

    # Copernicus Data Space Ecosystem (CDSE) STAC / OData Settings
    cdse_base_url: str = Field(
        default_factory=lambda: os.getenv("CDSE_BASE_URL", "https://catalogue.dataspace.copernicus.eu/odata/v1")
    )
    cdse_token_url: str = Field(
        default_factory=lambda: os.getenv("CDSE_TOKEN_URL", "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token")
    )
    cdse_username: Optional[str] = Field(default_factory=lambda: os.getenv("CDSE_USERNAME"))
    cdse_password: Optional[str] = Field(default_factory=lambda: os.getenv("CDSE_PASSWORD"))
    cdse_client_id: str = Field(default_factory=lambda: os.getenv("CDSE_CLIENT_ID", "cdse-public"))

    # ECMWF Copernicus Climate Data Store (CDS) ERA5 Settings
    cds_api_url: str = Field(
        default_factory=lambda: os.getenv("CDS_API_URL", "https://cds.climate.copernicus.eu/api")
    )
    cds_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("CDS_API_KEY"))

    # Copernicus Marine Service (CMEMS) Settings
    copernicus_marine_username: Optional[str] = Field(
        default_factory=lambda: os.getenv("COPERNICUS_MARINE_USERNAME")
    )
    copernicus_marine_password: Optional[str] = Field(
        default_factory=lambda: os.getenv("COPERNICUS_MARINE_PASSWORD")
    )

    # AIS Settings (Global Fishing Watch or Spire API)
    gfw_api_url: str = Field(
        default_factory=lambda: os.getenv("GFW_API_URL", "https://gateway.globalfishingwatch.org/v3")
    )
    gfw_api_token: Optional[str] = Field(default_factory=lambda: os.getenv("GFW_API_TOKEN"))

    # Scientific thresholds
    default_evidence_threshold: float = Field(
        default_factory=lambda: float(os.getenv("DEFAULT_EVIDENCE_THRESHOLD", "50.0"))
    )

    def is_demo_mode(self) -> bool:
        return self.app_mode == "DEMO"

    def ensure_directories(self) -> None:
        """Ensure that data directories exist on the filesystem."""
        for d in [self.data_dir, self.sar_data_dir, self.csiro_data_dir, self.metocean_data_dir, self.ais_data_dir]:
            d.mkdir(parents=True, exist_ok=True)


# Global settings singleton
settings = Settings()
