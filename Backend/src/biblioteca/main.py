from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(title="Biblioteca")


app = create_app()
