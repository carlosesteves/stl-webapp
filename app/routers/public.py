from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Organization
from app.templating import templates

router = APIRouter()


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    organizations = session.scalars(
        select(Organization).where(Organization.is_published.is_(True)).order_by(Organization.name)
    ).all()
    return templates.TemplateResponse(request, "public/home.html", {"organizations": organizations})
