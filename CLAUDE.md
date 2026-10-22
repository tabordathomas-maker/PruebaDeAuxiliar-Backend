# CLAUDE.md: Biblioteca (API de préstamo de libros)

Prueba técnica de backend: API REST con arquitectura hexagonal para prestar libros, con tres
roles (`admin`, `librarian` y `user`). Sin interfaz gráfica ni despliegue (fuera de alcance).
Repo: github.com/tabordathomas-maker/PruebaDeAuxiliar-Backend, rama `main`.

Especificaciones originales (en `~/Downloads`): `BaseDelproyecto.md` (requisitos),
`CasosDeusoPoRol.md` (casos de uso y roadmap de commits), `reglasdenegocio.txt` (decisiones del
modelo), `DER.jpg`, `implementar.md` (requerimiento de admin, gestión de cuentas y auditoría).
La bitácora y las historias de usuario están en `~/Downloads/Bitacora-Biblioteca.md`: es la
"bitácora" del proyecto, y se actualiza ahí sin borrar entradas anteriores.

## Comandos

```bash
poetry install
poetry run invoke up      # Postgres (Docker) + migraciones + seed + API en 127.0.0.1:8000
poetry run invoke test    # pytest --cov; falla con cobertura < 80 %. Las pruebas de Postgres se omiten si la BD no está arriba
poetry run invoke env | db | migrate | seed | down
```

- Swagger: http://127.0.0.1:8000/docs (botón *Authorize* con el JWT de `/auth/login`).
- Postgres corre en Docker en el puerto **15432** (contenedor `biblioteca-db-1`, usuario, clave y BD `biblioteca`).
  Las pruebas usan otra base, `biblioteca_test`.
- Consultar datos: `docker exec biblioteca-db-1 psql -U biblioteca -d biblioteca -c "…"`.
- Cuentas del seed: `admin@example.com` y `bibliotecario@example.com`; sus claves son `ADMIN_PASSWORD` y `LIBRARIAN_PASSWORD` del `.env`. El seed no cambia la clave de una cuenta que ya existe.
- **Secretos sin valor por defecto** (`JWT_SECRET`, `LIBRARIAN_PASSWORD`, `ADMIN_PASSWORD`): si faltan, `create_app()` lanza `ConfigurationError` y la app no arranca. `invoke env` crea el `.env` (ignorado por git) con valores aleatorios; las pruebas los fijan al inicio de `tests/conftest.py`. Nunca escribas claves reales en el código, el README ni este archivo.
- Migraciones: `0001` (esquema inicial) y `0002` (rol admin, `users.active`, `loan_modifications`).
  `alembic check` confirma que `tables.py` y las migraciones coinciden. Toda tabla nueva va
  también en `DATA_TABLES` de `tests/conftest.py`.
- Para pruebas de humo usa la base `biblioteca_test` (exporta `DATABASE_URL`), no la de desarrollo.
- En Windows el intérprete es `.venv/Scripts/python`.

## Requisitos

### Funcionales

| ID | Rol | Requisito | Ruta |
|---|---|---|---|
| RF-01 | Público | Registrarse (siempre con rol `user`) | `POST /auth/register` |
| RF-02 | Público | Iniciar sesión y recibir el JWT | `POST /auth/login` |
| RF-03 | Autenticado | Listar categorías | `GET /categories` |
| RF-04 | Autenticado | Buscar libros por categoría | `GET /books?category_id=` |
| RF-05 | Usuario | Solicitar un préstamo | `POST /loans` |
| RF-06 | Usuario | Devolver su libro | `POST /loans/{id}/return` |
| RF-07 | Usuario | Ver sus propios préstamos (filtro por estado) | `GET /loans/me?status=` |
| RF-08 | Bibliotecario | Ver todos los préstamos (filtros por estado y usuario) | `GET /loans?status=&user_id=` |
| RF-09 | Bibliotecario | Aprobar, cerrar o marcar vencido | `POST /loans/{id}/approve\|close\|overdue` |
| RF-10 | Bibliotecario | Crear categorías y libros, asignar categorías | `POST /categories`, `POST /books`, `POST /books/{id}/categories` |
| RF-11 | Público | Health check, responde 200 | `GET /` |
| RF-12 | Admin, bibliotecario | Modificar un libro | `PATCH /books/{id}` |
| RF-13 | Admin, bibliotecario | Modificar fechas o plazo de un préstamo (auditado) | `PATCH /loans/{id}` |
| RF-14 | Admin, bibliotecario | Ver la auditoría de un préstamo | `GET /loans/{id}/modifications` |
| RF-15 | Admin | Crear, consultar y modificar bibliotecarios y lectores | `POST /users`, `GET /users[/{id}]`, `PUT /users/{id}` |
| RF-16 | Admin, bibliotecario | Desactivar cuentas (el bibliotecario, solo lectores) | `DELETE /users/{id}` |
| RF-17 | Autenticado / usuario | Ver su cuenta; el lector además la modifica o se da de baja | `GET`, `PUT`, `DELETE /users/me` |

Matriz de permisos (criterio de aceptación de `implementar.md`). **No amplíes permisos por conveniencia**:

| Operación | Admin | Bibliotecario | Lector |
|---|---|---|---|
| Crear, modificar o desactivar bibliotecarios | Sí | No | No |
| Crear lectores | Sí | No (registro público) | No |
| Modificar lectores | Sí | No | Solo él mismo |
| Desactivar lectores | Sí | Sí | Solo él mismo |
| Modificar libros y plazos de préstamos | Sí | Sí | No |
| Ver la auditoría de préstamos | Sí | Sí | No |

El admin **no** tiene acceso a las rutas que ya eran del bibliotecario (catálogo, aprobar,
cerrar, vencer, listar préstamos), y nadie gestiona administradores por la API: se crean con el seed.

### No funcionales

- **Arquitectura hexagonal** de tres capas: dominio, casos de uso y adaptadores. Toda la lógica de negocio vive **solo** en `application/`.
- **Patrón repositorio** detrás de interfaces. Postgres es la implementación por defecto y la de memoria demuestra que es intercambiable.
- **Seguridad:** un validador global comprueba el JWT y el rol. Sin token o con token inválido responde 401; con un rol no permitido, 403. Además, `VerifyPrincipal` consulta la base en cada petición: si la cuenta no existe, está desactivada o cambió de rol, responde 401.
- **Trazabilidad:** todo cambio de plazos de un préstamo deja un registro independiente en `loan_modifications`, en la misma transacción que el cambio.
- **Integridad:** las bajas son lógicas (`users.active`); préstamos y auditoría nunca se borran (FK `RESTRICT`).
- **Fechas:** con zona horaria; se guardan y comparan en UTC.
- **Modelo ER:** tabla pivote `book_categories`, relaciones muchos a uno (préstamo → libro y préstamo → usuario) y uno a muchos (usuario → préstamos). Diagrama en `docs/`.
- **Herramientas:** Poetry; una sola tarea Invoke levanta todo; un solo comando corre las pruebas.
- **Pruebas:** unitarias de casos de uso con repositorios simulados (memoria y mocks con pytest-mock).
- **Concurrencia:** dos solicitudes simultáneas no se llevan la misma última copia (`SELECT … FOR UPDATE`).
- **Privacidad:** los IDs son UUID; un préstamo ajeno responde 404 para no revelar que existe; el login no dice si falló el email o la clave.
- **Documentación:** el README explica cómo instalar, levantar y probar.

## Arquitectura

```
src/biblioteca/
  domain/entities.py     dataclasses sin lógica: User, Role, Book, Category, Loan, LoanModification, LoanStatus, RoleName, Principal
  domain/ports.py        interfaces: repositorios (incl. LoanModificationRepository), UnitOfWork, PasswordHasher, TokenService
  application/           casos de uso (auth, catalog, search, loans, users) + errors.py
  adapters/http/         routers FastAPI (auth, catalog, loans, users), schemas, security.py (validador global), errors.py, dependencies.py
  adapters/persistence/  postgres/ (tables.py, repositories.py) y memory.py
  adapters/security/     bcrypt_hasher.py, jwt_tokens.py
  config.py              Settings (pydantic-settings, lee .env)
  seed.py                crea el administrador y el bibliotecario iniciales (idempotente)
  main.py                create_app(): registra el validador global y los routers
migrations/              Alembic: 0001_initial_schema y 0002_admin_role_and_loan_audit
```

- **Las dependencias apuntan hacia adentro:** `domain` no importa nada del proyecto y `application` solo importa `domain`.
- **Flujo de una petición:** `global_validator` decodifica el JWT, comprueba el rol de la ruta, verifica la cuenta en la base (`VerifyPrincipal`) y guarda el principal en `request.state.principal` → la ruta obtiene `current_principal` y `get_uow` → el caso de uso abre `with uow:`, usa los repositorios y hace `uow.commit()` → `LoanResponse.of(...)` arma la respuesta.
- **Rutas privadas por defecto.** Usa `@public` para eximir una ruta y `@roles(RoleName.X)` para exigir un rol. Una prueba recorre todas las rutas, así que toda ruta nueva debe llevar uno de los dos decoradores o quedará privada.
- **Errores:** los casos de uso lanzan `ApplicationError` y `adapters/http/errors.py` los traduce: `NotFoundError` → 404, `ConflictError` y `BusinessRuleError` (incluye `StockError`) → 409, `InvalidCredentialsError` e `InvalidTokenError` → 401, `ForbiddenError` → 403, `InvalidInputError` → 422. La entrada inválida responde 422 (FastAPI). Los textos obligatorios pasan por `required_text` (`application/errors.py`), que quita espacios y rechaza el texto vacío.
- **Inyección:** `adapters/http/dependencies.py`. Las pruebas la sustituyen con `app.dependency_overrides` por el UoW en memoria.
- **Hora:** los casos de uso de préstamos reciben `clock` (por defecto `utc_now`); las pruebas inyectan una hora fija.

## Lógica de negocio

```
PENDING ─aprobar─► ACTIVE ─devolver/cerrar─► RETURNED
   │                 │                          ▲
   cerrar         marcar vencido                │ devolver/cerrar
   ▼                 ▼                          │
REJECTED          OVERDUE ──────────────────────┘
```

- **Solicitar** (`BorrowBook`): bloquea el libro y falla si el usuario ya tiene un préstamo abierto (`PENDING`, `ACTIVE` u `OVERDUE`) de ese libro o si `available_copies < 1`. Si pasa, resta 1 a `available_copies` y crea el préstamo en `PENDING`. **La copia se reserva al solicitar**, no al aprobar.
- **Aprobar** (`ApproveLoan`): solo préstamos `PENDING`. Vuelve a validar el stock: el libro debe existir, los préstamos abiertos no pueden superar `total_copies` y se debe cumplir `available_copies == total_copies - abiertos`; si no, lanza `StockError`. Fija `loaned_at = ahora` y `due_at = ahora + LOAN_DAYS` (14).
- **Cerrar** (`CloseLoan`): si es `PENDING`, lo pasa a `REJECTED`; si es `ACTIVE` u `OVERDUE`, lo pasa a `RETURNED` con `returned_at`. En los dos casos repone la copia. Desde otro estado responde 409.
- **Devolver** (`ReturnBook`): el usuario, sobre **su** préstamo `ACTIVE` u `OVERDUE`. Un préstamo ajeno se trata como inexistente (404).
- **Marcar vencido** (`MarkLoanOverdue`): solo `ACTIVE` con `due_at` ya pasado. Lo hace el bibliotecario a mano; no hay job automático.
- **Listar** (`ListLoans`): el bibliotecario ve todo; un no bibliotecario queda forzado a su propio `user_id`, y si pide otro recibe `ForbiddenError`.
- **Catálogo:** nombre de categoría e ISBN únicos (409). Nombre de categoría, título, autor, ISBN y nombre de usuario en blanco responden 422. Un libro necesita al menos 1 copia y nace con `available = total`. Asignar categorías **suma** a las existentes. Buscar en una categoría inexistente responde 404, no `[]`.
- **Auth:** el email se normaliza (trim y minúsculas, `normalize_email`). El rol se lee de la tabla `roles` al iniciar sesión y viaja en el claim `role` del JWT, junto con `sub` (el user_id). Una cuenta desactivada no puede iniciar sesión (401, mismo mensaje que credenciales erróneas). Sin límite de préstamos por usuario.
- **Modificar plazos** (`ModifyLoanTerms`): solo `ACTIVE` u `OVERDUE`. Acepta `loaned_at`, `due_at` o `duration_days` (excluyente con `due_at`; recalcula desde `loaned_at`) y un `reason` opcional. Las fechas deben traer zona horaria y se guardan en UTC. `loaned_at` no puede ser futura, `due_at` debe ser mayor que `loaned_at` y algo debe cambiar; si no, `BusinessRuleError` (409). Un `OVERDUE` con nueva `due_at` futura vuelve a `ACTIVE`, y el cambio de estado también se audita.
- **Auditoría** (`loan_modifications`): `changed_fields` más `old_values`/`new_values` (JSONB, texto ISO UTC, solo los campos cambiados), `modified_by`, `modified_at` y `reason`. Se agrega en el mismo `with uow` que `loans.update` y antes del único `commit`. El puerto solo tiene `add` y `list_by_loan`: es de solo inserción, y la API no expone escritura sobre la auditoría.
- **Cuentas** (`application/users.py`): los permisos viven en `MANAGEABLE_ROLES`, `DEACTIVATABLE_ROLES` y `SELF_SERVICE_ROLES`. Un rol fuera de lo permitido recibe `ForbiddenError` (403); una cuenta inexistente, `NotFoundError` (404). Nadie cambia roles (los esquemas usan `extra="forbid"`, así que mandar `role`, `active` o `id` da 422). La baja se niega con 409 si hay préstamos abiertos, y es idempotente.
- **Libros** (`UpdateBook`): ISBN único. Cambiar `total_copies` mueve `available_copies` en la misma cantidad y no puede quedar por debajo de los ejemplares que están fuera (`StockError`, 409).

## Pruebas

- `tests/application/`: casos de uso con `memory_uow` y `mock_uow`.
- `tests/http/`: la app real con el repositorio en memoria; fixtures `client`, `admin`, `librarian`, `reader` y `create_account(role)` en `tests/conftest.py` (las cuentas traen `.headers`).
- `tests/contract/`: las mismas pruebas contra memoria y Postgres.
- `tests/integration/`: contra Postgres; concurrencia y atomicidad préstamo/auditoría.
- Todo nuevo caso de uso lleva pruebas de aplicación y de HTTP (incluidos 401 y 403).
- **Las pruebas nuevas siguen el patrón AAA** con comentarios `# Arrange`, `# Act`, `# Assert` (o `# Act / Assert` con `pytest.raises`).
- Los tokens de prueba deben pertenecer a cuentas registradas en el almacén: el validador las verifica en la base.

## Avance

21 commits en `main`, todos subidos: el roadmap original (16) y la fase 5 de `implementar.md`
(5). La suite queda en 307 pruebas pasando. Commits del roadmap:
- Fase 1, base: `chore: add project base with poetry`, `feat: add health route`.
- Fase 2, dominio y datos: `feat: add domain entities`, `feat: add repository ports`, `feat: add postgres repositories and schema`, `feat: add in memory repositories`.
- Fase 3, seguridad: `feat: add jwt authentication`, `feat: add global role validators`.
- Fase 4, casos de uso: `feat: add catalog management use case`, `feat: add book search by category use case`, `feat: add borrow book use case`, `feat: add return book use case`, `feat: add list loans use case`, `feat: add librarian loan management use case`.
- Cierre: `docs: add readme and er diagram`, `refactor: move backend files to repository root` (ya no existe la carpeta `Backend/`).
- Fase 5, admin, cuentas y auditoría: `feat: add admin role and loan audit persistence`, `feat: add account management use cases`, `feat: add book update use case`, `feat: add loan terms modification with audit`, `docs: document admin role, accounts and loan audit`.
- Pendiente: `docs/DER.jpg` sigue mostrando el esquema `0001` (`docs/er.md` sí está al día).

## Convenciones

- Commits en Conventional Commits, en inglés y en minúsculas, en imperativo (`feat: add …`, `docs: …`, `refactor: …`), cada uno con sus pruebas. Si hace falta, un cuerpo breve en inglés explica el porqué.
- **El usuario es el único autor:** nunca añadas `Co-Authored-By` ni atribución a Claude en commits o PRs.
- No hagas commit ni push sin que el usuario lo pida.
- Código, docstrings, comentarios y mensajes de error en español; identificadores en inglés.
- Si `GET /loans/me` devuelve `[]`, revisa que el token sea del usuario dueño de los préstamos antes de buscar un bug.
