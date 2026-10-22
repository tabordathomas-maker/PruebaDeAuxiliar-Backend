# Biblioteca: API de préstamo de libros

API REST con arquitectura hexagonal para gestionar el préstamo de libros. Hay dos
roles: **bibliotecario** y **usuario**.

Stack: Python 3.12+, Poetry, FastAPI, SQLAlchemy 2 con Postgres 17, Alembic, JWT
(PyJWT), bcrypt, pytest con pytest-mock, e Invoke para las tareas.

## Requisitos

- Python 3.12 o superior
- [Poetry](https://python-poetry.org/) 2.x
- Docker, para Postgres

## Instalar

```bash
cd PruebaDeAuxiliar-Backend
poetry install
cp .env.example .env   # opcional: los valores por defecto ya sirven en local
```

## Levantar

```bash
poetry run invoke up
```

Esa única tarea hace todo lo siguiente:
1. Levanta Postgres con Docker y espera a que esté listo.
2. Aplica las migraciones, que incluyen los roles base.
3. Crea el bibliotecario inicial si todavía no existe.
4. Arranca la API en http://127.0.0.1:8000.

- `GET /` responde `200 {"status": "ok"}`.
- La documentación interactiva está en http://127.0.0.1:8000/docs. El botón *Authorize* acepta el token.
- Bibliotecario inicial: `bibliotecario@example.com` / `bibliotecario123`. Se cambia con `LIBRARIAN_EMAIL` y `LIBRARIAN_PASSWORD`.

> El contenedor publica Postgres en el puerto **15432**, no en el 5432, para no chocar
> con un Postgres instalado en la máquina. Se cambia con `DB_PORT` y `DATABASE_URL`.

Otras tareas: `invoke db`, `invoke migrate`, `invoke seed`, `invoke down` (ver `invoke --list`).

## Probar

```bash
poetry run invoke test     # o: poetry run pytest
```

- **Casos de uso** (`tests/application`): son pruebas unitarias con el repositorio en memoria y con mocks (`mock_uow`, `pytest-mock`). No necesitan base de datos.
- **HTTP** (`tests/http`): usan la app real, pero con el repositorio en memoria inyectado. Cubren el 401, el 403 y los permisos de cada rol.
- **Contrato de repositorios** (`tests/contract`): las mismas pruebas corren contra el repositorio en memoria y contra Postgres. Eso demuestra que las implementaciones son intercambiables.
- **Integración** (`tests/integration`): dos solicitudes simultáneas por la última copia, contra Postgres.

Las pruebas que usan Postgres crean y migran su propia base, `biblioteca_test`. Si
Postgres no está levantado (`invoke db`) se **omiten** y el resto corre igual.

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
- **Patrón repositorio.** Los casos de uso reciben un `UnitOfWork`, que agrupa los repositorios en una transacción. La implementación concreta se inyecta en `adapters/http/dependencies.py`, y las pruebas la sustituyen con `app.dependency_overrides`.
- **Validador global** (`adapters/http/security.py`). Es una sola dependencia registrada en la app que corre antes de cada ruta. Toda ruta es privada por defecto:
  - Sin token, o con un token inválido o expirado, responde **401**.
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

## Reglas de negocio

```
          aprobar             devolver / cerrar
PENDING ──────────► ACTIVE ─────────────────────► RETURNED
   │                  │                              ▲
   │ cerrar           │ marcar vencido               │ devolver / cerrar
   ▼                  ▼                              │
REJECTED           OVERDUE ──────────────────────────┘
```

- **Al solicitar** se reserva un ejemplar (`available_copies - 1`). Falla con 409 si no quedan copias. El libro se bloquea (`SELECT … FOR UPDATE`), así que dos solicitudes simultáneas no se llevan la misma copia.
- Un usuario no puede tener dos préstamos abiertos del mismo libro.
- **Al aprobar** empiezan a correr las fechas: `loaned_at = ahora` y `due_at = ahora + LOAN_DAYS` (14 por defecto). Antes de aprobar se **vuelve a validar el stock**. Si el libro ya no existe o sus copias no cuadran con los préstamos abiertos, la aprobación falla con un error de stock (409).
- **Cerrar** rechaza un préstamo pendiente o registra la devolución de uno activo o vencido. En ambos casos repone el ejemplar.
- **Devolver** lo hace el usuario con sus propios préstamos activos o vencidos. Los préstamos de otro usuario responden 404, para no revelar que existen.
- **Marcar vencido** solo se permite en préstamos activos cuya fecha límite ya pasó.

Códigos de error: 401 (sin credenciales válidas), 403 (rol sin acceso o recurso
ajeno), 404 (no existe), 409 (conflicto o regla de negocio), 422 (entrada inválida).

## Modelo entidad-relación

Está en [`docs/DER.jpg`](docs/DER.jpg), y en [`docs/er.md`](docs/er.md) en versión Mermaid, junto con las decisiones de diseño.

## Variables de entorno

| Variable | Por defecto |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://biblioteca:biblioteca@localhost:15432/biblioteca` |
| `TEST_DATABASE_URL` | la misma, con la base `biblioteca_test` |
| `DB_PORT` | `15432` (puerto publicado por Docker) |
| `JWT_SECRET` | un valor de desarrollo: **cámbialo**, con al menos 32 bytes |
| `JWT_ALGORITHM` / `JWT_EXPIRES_MINUTES` | `HS256` / `60` |
| `LOAN_DAYS` | `14` |
| `LIBRARIAN_NAME` / `LIBRARIAN_EMAIL` / `LIBRARIAN_PASSWORD` | bibliotecario inicial |

Fuera de alcance: interfaz gráfica y despliegue.
