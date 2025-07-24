from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.crud import dpgf as crud
from app.schemas.dpgf import DPGFCreate, DPGFRead
from app.api.deps import get_db
from typing import Any, Dict
import os
import io
import shutil
import tempfile
from pathlib import Path
from app.services.dpgf_import import DPGFImportService
import traceback

router = APIRouter(prefix='/dpgf', tags=['dpgf'])

@router.post('/upload')
async def upload_dpgf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload un fichier Excel DPGF et lance l'import directement via le service
    
    Le fichier est traité par le service d'import intégré à l'API,
    sans passer par un script externe.
    """
    try:
        # Sauvegarder le fichier temporairement
        print(f"Réception du fichier: {file.filename}")
        tmpdir = tempfile.mkdtemp()
        file_path = os.path.join(tmpdir, file.filename)
        
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        print(f"Fichier sauvegardé à: {file_path}")
        
        # Récupérer la clé Gemini de l'environnement (optionnelle)
        gemini_key = os.environ.get('GEMINI_API_KEY', '')
        use_gemini = bool(gemini_key)
        
        # Créer le service d'import et traiter le fichier
        print("Initialisation du service d'import...")
        import_service = DPGFImportService(
            gemini_key=gemini_key,
            use_gemini=use_gemini
        )
        
        print("Lancement de l'import...")
        # Capturer la sortie standard pour la retourner à l'utilisateur
        import_results = io.StringIO()
        
        # Utiliser une redirection temporaire de stdout
        import sys
        original_stdout = sys.stdout
        sys.stdout = import_results
        
        # Exécuter l'import
        dpgf_id = import_service.import_file(db, file_path)
        
        # Restaurer stdout
        sys.stdout = original_stdout
        
        # Nettoyer les fichiers temporaires
        shutil.rmtree(tmpdir)
        
        if not dpgf_id:
            raise HTTPException(status_code=500, detail="Erreur lors de l'import du DPGF")
        
        return {
            "success": True,
            "dpgf_id": dpgf_id,
            "stdout": import_results.getvalue(),
            "stderr": ""
        }
    
    except Exception as e:
        # Nettoyer en cas d'erreur
        if 'tmpdir' in locals() and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
        
        print(f"Erreur upload: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import: {str(e)}")

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
