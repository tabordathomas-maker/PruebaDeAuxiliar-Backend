# Modelo entidad-relación

La imagen está en [`DER.jpg`](DER.jpg). Las dos versiones reflejan el esquema actual, con las
migraciones `0001` a `0003`; la de Mermaid, además, se puede versionar y comparar en los diffs. El esquema real está en `migrations/versions/`.

```mermaid
erDiagram
    roles ||--o{ users : "1:N"
    users ||--o{ loans : "1:N"
    books ||--o{ loans : "1:N"
    books ||--o{ book_categories : "1:N"
    loans ||--o{ loan_modifications : "1:N"
    users ||--o{ loan_modifications : "1:N (autor)"
    categories ||--o{ book_categories : "1:N"

    roles {
        uuid id PK
        text name UK
    }
    users {
        uuid id PK
        text name
        text email UK
        text password_hash
        uuid role_id FK
        bool active "baja lógica"
    }
    categories {
        uuid id PK
        text name UK
    }
    books {
        uuid id PK
        text title
        text author
        text isbn UK
        int total_copies
        int available_copies
    }
    book_categories {
        uuid book_id PK, FK
        uuid category_id PK, FK
    }
    loans {
        uuid id PK
        uuid user_id FK "indexado"
        uuid book_id FK "indexado"
        timestamptz requested_at "al solicitar"
        timestamptz loaned_at
        timestamptz due_at
        timestamptz returned_at
        loan_status status "pending | active | overdue | returned | rejected"
    }
    loan_modifications {
        uuid id PK
        uuid loan_id FK "indexado"
        uuid modified_by FK
        timestamptz modified_at
        text_array changed_fields
        jsonb old_values
        jsonb new_values
        text reason
    }
```

## Relaciones que pide la prueba

| Requisito | Dónde |
|---|---|
| Tabla pivote | `book_categories`: libros y categorías de muchos a muchos. La PK es la pareja `(book_id, category_id)`, así que un libro no se asigna dos veces a la misma categoría |
| Muchos a uno | `loans → books` y `loans → users`: cada préstamo es de un libro y de un usuario |
| Uno a muchos | `users → loans`: un usuario tiene muchos préstamos (también `roles → users`) |

## Decisiones

- **Roles en su propia tabla.** El token lleva el rol leído de `roles` al iniciar sesión, y se pueden agregar roles sin tocar la estructura.
- **Identificadores UUID** en todas las tablas, para no exponer números consecutivos adivinables en las rutas. Se generan en el dominio, así que el repositorio en memoria y el de Postgres se comportan igual.
- **`available_copies`** está protegido por `CHECK (available_copies >= 0 AND available_copies <= total_copies)`.
- **`returned_at` vacío** significa que el libro no se ha devuelto. `status` distingue además entre pendiente, activo, vencido, devuelto y rechazado.
- **Índices explícitos** en `loans.user_id` y `loans.book_id`, porque Postgres no indexa las llaves foráneas por su cuenta.
- **`ON DELETE RESTRICT`** en las llaves de `loans` y `users`: no se borra un libro ni un usuario con préstamos. En la pivote es `CASCADE`.
- **Roles:** `admin`, `librarian` y `user`. El de `admin` lo agrega la migración `0002`.
- **Bajas lógicas** con `users.active`: las cuentas no se borran, así que sus préstamos y su autoría en la auditoría se conservan.
- **`loan_modifications`** es la auditoría de los cambios de plazos: una fila por modificación, nunca se actualiza. Sus dos llaves son `RESTRICT`, de modo que la base se niega a borrar un préstamo o un usuario que aparezca en el historial. Los valores se guardan en JSONB como texto (fechas ISO 8601 en UTC) para compararlos tal como estaban.
