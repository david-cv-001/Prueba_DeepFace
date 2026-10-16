import os
import tempfile
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from deepface import DeepFace
from deepface.modules import verification
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import get_db
from .models import EMBEDDING_DIM, KnownFace

MODEL_NAME = os.getenv("DEEPFACE_MODEL", "Facenet512")
DETECTOR_BACKEND = os.getenv("DEEPFACE_DETECTOR", "opencv")

BASE_DIR = Path(__file__).resolve().parent.parent  # /code dentro del contenedor
FACE_DIR = Path(os.getenv("FACE_DIR", BASE_DIR / "face"))
FRONT_DIR = Path(os.getenv("FRONT_DIR", BASE_DIR / "front"))
FACE_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def _threshold(model: str) -> float:
    """Umbral de distancia coseno recomendado por DeepFace para el modelo."""
    try:
        return float(
            verification.find_threshold(model_name=model, distance_metric="cosine")
        )
    except Exception:
        return 0.30


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-descarga el modelo para que la primera peticion no tarde.
    try:
        DeepFace.build_model(MODEL_NAME)
    except Exception:
        pass
    yield


app = FastAPI(title="Prueba DeepFace", version="0.2.0", lifespan=lifespan)


def _save_temp(upload: UploadFile) -> str:
    """Guarda el archivo subido en un temporal y devuelve su ruta."""
    suffix = os.path.splitext(upload.filename or "")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(upload.file.read())
        return tmp.name


def _embedding(path: str, model: str, detector_backend: str) -> list[float] | None:
    """Devuelve el embedding del rostro o None si no se detecto ninguno."""
    try:
        reps = DeepFace.represent(
            img_path=path,
            model_name=model,
            detector_backend=detector_backend,
            enforce_detection=True,
        )
    except ValueError:
        return None
    if not reps:
        return None
    embedding = reps[0].get("embedding")
    if embedding and len(embedding) == EMBEDDING_DIM:
        return embedding
    return None


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/faces")
def enroll_face(
    name: str = Form(..., min_length=1, description="Nombre de la persona"),
    file: UploadFile = File(..., description="Foto del rostro"),
    db: Session = Depends(get_db),
):
    """Registra un rostro conocido: guarda la foto y su embedding."""
    suffix = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    filename = f"{uuid4().hex}{suffix}"
    dest = FACE_DIR / filename
    dest.write_bytes(file.file.read())

    embedding = _embedding(str(dest), MODEL_NAME, DETECTOR_BACKEND)
    if embedding is None:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="No se detecto un rostro en la imagen")

    face = KnownFace(name=name, image_filename=filename, embedding=embedding)
    db.add(face)
    db.commit()
    db.refresh(face)

    return {
        "id": face.id,
        "name": face.name,
        "image_url": f"/images/{face.image_filename}",
    }


@app.delete("/faces/{face_id}", status_code=204)
def delete_face(face_id: int, db: Session = Depends(get_db)):
    """Elimina un rostro conocido: borra la fila y su foto."""
    face = db.get(KnownFace, face_id)
    if face is None:
        raise HTTPException(status_code=404, detail="Rostro no encontrado")

    filename = face.image_filename
    db.delete(face)
    db.commit()
    # Borra la imagen del disco (si ya no existe, no falla).
    (FACE_DIR / filename).unlink(missing_ok=True)
    return Response(status_code=204)


@app.get("/faces")
def list_faces(db: Session = Depends(get_db)):
    """Lista los rostros conocidos (sin el embedding)."""
    faces = db.execute(select(KnownFace).order_by(KnownFace.id)).scalars().all()

    return [
        {
            "id": f.id,
            "name": f.name,
            "image_url": f"/images/{f.image_filename}",
            "created_at": f.created_at,
        }
        for f in faces
    ]


@app.post("/recognize")
def recognize(
    file: UploadFile = File(..., description="Frame tomado de la camara"),
    db: Session = Depends(get_db),
):
    """Busca el rostro en la base de datos y devuelve la coincidencia mas cercana."""
    path = _save_temp(file)
    try:
        embedding = _embedding(path, MODEL_NAME, DETECTOR_BACKEND)
    finally:
        os.unlink(path)

    if embedding is None:
        return {"found": False}

    distance = KnownFace.embedding.cosine_distance(embedding)
    row = db.execute(
        select(KnownFace, distance.label("distance")).order_by(distance).limit(1)
    ).first()

    if row is None:
        return {"found": False}

    face, dist = row
    threshold = _threshold(MODEL_NAME)
    if dist is not None and float(dist) <= threshold:
        return {
            "found": True,
            "name": face.name,
            "image_url": f"/images/{face.image_filename}",
            "distance": float(dist),
            "threshold": threshold,
        }
    return {"found": False}


# Archivos estáticos: las fotos de los rostros y el front.
app.mount("/images", StaticFiles(directory=str(FACE_DIR)), name="images")
if FRONT_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONT_DIR), html=True), name="front")
