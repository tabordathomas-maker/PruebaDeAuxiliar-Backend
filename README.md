# Biblioteca: API de préstamo de libros

API REST con arquitectura hexagonal para gestionar el préstamo de libros. Hay tres
roles: **administrador**, **bibliotecario** y **usuario** (lector).

Stack: Python 3.12+, Poetry, FastAPI, SQLAlchemy 2 con Postgres 17, Alembic, JWT
(PyJWT), bcrypt, pytest con pytest-mock, ruff, Invoke para las tareas, Docker y GitHub Actions.

## Requisitos

- Python 3.12 o superior
- [Poetry](https://python-poetry.org/) 2.x
- Docker, para Postgres y para levantar la API en un contenedor

## Levantar con Docker

La forma más corta: la API y Postgres en contenedores, sin instalar Python.

```bash
cp .env.example .env    # y completa POSTGRES_PASSWORD, JWT_SECRET (32+ caracteres), LIBRARIAN_PASSWORD y ADMIN_PASSWORD
docker compose up --build
```

Si tienes Poetry, `poetry run invoke env` crea el `.env` con secretos aleatorios. El repositorio
no guarda ninguna clave: Docker Compose se niega a arrancar si falta `POSTGRES_PASSWORD`.

Al arrancar, el contenedor `api` aplica las migraciones, crea las cuentas iniciales si
faltan y sirve la API en http://127.0.0.1:8000 (Swagger en `/docs`). El puerto se
cambia con `API_PORT`. `docker compose down` lo detiene.

La imagen (`Dockerfile`) tiene dos etapas: la primera instala las dependencias con
Poetry y la segunda solo copia el entorno virtual, y corre con un usuario sin privilegios.

## Instalar (desarrollo local)

```bash
cd PruebaDeAuxiliar-Backend
poetry install
poetry run invoke env   # crea o completa el .env con secretos aleatorios (invoke up también lo hace)
```

## Levantar

```bash
poetry run invoke up
```

Esa única tarea hace todo lo siguiente:
1. Crea el `.env` desde `.env.example`, con `JWT_SECRET`, la clave de Postgres y las claves iniciales generadas al azar. Si ya existe, solo agrega las variables que falten y no cambia las demás.
2. Levanta Postgres con Docker y espera a que esté listo.
3. Aplica las migraciones, que incluyen los roles base.
4. Crea el administrador y el bibliotecario iniciales si todavía no existen.
5. Arranca la API en http://127.0.0.1:8000.

- `GET /` responde `200 {"status": "ok"}`.
- La documentación interactiva está en http://127.0.0.1:8000/docs. El botón *Authorize* acepta el token.
- Administrador inicial: `admin@example.com`, con la clave de `ADMIN_PASSWORD` en tu `.env`.
- Bibliotecario inicial: `bibliotecario@example.com`, con la clave de `LIBRARIAN_PASSWORD` en tu `.env`.
- Los secretos no tienen valor por defecto en el código: si falta alguno, la API no arranca y dice cuál.

### Migraciones

`invoke up` y `invoke migrate` aplican las pendientes con `alembic upgrade head`.
`alembic current` muestra la versión aplicada.

| Versión | Cambios |
|---|---|
| `0001` | Esquema inicial y roles `librarian` y `user` |
| `0002` | Rol `admin`, columna `users.active` (las cuentas existentes quedan activas) y tabla `loan_modifications` |
| `0003` | Columna `loans.requested_at`, la fecha en que se pidió el préstamo. Los préstamos existentes toman su `loaned_at`, o la hora de la migración si siguen pendientes |

Las tres son aditivas. El `downgrade` de `0002` es destructivo: borra la auditoría.

> El contenedor publica Postgres en el puerto **15432**, no en el 5432, para no chocar
> con un Postgres instalado en la máquina. Se cambia con `DB_PORT` y `DATABASE_URL`.

Otras tareas: `invoke db`, `invoke migrate`, `invoke seed`, `invoke lint`, `invoke down` (ver `invoke --list`).

## Probar

```bash
poetry run invoke test     # pytest con cobertura; falla si baja del 80 %
```

`invoke test` mide la cobertura del paquete `biblioteca` (con ramas) y falla si queda por
debajo del 80 % (`fail_under` en `pyproject.toml`). `poetry run pytest` corre las pruebas
sin medirla, útil para lanzar un solo archivo.

- **Casos de uso** (`tests/application`): son pruebas unitarias con el repositorio en memoria y con mocks (`mock_uow`, `pytest-mock`). No necesitan base de datos.
- **HTTP** (`tests/http`): usan la app real, pero con el repositorio en memoria inyectado. Cubren el 401, el 403 y los permisos de cada rol.
- **Contrato de repositorios** (`tests/contract`): las mismas pruebas corren contra el repositorio en memoria y contra Postgres. Eso demuestra que las implementaciones son intercambiables.
- **Integración** (`tests/integration`): contra Postgres. Dos solicitudes simultáneas por la última copia, dos peticiones simultáneas que crean el mismo email, categoría o ISBN (la segunda responde 409), y la atomicidad entre un préstamo y su auditoría: si falla la inserción de la auditoría, el cambio del préstamo se revierte.

Las pruebas nuevas siguen el patrón **AAA** (Arrange, Act, Assert), marcado con comentarios.

Las pruebas que usan Postgres crean y migran su propia base, `biblioteca_test`. Si
Postgres no está levantado (`invoke db`) se **omiten** y el resto corre igual.

### Estilo

```bash
poetry run invoke lint     # ruff check y ruff format --check
```

La configuración de ruff está en `pyproject.toml` (líneas de 100 caracteres; reglas de
pycodestyle, pyflakes, isort, pyupgrade y bugbear). `ruff format .` aplica el formato.

## Integración continua

`.github/workflows/ci.yml` corre en cada push y pull request a `main` y `develop`, con tres jobs:

1. **Estilo:** `invoke lint`.
2. **Pruebas:** `invoke test` contra un Postgres de servicio, así que las pruebas de contrato e integración no se omiten. Falla si la cobertura baja del 80 %.
3. **Construcción:** construye la imagen, levanta todo con `docker compose up --wait` y comprueba que `GET /` responde.

## Ramas

- `main`: versión estable, lista para entregar.
- `develop`: integración; las ramas de trabajo (`feat/…`, `fix/…`, `chore/…`, `docs/…`) se fusionan aquí por pull request, y `develop` pasa a `main` cuando está estable.

## Arquitectura

```
src/biblioteca/
  domain/           entidades (dataclasses sin lógica) y puertos (interfaces)
  application/      casos de uso: toda la lógica de negocio
  adapters/
    http/           routers FastAPI, esquemas, validador global, traducción de errores
    persistence/    repositorios Postgres (por defecto) y en memoria
    security/       bcrypt y JWT detrás de los puertos PasswordHasher y TokenService
  main.py           crea la app y registra el validador global
```

- **Dependencias hacia adentro.** `domain` no importa nada del proyecto, `application` solo depende de `domain`, y los adaptadores dependen de ambos.
- **Persistencia con SQLAlchemy.** El esquema se declara con SQLAlchemy (`adapters/persistence/postgres/tables.py`), las migraciones salen de él con Alembic y los repositorios usan la `Session` del ORM y el lenguaje de expresiones de SQLAlchemy (`select`, `insert`, `update`, con `FOR UPDATE` donde hace falta). Los repositorios traducen las filas a las entidades del dominio, que siguen siendo dataclasses puras sin dependencia de la base.
- **Clases abstractas.** Los puertos de `domain/ports.py` son clases abstractas (`ABC` con `@abstractmethod`): repositorios, `UnitOfWork`, `PasswordHasher` y `TokenService`. Postgres y la memoria son dos implementaciones de las mismas interfaces.
- **Patrón repositorio.** Los casos de uso reciben un `UnitOfWork`, que agrupa los repositorios en una transacción. La implementación concreta se inyecta en `adapters/http/dependencies.py`, y las pruebas la sustituyen con `app.dependency_overrides`.
- **Validador global** (`adapters/http/security.py`). Es una sola dependencia registrada en la app que corre antes de cada ruta. Toda ruta es privada por defecto:
  - Sin token, o con un token inválido o expirado, responde **401**.
  - También responde **401** si la cuenta del token ya no existe, está desactivada o cambió de rol. Se comprueba en la base en cada petición, así que una baja surte efecto de inmediato.
  - `@roles(...)` exige además un rol; si no corresponde, responde **403**.
  - `@public` exime a una ruta.

  Una prueba recorre todas las rutas para comprobar que ninguna queda abierta por accidente.

## Casos de uso y rutas

| Rol | Caso de uso | Ruta |
|---|---|---|
| Público | Registrarse (siempre con rol usuario) | `POST /auth/register` |
| Público | Iniciar sesión y recibir el JWT | `POST /auth/login` |
| Autenticado | Listar categorías | `GET /categories` |
| Autenticado | Buscar libros por categoría | `GET /books?category_id=…` |
| Usuario | Prestar un libro (solicitud) | `POST /loans` |
| Usuario | Devolver un libro | `POST /loans/{id}/return` |
| Usuario | Ver sus propios préstamos | `GET /loans/me?status=…` |
| Bibliotecario | Ver todos los préstamos | `GET /loans?status=…&user_id=…` |
| Bibliotecario | Aprobar un préstamo | `POST /loans/{id}/approve` |
| Bibliotecario | Cerrar un préstamo | `POST /loans/{id}/close` |
| Bibliotecario | Marcar vencido | `POST /loans/{id}/overdue` |
| Bibliotecario | Crear categoría / libro | `POST /categories`, `POST /books` |
| Bibliotecario | Asignar categorías a un libro | `POST /books/{id}/categories` |
| Admin, bibliotecario | Modificar un libro | `PATCH /books/{id}` |
| Admin, bibliotecario | Modificar fechas o plazo de un préstamo (queda auditado) | `PATCH /loans/{id}` |
| Admin, bibliotecario | Ver la auditoría de un préstamo | `GET /loans/{id}/modifications` |
| Admin, bibliotecario | Dar de baja una cuenta (el bibliotecario, solo lectores) | `DELETE /users/{id}` |
| Admin | Crear bibliotecarios y lectores | `POST /users` |
| Admin | Consultar bibliotecarios y lectores | `GET /users?role=…`, `GET /users/{id}` |
| Admin | Modificar bibliotecarios y lectores | `PUT /users/{id}` |
| Autenticado | Ver su propia cuenta | `GET /users/me` |
| Usuario | Modificar sus datos / darse de baja | `PUT /users/me`, `DELETE /users/me` |

### Matriz de permisos de cuentas, libros y plazos

| Operación | Admin | Bibliotecario | Lector |
|---|---|---|---|
| Crear, modificar o desactivar bibliotecarios | Sí | No | No |
| Crear lectores | Sí | No (los lectores se registran solos) | No |
| Modificar datos de lectores | Sí | No | Solo los suyos |
| Desactivar lectores | Sí | Sí | Solo su cuenta |
| Modificar libros | Sí | Sí | No |
| Modificar plazos de préstamos | Sí | Sí | No |
| Consultar la auditoría de préstamos | Sí | Sí | No |

Los administradores no se gestionan por la API: se crean con el seed. Nadie puede
cambiar roles. Las rutas del bibliotecario que ya existían (catálogo, aprobar,
cerrar, marcar vencido, listar préstamos) siguen siendo solo del bibliotecario.

## Reglas de negocio

```
          aprobar             devolver / cerrar
PENDING ──────────► ACTIVE ─────────────────────► RETURNED
   │                  │                              ▲
   │ cerrar           │ marcar vencido               │ devolver / cerrar
   ▼                  ▼                              │
REJECTED           OVERDUE ──────────────────────────┘
```

- **Al solicitar** se guarda la fecha de la solicitud (`requested_at`) y se reserva un ejemplar (`available_copies - 1`). Falla con 409 si no quedan copias. El libro se bloquea (`SELECT … FOR UPDATE`), así que dos solicitudes simultáneas no se llevan la misma copia.
- Un usuario no puede tener dos préstamos abiertos del mismo libro.
- **Al aprobar** empiezan a correr las fechas: `loaned_at = ahora` y `due_at = ahora + LOAN_DAYS` (14 por defecto). Antes de aprobar se **vuelve a validar el stock**. Si el libro ya no existe o sus copias no cuadran con los préstamos abiertos, la aprobación falla con un error de stock (409).
- **Cerrar** rechaza un préstamo pendiente o registra la devolución de uno activo o vencido. En ambos casos repone el ejemplar.
- **Devolver** lo hace el usuario con sus propios préstamos activos o vencidos. Los préstamos de otro usuario responden 404, para no revelar que existen.
- **Marcar vencido** solo se permite en préstamos activos cuya fecha límite ya pasó.
- **Modificar plazos** (`PATCH /loans/{id}`) acepta `loaned_at`, `due_at` o `duration_days` (excluyente con `due_at`), más un `reason` opcional, y solo en préstamos activos o vencidos. Las fechas deben traer zona horaria y se guardan en UTC. `loaned_at` no puede ser futura y `due_at` debe ser posterior a `loaned_at`. Si un préstamo vencido recibe una fecha límite futura, vuelve a `active`.
- **Auditoría.** Cada modificación de plazos inserta una fila en `loan_modifications` con el préstamo, quién la hizo, cuándo (UTC), los campos cambiados y sus valores anteriores y nuevos. Se escribe en la misma transacción que el préstamo, así que o se guardan los dos o ninguno. La API no permite editar ni borrar estos registros.
- **Bajas lógicas.** `DELETE /users/...` pone `active = false`: la cuenta no puede iniciar sesión y sus tokens dejan de valer. Préstamos y auditoría se conservan. Se niega con 409 si la cuenta tiene préstamos abiertos.
- **Modificar un libro**: cambiar `total_copies` mueve `available_copies` en la misma cantidad y no puede bajar por debajo de los ejemplares que están fuera (409).
- **Textos obligatorios.** Nombre de categoría, título, autor, ISBN y nombre de usuario se guardan sin espacios en los extremos; si quedan vacíos, responden 422.
- **Duplicados simultáneos.** Si dos peticiones crean a la vez el mismo email, categoría o ISBN, la base frena la segunda y la API responde 409, igual que con un duplicado normal.

Códigos de error: 401 (sin credenciales válidas), 403 (rol sin acceso o recurso
ajeno), 404 (no existe), 409 (conflicto o regla de negocio), 422 (entrada inválida).

## Modelo entidad-relación

Está en [`docs/DER.jpg`](docs/DER.jpg), y en [`docs/er.md`](docs/er.md) en versión Mermaid, junto con las decisiones de diseño.

## Variables de entorno

| Variable | Por defecto |
|---|---|
| `POSTGRES_USER` / `POSTGRES_DB` | `biblioteca` / `biblioteca` (usuario y base del contenedor) |
| `POSTGRES_PASSWORD` | **obligatoria** para Docker Compose; Postgres la fija al crear el volumen |
| `DATABASE_URL` | **obligatoria**, sin valor por defecto; `invoke env` la arma con las `POSTGRES_*` |
| `TEST_DATABASE_URL` | la `DATABASE_URL`, con la base `biblioteca_test` |
| `DB_PORT` | `15432` (puerto publicado por Docker) |
| `JWT_SECRET` | **obligatoria**, sin valor por defecto; al menos 32 caracteres |
| `JWT_ALGORITHM` / `JWT_EXPIRES_MINUTES` | `HS256` / `60` |
| `LOAN_DAYS` | `14` |
| `LIBRARIAN_NAME` / `LIBRARIAN_EMAIL` | bibliotecario inicial (`Bibliotecario` / `bibliotecario@example.com`) |
| `LIBRARIAN_PASSWORD` | **obligatoria**, sin valor por defecto; al menos 8 caracteres |
| `ADMIN_NAME` / `ADMIN_EMAIL` | administrador inicial (`Administrador` / `admin@example.com`) |
| `ADMIN_PASSWORD` | **obligatoria**, sin valor por defecto; al menos 8 caracteres |

Fuera de alcance: interfaz gráfica y despliegue.
