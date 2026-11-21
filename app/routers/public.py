from fastapi import APIRouter, Depends, HTTPException, Request
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


TAG_GROUPS = (
    ("Area of impact", "area_of_impact"),
    ("Category", "category"),
    ("Technology", "technology"),
    ("Sport focus", "sport_focus"),
    ("Market", "market"),
)


@router.get("/organizations/{organization_id}")
def organization_page(
    request: Request, organization_id: int, session: Session = Depends(get_session)
):
    organization = session.get(Organization, organization_id)
    if organization is None or not organization.is_published:
        raise HTTPException(status_code=404, detail="Organization not found")
    tag_groups = [
        (label, [tag.name for tag in organization.tags_in(vocabulary)])
        for label, vocabulary in TAG_GROUPS
        if organization.tags_in(vocabulary)
    ]
    events = [event for event in organization.events if event.is_published]
    return templates.TemplateResponse(
        request,
        "public/organization.html",
        {"organization": organization, "tag_groups": tag_groups, "events": events},
    )
