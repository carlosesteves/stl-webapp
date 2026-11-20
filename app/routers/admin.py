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
from app.models import Item
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
def item_list(
    request: Request,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    items = session.scalars(select(Item).order_by(Item.name)).all()
    return templates.TemplateResponse(request, "admin/items.html", {"items": items})


@router.get("/items/new")
def new_item_form(request: Request, _: dict = Depends(require_admin)):
    return templates.TemplateResponse(
        request, "admin/item_form.html", {"item": None, "action": "/admin/items"}
    )


@router.post("/items")
def create_item(
    name: str = Form(),
    description: str = Form(""),
    published: bool = Form(False),
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    session.add(Item(name=name, description=description, published=published))
    session.commit()
    return RedirectResponse("/admin", status_code=303)


def get_item_or_404(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/items/{item_id}/edit")
def edit_item_form(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    item = get_item_or_404(session, item_id)
    return templates.TemplateResponse(
        request,
        "admin/item_form.html",
        {"item": item, "action": f"/admin/items/{item.id}"},
    )


@router.post("/items/{item_id}")
def update_item(
    item_id: int,
    name: str = Form(),
    description: str = Form(""),
    published: bool = Form(False),
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    item = get_item_or_404(session, item_id)
    item.name, item.description, item.published = name, description, published
    session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/items/{item_id}/delete")
def delete_item(
    item_id: int,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    session.delete(get_item_or_404(session, item_id))
    session.commit()
    return RedirectResponse("/admin", status_code=303)
