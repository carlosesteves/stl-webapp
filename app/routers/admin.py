from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.auth import (
    ACCESS_COOKIE,
    InvalidToken,
    NotAdmin,
    TokenVerifier,
    get_verifier,
    verify_admin,
)
from app.config import Settings, get_settings
from app.supabase import InvalidCredentials, SupabaseAuthClient, get_auth_client
from app.templating import templates

router = APIRouter(prefix="/admin")


def login_error(request: Request, message: str, status_code: int):
    return templates.TemplateResponse(
        request, "admin/login.html", {"error": message}, status_code=status_code
    )


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"error": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    auth_client: SupabaseAuthClient = Depends(get_auth_client),
    verifier: TokenVerifier = Depends(get_verifier),
    settings: Settings = Depends(get_settings),
):
    try:
        result = auth_client.sign_in(email, password)
    except InvalidCredentials:
        return login_error(request, "Invalid email or password", 401)
    try:
        verify_admin(result.access_token, verifier)
    except (InvalidToken, NotAdmin):
        return login_error(request, "This account is not an admin", 403)

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        ACCESS_COOKIE,
        result.access_token,
        max_age=result.expires_in,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(ACCESS_COOKIE)
    return response
