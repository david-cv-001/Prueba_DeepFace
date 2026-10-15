-- Tablas del proyecto.
-- Se ejecuta una sola vez al crear el volumen de Postgres (docker-entrypoint-initdb.d).
-- La extension `vector` la crea 01-extension.sql.

CREATE TABLE IF NOT EXISTS known_face (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(120) NOT NULL,
    image_filename VARCHAR(255) NOT NULL,
    embedding      vector(512)   NOT NULL,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_known_face_name ON known_face (name);
