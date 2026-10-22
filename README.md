# Biblioteca

API de préstamo de libros con arquitectura hexagonal. El código, las instrucciones
para instalar, levantar y probar, y el diagrama entidad-relación están en
[`Backend/`](Backend/README.md).

```bash
cd Backend
poetry install
poetry run invoke up     # levanta Postgres + API en http://127.0.0.1:8000
poetry run invoke test   # ejecuta las pruebas
```
