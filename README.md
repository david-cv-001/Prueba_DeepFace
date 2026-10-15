# Prueba DeepFace 🔍

Mini proyecto de **reconocimiento facial**: registras rostros conocidos con una foto y luego la webcam del navegador los identifica en tiempo real.

- **Backend**: FastAPI + DeepFace (modelo `Facenet512`) que expone la API y sirve el front.
- **Base de datos**: PostgreSQL 16 con `pgvector` para guardar los embeddings (512 dims) y buscar por distancia coseno.
- **Frontend**: una sola página HTML que abre la cámara y pregunta al backend.
- **Todo con Docker Compose**: no hace falta instalar Python ni Postgres en tu máquina.

```
Navegador (webcam)  ──►  /recognize  ──►  DeepFace (embedding)  ──►  pgvector (búsqueda)
   front/index.html          api                              known_face
```

---

## 1. Requisitos

- **Docker** + **Docker Compose v2** (`docker compose`, con espacio).
- Navegador con cámara (Chrome/Firefox/Edge). El acceso debe ser a `localhost` para que el navegador permita usar la webcam.
- Linux/macOS/Windows. Conexión a internet la primera vez (descarga el modelo de DeepFace).

Comprueba que tienes lo necesario:

```bash
docker --version
docker compose version
```

---

## 2. Arrancar el proyecto

Todos los comandos de Docker se ejecutan **dentro de la carpeta `back/`** (ahí está el `compose.yaml`).

```bash
cd back
docker compose up --build
```

Qué pasa la primera vez (puede tardar varios minutos):

1. Construye la imagen del API instalando TensorFlow y DeepFace.
2. Levanta PostgreSQL y ejecuta `db/init/*.sql`, que crea la extensión `vector` y la tabla `known_face`.
3. El API arranca, **pre-descarga el modelo `Facenet512`** y queda escuchando en el puerto `8000`.

Deja ese terminal abierto (verás los logs). Cuando aparezca algo como `Uvicorn running on http://0.0.0.0:8000`, ya está listo.

### Comprobar que está arriba

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Abrir el front

Abre en el navegador:

| Recurso | URL |
|---|---|
| Interfaz (webcam) | http://localhost:8000/ |
| Documentación de la API (Swagger) | http://localhost:8000/docs |
| Estado | http://localhost:8000/health |

---

## 3. Cargar (enrolar) imágenes

Tienes **dos formas**: con la interfaz de Swagger o con `curl`.

### Opción A — desde Swagger (recomendado para empezar)

1. Entra en http://localhost:8000/docs
2. Abre **`POST /faces`** → botón **Try it out**.
3. Rellena:
   - `name`: el nombre de la persona, p. ej. `David`.
   - `file`: **Choose File** y selecciona una foto clara de la cara (JPG/PNG).
4. Pulsa **Execute**.

Respuesta esperada:

```json
{
  "id": 1,
  "name": "David",
  "image_url": "/images/3f9c...a1.jpg"
}
```

Si la foto no tiene una cara detectada, recibirás un error `422`:

```json
{ "detail": "No se detecto un rostro en la imagen" }
```

### Opción B — desde la terminal con `curl`

```bash
curl -X POST http://localhost:8000/faces \
  -F "name=David" \
  -F "file=@/ruta/a/tu/foto.jpg"
```

Repite el proceso para cada persona. Puedes listar las imágenes registradas porque se guardan en `back/face/`.

---

## 4. Reconocer con la cámara

1. Abre http://localhost:8000/
2. Pulsa **Iniciar cámara** y acepta el permiso del navegador.
3. Ponte frente a la cámara. Cada ~2,5 s el front envía un frame a `POST /recognize`.

Resultado:

- **Coincidencia** → muestra la foto guardada, `Bienvenido, <nombre>` y la distancia.
- **Sin coincidencia** → `No encontrado`.

> La primera detección puede tardar porque el modelo se carga en memoria. Las siguientes son rápidas.

### Probar el endpoint directo (sin cámara)

```bash
curl -X POST http://localhost:8000/recognize -F "file=@/ruta/a/tu/foto.jpg"
```

- Encontrado: `{"found":true,"name":"David","image_url":"...","distance":0.21,"threshold":0.3}`
- No encontrado: `{"found":false}`

---

## 5. Configuración (opcional)

El `compose.yaml` funciona con valores por defecto. Si quieres cambiarlos, crea un archivo `.env` dentro de `back/` (está ignorado por git):

```dotenv
POSTGRES_USER=deepface
POSTGRES_PASSWORD=deepface
POSTGRES_DB=deepface
DEEPFACE_MODEL=Facenet512
DEEPFACE_DETECTOR=opencv
```

| Variable | Descripción | Por defecto |
|---|---|---|
| `POSTGRES_USER` | Usuario de Postgres | `deepface` |
| `POSTGRES_PASSWORD` | Contraseña de Postgres | `deepface` |
| `POSTGRES_DB` | Nombre de la base de datos | `deepface` |
| `DEEPFACE_MODEL` | Modelo de embeddings | `Facenet512` |
| `DEEPFACE_DETECTOR` | Detector de rostro (`opencv`, `retinaface`, …) | `opencv` |

> Si cambias `DEEPFACE_MODEL`, la tabla `known_face` está fijada a `vector(512)`. Usa otro modelo solo si su embedding también es de 512 dims (o actualiza `02-tables.sql` y `models.py`).

---

## 6. Comandos útiles

| Acción | Comando (desde `back/`) |
|---|---|
| Arrancar en segundo plano | `docker compose up -d --build` |
| Ver logs | `docker compose logs -f` |
| Ver logs solo del API | `docker compose logs -f api` |
| Parar (conserva datos) | `docker compose down` |
| Parar y **borrar datos** (DB + pesos) | `docker compose down -v` |
| Reconstruir el API | `docker compose up -d --build api` |
| Entrar a la shell del API | `docker compose exec api bash` |

---

## 7. Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Comprueba API + conexión a la base de datos. |
| `POST` | `/faces` | Registra un rostro (`name` + `file`). |
| `POST` | `/recognize` | Identifica el rostro de un frame (`file`). |
| `GET` | `/images/{archivo}` | Sirve las fotos registradas. |
| `GET` | `/` | Sirve el front (webcam). |
| `GET` | `/docs` | Swagger UI. |

---

## 8. Notas y problemas comunes

- **La primera vez tarda**: construir la imagen (TensorFlow) y descargar el modelo puede llevar varios minutos. Los pesos quedan cacheados en el volumen `deepface_weights`.
- **La cámara no funciona**: usa `http://localhost:8000/` (no la IP de la máquina). Los navegadores solo permiten la webcam en `localhost` o HTTPS.
- **Puerto 5432 ocupado**: si ya tienes otro Postgres local, cambia el mapeo en `compose.yaml` (p. ej. `"5433:5432"`).
- **Cambié los archivos SQL y no se aplican**: los scripts de `db/init/` solo se ejecutan al crear el volumen. Haz `docker compose down -v` y vuelve a levantar.
- **Reseteo total** (borra rostros, base de datos y modelo descargado): `docker compose down -v` y luego `docker compose up --build`.
