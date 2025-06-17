from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.crud import dpgf as crud
from app.schemas.dpgf import DPGFCreate, DPGFRead
from app.api.deps import get_db
from typing import Any, Dict
import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

router = APIRouter(prefix='/dpgf', tags=['dpgf'])

@router.post('/upload')
async def upload_dpgf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload DPGF Excel file and run import_complete script"""
    # Save uploaded file to a temporary directory
    tmpdir = tempfile.mkdtemp()
    file_path = os.path.join(tmpdir, file.filename)
    with open(file_path, 'wb') as f:
        content = await file.read()
        f.write(content)
    # Determine path to import script
    project_root = Path(__file__).parents[3]
    script_path = project_root / 'scripts' / 'import_complete.py'
    # Get Gemini key from environment
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    # Execute import script
    cmd = [sys.executable, str(script_path), '--file', str(file_path)]
    if gemini_key:
        cmd += ['--gemini-key', gemini_key]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Cleanup temporary files
    shutil.rmtree(tmpdir)
    # Handle errors
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Import script failed: {result.stderr}")
    return {"stdout": result.stdout, "stderr": result.stderr}

@router.post('/', response_model=DPGFRead)
def create_dpgf(dpgf_in: DPGFCreate, db: Session = Depends(get_db)):
    return crud.create_dpgf(db, dpgf_in)

@router.get('/', response_model=list[DPGFRead])
def read_dpgfs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_dpgfs(db, skip, limit)

@router.get('/{dpgf_id}', response_model=DPGFRead)
def read_dpgf(dpgf_id: int, db: Session = Depends(get_db)):
    obj = crud.get_dpgf(db, dpgf_id)
    if not obj:
        raise HTTPException(status_code=404, detail='DPGF not found')
    return obj

@router.delete('/{dpgf_id}', status_code=204)
def delete_dpgf(dpgf_id: int, db: Session = Depends(get_db)):
    crud.delete_dpgf(db, dpgf_id)
    return None

@router.get('/{dpgf_id}/structure', response_model=Dict[str, Any])
def read_dpgf_structure(dpgf_id: int, db: Session = Depends(get_db)):
    """
    Récupérer la structure complète d'un DPGF avec ses lots, sections et éléments d'ouvrage
    organisés de manière hiérarchique, comme dans un fichier Excel.
    """
    structure = crud.get_dpgf_structure(db, dpgf_id)
    if not structure:
        raise HTTPException(status_code=404, detail="DPGF not found")
    return structure
