from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.api.v1 import client, dpgf, lot, section, element_ouvrage, dpgf_analysis

app = FastAPI(title='DPGF API')

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Monter les fichiers statiques (si nécessaire)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(client.router, prefix='/api/v1')
app.include_router(dpgf.router, prefix='/api/v1')
app.include_router(lot.router, prefix='/api/v1')
app.include_router(section.router, prefix='/api/v1')
app.include_router(element_ouvrage.router, prefix='/api/v1')
app.include_router(dpgf_analysis.router, prefix='/api/v1')
