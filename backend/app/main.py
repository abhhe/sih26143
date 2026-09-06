# pyrefly: ignore [missing-import]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.api.v1.endpoints_sar import router as sar_router
from backend.app.api.v1.endpoints_ais import router as ais_router
from backend.app.api.v1.endpoints_attribution import router as attribution_router
from backend.app.api.v1.endpoints_validation import router as validation_router

app = FastAPI(
    title="Oil Spill Source Attribution API",
    description="Scientific Backend for SIH 2026 Problem Statement 26143: Satellite SAR Detection & AIS Correlation",
    version="1.0.0",
)

# Configure CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(sar_router)
app.include_router(ais_router)
app.include_router(attribution_router)
app.include_router(validation_router)




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
