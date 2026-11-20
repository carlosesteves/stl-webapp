from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Item
from app.templating import templates

router = APIRouter()


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    items = session.scalars(
        select(Item).where(Item.published.is_(True)).order_by(Item.name)
    ).all()
    return templates.TemplateResponse(request, "public/home.html", {"items": items})
