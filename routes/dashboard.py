"""Renders the 12 MAIN + 8 APPENDIX HTML page shells.

Every screen fetches its own data client-side via the JSON API on load
(see static/js/charts.js / optimization.js / simulator.js), so these views
only need to supply navigation context -- not pre-computed chart data.
"""
from flask import Blueprint, redirect, render_template, url_for

import config

dashboard_bp = Blueprint("dashboard", __name__)


def _endpoint_for(slug: str) -> str:
    return slug.replace("-", "_")


def _make_view(screen_def):
    def view():
        return render_template(
            screen_def["template"],
            screen=screen_def,
            main_screens=config.MAIN_SCREENS,
            appendix_screens=config.APPENDIX_SCREENS,
        )
    view.__name__ = f"view_{_endpoint_for(screen_def['slug'])}"
    return view


@dashboard_bp.route("/")
def index():
    return redirect(url_for(f"dashboard.{_endpoint_for(config.MAIN_SCREENS[0]['slug'])}"))


for _screen_def in config.MAIN_SCREENS + config.APPENDIX_SCREENS:
    dashboard_bp.add_url_rule(
        f"/{_screen_def['slug']}",
        endpoint=_endpoint_for(_screen_def["slug"]),
        view_func=_make_view(_screen_def),
    )
