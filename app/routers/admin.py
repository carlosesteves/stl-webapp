from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    ACCESS_COOKIE,
    InvalidToken,
    NotAdmin,
    TokenVerifier,
    get_verifier,
    require_admin,
    verify_admin,
)
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Organization
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


@router.get("")
def organization_list(
    request: Request,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    organizations = session.scalars(select(Organization).order_by(Organization.name)).all()
    return templates.TemplateResponse(request, "admin/organizations.html", {"organizations": organizations})


@router.get("/organizations/new")
def new_organization_form(request: Request, _: dict = Depends(require_admin)):
    return templates.TemplateResponse(
        request, "admin/organization_form.html", {"organization": None, "action": "/admin/organizations"}
    )


@router.post("/organizations")
def create_organization(
    name: str = Form(),
    description: str = Form(""),
    is_published: bool = Form(False),
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    session.add(Organization(name=name, description=description, is_published=is_published))
    session.commit()
    return RedirectResponse("/admin", status_code=303)


def get_organization_or_404(session: Session, organization_id: int) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


@router.get("/organizations/{organization_id}/edit")
def edit_organization_form(
    request: Request,
    organization_id: int,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    organization = get_organization_or_404(session, organization_id)
    return templates.TemplateResponse(
        request,
        "admin/organization_form.html",
        {"organization": organization, "action": f"/admin/organizations/{organization.id}"},
    )


@router.post("/organizations/{organization_id}")
def update_organization(
    organization_id: int,
    name: str = Form(),
    description: str = Form(""),
    is_published: bool = Form(False),
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    organization = get_organization_or_404(session, organization_id)
    organization.name, organization.description, organization.is_published = name, description, is_published
    session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/organizations/{organization_id}/delete")
def delete_organization(
    organization_id: int,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    session.delete(get_organization_or_404(session, organization_id))
    session.commit()
    return RedirectResponse("/admin", status_code=303)
