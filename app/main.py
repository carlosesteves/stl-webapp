from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import public
from app.templating import BASE_DIR


def create_app() -> FastAPI:
    app = FastAPI(title="stl-webapp")
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    app.include_router(public.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
