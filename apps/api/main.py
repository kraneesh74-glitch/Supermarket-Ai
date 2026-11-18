"""Main FastAPI Gateway Application (SuperMart AI Enquiry Agent)."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.routes.whatsapp import router as whatsapp_router
from apps.api.routes.chat import router as chat_router
from apps.api.routes.reports import router as reports_router

app = FastAPI(
    title="SuperMart AI Enquiry Agent Gateway",
    description="Conversational AI Gateway for Supermarket Shoppers across WhatsApp and Web Chat.",
    version="1.0.0",
)

# CORS configuration for web widget embedding
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
app.include_router(whatsapp_router)
app.include_router(chat_router)
app.include_router(reports_router)

# Mount static files for web chat widget
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "SuperMart AI Enquiry Agent",
        "version": "1.0.0",
    }


@app.get("/", response_class=HTMLResponse)
async def serve_widget_demo():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return "<h1>SuperMart AI Enquiry Agent Gateway is Running</h1>"

