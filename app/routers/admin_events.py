from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_session
from app.event_form import EventFormData, apply_event_form
from app.models import OrganizationEvent, Term
from app.routers.admin import get_organization_or_404
from app.templating import templates

router = APIRouter(prefix="/admin")


def read_event_form(
    event_type_id: str = Form(""),
    year: str = Form(""),
    month: str = Form(""),
    day: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    old_value: str = Form(""),
    new_value: str = Form(""),
    related_name: str = Form(""),
    source_url: str = Form(""),
    is_published: bool = Form(False),
    funding_stage_id: str = Form(""),
    amount: str = Form(""),
    investors: str = Form(""),
) -> EventFormData:
    return EventFormData(
        event_type_id, year, month, day, title, description, old_value, new_value,
        related_name, source_url, is_published, funding_stage_id, amount, investors,
    )


def get_event_or_404(session: Session, event_id: int) -> OrganizationEvent:
    event = session.get(OrganizationEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def terms_in(session: Session, vocabulary: str) -> list[Term]:
    return list(
        session.scalars(
            select(Term).where(Term.vocabulary == vocabulary).order_by(Term.sort_order, Term.name)
        )
    )


def render_form(request, session, organization, event, form, action, errors=(), status_code=200):
    return templates.TemplateResponse(
        request,
        "admin/event_form.html",
        {
            "organization": organization,
            "event": event,
            "form": form,
            "errors": list(errors),
            "action": action,
            "event_types": terms_in(session, "event_type"),
            "funding_stages": terms_in(session, "funding_stage"),
        },
        status_code=status_code,
    )


def back_to(organization_id: int) -> RedirectResponse:
    return RedirectResponse(f"/admin/organizations/{organization_id}", status_code=303)


@router.get("/organizations/{organization_id}/events/new")
def new_event_form(
    request: Request,
    organization_id: int,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    organization = get_organization_or_404(session, organization_id)
    return render_form(
        request, session, organization, None, EventFormData(),
        f"/admin/organizations/{organization.id}/events",
    )


@router.post("/organizations/{organization_id}/events")
def create_event(
    request: Request,
    organization_id: int,
    form: EventFormData = Depends(read_event_form),
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    organization = get_organization_or_404(session, organization_id)
    event = OrganizationEvent()
    errors = apply_event_form(session, event, form)
    if errors:
        return render_form(
            request, session, organization, None, form,
            f"/admin/organizations/{organization.id}/events", errors, 422,
        )
    event.organization = organization
    session.add(event)
    session.commit()
    return back_to(organization.id)


@router.get("/events/{event_id}/edit")
def edit_event_form(
    request: Request,
    event_id: int,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    event = get_event_or_404(session, event_id)
    return render_form(
        request, session, event.organization, event, EventFormData.from_event(event),
        f"/admin/events/{event.id}",
    )


@router.post("/events/{event_id}")
def update_event(
    request: Request,
    event_id: int,
    form: EventFormData = Depends(read_event_form),
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    event = get_event_or_404(session, event_id)
    organization = event.organization
    errors = apply_event_form(session, event, form)
    if errors:
        return render_form(
            request, session, organization, event, form, f"/admin/events/{event.id}", errors, 422,
        )
    session.commit()
    return back_to(organization.id)


@router.post("/events/{event_id}/delete")
def delete_event(
    event_id: int,
    session: Session = Depends(get_session),
    _: dict = Depends(require_admin),
):
    event = get_event_or_404(session, event_id)
    organization_id = event.organization_id
    session.delete(event)
    session.commit()
    return back_to(organization_id)
