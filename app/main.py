from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers import admin, admin_events, public
from app.templating import BASE_DIR


def create_app() -> FastAPI:
    app = FastAPI(title="stl-webapp")
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    app.include_router(public.router)
    app.include_router(admin.router)
    app.include_router(admin_events.router)

    @app.exception_handler(HTTPException)
    async def redirect_unauthenticated_admin(request: Request, exc: HTTPException):
        if exc.status_code == 401 and request.url.path.startswith("/admin"):
            return RedirectResponse("/admin/login", status_code=303)
        return await http_exception_handler(request, exc)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
