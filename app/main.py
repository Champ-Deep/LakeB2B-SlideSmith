"""
FastAPI application entry point.
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from app.config import ensure_dirs
from app.routes.upload import router as upload_router
from app.routes.status import router as status_router
from app.routes.single import router as single_router

# Create app
app = FastAPI(
    title="LakeB2B Pitch Deck Creator",
    description="Batch pitch deck generation from Excel prospect lists",
    version="1.0.0",
)

# CORS (allow all for local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Include routers
app.include_router(upload_router)
app.include_router(status_router)
app.include_router(single_router)


@app.on_event("startup")
async def startup():
    """Create required directories on startup."""
    ensure_dirs()


@app.get("/")
async def root(request: Request):
    """Serve the upload UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "LakeB2B Pitch Deck Creator"}
