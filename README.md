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
o
docker compose up -d
```

Qué pasa la primera vez (puede tardar varios minutos):

1. Construye la imagen del API instalando TensorFlow y DeepFace.
2. Levanta PostgreSQL y ejecuta `db/init/*.sql`, que crea la extensión `vector` y la tabla `known_face`.
3. El API arranca, **pre-descarga el modelo `Facenet512`** y queda escuchando en el puerto `8000`.

Deja ese terminal abierto (verás los logs). Cuando aparezca algo como `Uvicorn running on http://0.0.0.0:8000`, ya está listo.

### Comprobar que está arriba

```bash
http://localhost:8000/health
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

## 3. Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Comprueba API + conexión a la base de datos. |
| `GET` | `/faces` | Lista los rostros registrados (sin el embedding). |
| `POST` | `/faces` | Registra un rostro (`name` + `file`): guarda la foto y su embedding. |
| `DELETE` | `/faces/{face_id}` | Elimina un rostro por su `id` (borra la fila y su foto). Devuelve `204`. |
| `POST` | `/recognize` | Identifica el rostro de un frame (`file`) buscando la coincidencia más cercana. |
| `GET` | `/images/{archivo}` | Sirve las fotos registradas. |
| `GET` | `/` | Sirve el front (webcam). |
| `GET` | `/docs` | Swagger UI. |

---

## 4. ¿Cómo funciona DeepFace?

DeepFace se encarga de **convertir una cara en un vector de números** (el *embedding*). Con ese vector comparamos dos rostros midiendo la distancia entre ellos. Nada más: DeepFace es una librería de cálculo, **no guarda tus datos ni tu base de datos**.

### 4.1. Qué hace con cada imagen

1. **Detección**: encuentra la cara dentro de la foto usando un *detector*. Aquí usamos `opencv` (backend `DEEPFACE_DETECTOR=opencv`).
2. **Alineación y normalización**: recorta/endereza la cara y ajusta tamaño y colores.
3. **Embedding**: pasa la cara por la red neuronal del modelo elegido. Con `Facenet512` (`DEEPFACE_MODEL=Facenet512`) devuelve un vector de **512 números** (floats).
4. **Comparación**: para saber si dos caras son la misma persona se calcula la **distancia coseno** entre sus vectores. Cuanto más pequeña, más parecidas. Se compara con un **umbral** (nosotros lo sacamos de `deepface.modules.verification.find_threshold`).

### 4.2. Dónde y cómo se guardan los *pesos* del modelo

- El modelo son unos **pesos preentrenados** (no se entrena nada aquí). Se guardan en un archivo **`.h5`** (formato HDF5, es decir, binario con la red ya entrenada), no en la base de datos.
- Ruta por defecto dentro de la librería: `~/.deepface/weights/`. En el contenedor (usuario `root`) es `/root/.deepface/weights/facenet512_weights.h5` (~**95 MB**).
- En este proyecto ese directorio está montado en el **volumen Docker `deepface_weights`**, así que **sobrevive** a reinicios y a reconstruir la imagen.

### 4.3. ¿Necesita internet? ¿Local o red?

- **La primera vez**: sí. Si el archivo `.h5` no existe, DeepFace lo **descarga** desde GitHub (`github.com/serengil/deepface_models`, release `v1.0`). Con `Facenet512` son ~95 MB.
- **Después**: **no**. El archivo queda en el volumen y se lee **desde el disco local**. A partir de ahí todo funciona **sin conexión**.
- El **detector `opencv`** no descarga nada: usa un clasificador Haar que viene incluido con OpenCV.
- Internet también hizo falta al construir la imagen (para `pip install`).
- Si borras el volumen (`docker compose down -v`), **vuelve a descargar** el modelo.

### 4.4. ¿Se carga una vez y queda en memoria?

- Sí. Al arrancar, el API hace `DeepFace.build_model("Facenet512")` (el *warmup* en `lifespan`) y **carga los pesos en RAM una sola vez**.
- Todas las peticiones (`/faces`, `/recognize`) reutilizan ese modelo ya cargado: **no se vuelve a descargar ni a leer del disco** en cada llamada.
- Por eso la primera petición tras arrancar ya es rápida; el único coste es el arranque.

### 4.5. Entonces… ¿quién guarda la información?

Dos sitios, y **ninguno es DeepFace**:

| Qué | Dónde | Cómo |
|---|---|---|
| El **modelo** (pesos) | Volumen Docker `deepface_weights` (`/root/.deepface/weights/`) | Archivo `.h5` (HDF5), ~95 MB. |
| Los **rostros conocidos** | PostgreSQL (`known_face`) | `name`, `image_filename` y el **embedding** en una columna `vector(512)` (pgvector). |
| Las **fotos** | Carpeta `back/face/` | Imágenes `.jpg`/`.png` servidas en `/images/...`. |

Resumen: **DeepFace solo calcula** el vector; **tu base de datos** guarda el nombre y el vector; **la carpeta `face/`** guarda la foto. En `/recognize` se calcula el vector del frame y se buscan con pgvector las filas más cercanas por distancia coseno.

---
