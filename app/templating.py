from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.formatting import display_domain, format_eur, format_event_date, is_http_url

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["eur"] = format_eur
templates.env.filters["event_date"] = lambda event: format_event_date(
    event.event_date, event.date_precision
)
templates.env.filters["domain"] = display_domain
templates.env.tests["http_url"] = is_http_url
