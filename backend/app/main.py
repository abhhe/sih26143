# pyrefly: ignore [missing-import]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.api.v1.endpoints_sar import router as sar_router
from backend.app.api.v1.endpoints_ais import router as ais_router
from backend.app.api.v1.endpoints_attribution import router as attribution_router
from backend.app.api.v1.endpoints_validation import router as validation_router
from backend.app.api.v1.endpoints_metocean import router as metocean_router
from backend.app.api.v1.endpoints_drift import router as drift_router

app = FastAPI(
    title="Oil Spill Source Attribution API",
    description="Scientific Backend for SIH 2026 Problem Statement 26143: Satellite SAR Detection & AIS Correlation",
    version="1.0.0",
)

# Configure CORS for local React development and configured domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(sar_router)
app.include_router(ais_router)
app.include_router(attribution_router)
app.include_router(validation_router)
app.include_router(metocean_router)
app.include_router(drift_router)


@app.get("/health", tags=["System"])
@app.get("/api/health", tags=["System"])
def health_check():
    return {
        "status": "online",
        "mode": settings.app_mode,
        "service": "SIH-PS26143-Attribution-Engine",
    }


if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
