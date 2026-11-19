| Tabla | Ruta | Versión |
|---|---|---|
| tenants | /home/davidcv/proyectos/Backend_Beca_Alimentaria/alembic/versions/0002_create_tenants_table.py | 0002_create_tenants_table |
| users | /home/davidcv/proyectos/Backend_Beca_Alimentaria/alembic/versions/0003_create_users_table.py | 0003_create_users_table |

```mermaid
erDiagram
    TENANTS["tenants · 0002_create_tenants_table"] {
        uuid id PK "gen_random_uuid()"
        varchar(20) folio UK "unique lower(folio)"
        varchar(120) name UK "unique lower(name)"
        varchar(120) representative ""
        time breakfast_start "07:00 (0004)"
        time breakfast_end "10:00 (0004)"
        time lunch_start "13:00 (0004)"
        time lunch_end "16:00 (0004)"
        boolean active "TRUE"
        timestamptz created_at "NOW()"
        timestamptz updated_at "NOW()"
    }
```

```mermaid
erDiagram
    TENANTS["tenants · 0002_create_tenants_table"] ||--o{ USERS["users · 0003_create_users_table"] : "tenant_id"

    TENANTS {
        uuid id PK
    }

    USERS {
        uuid id PK "gen_random_uuid()"
        uuid tenant_id FK "NULL solo si SUPERADMIN"
        varchar(20) role "SUPERADMIN | ADMIN | CHECKER"
        varchar(30) username UK "unique lower(username)"
        varchar(120) email UK "unique lower(email)"
        varchar(255) password_hash ""
        varchar(120) full_name ""
        varchar(15) phone ""
        boolean active "TRUE"
        timestamptz last_login_at "nullable"
        timestamptz created_at "NOW()"
        timestamptz updated_at "NOW()"
    }
```

```mermaid
flowchart LR
    A["Frontend (Angular)"] -->|"POST /api/v1/auth/login"| B["authenticate()"]
    B --> C["verify_password()"]
    C -->|"ok"| D["create_access_token() → JWT"]
    D --> A
    A -->|"Bearer token"| E["CORS → Router /api/v1"]
    E --> F["get_current_user()<br/>JWT → User en BD + TenantContext"]
    F --> G["require_roles()"]
    G --> H["Service"]
    H --> I["Repository"]
    I --> J[("PostgreSQL + pgvector")]
    H -.->|"AppException"| K["Exception handlers"]
    K -.->|"{process, message, errors}"| A
```
