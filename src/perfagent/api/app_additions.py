# =====================================================================
# APPEND THESE to src/perfagent/api/app.py
# (after `app = FastAPI(...)` is constructed and other routers mounted)
# =====================================================================
from fastapi import Response
from perfagent.observability.metrics import render_latest
from perfagent.api.reporting_routes import router as reporting_router

app.include_router(reporting_router)


@app.get("/metrics", tags=["observability"])   # x-access: read
def metrics() -> Response:
    """Prometheus scrape endpoint (deterministic, no AI)."""
    payload, content_type = render_latest()
    return Response(content=payload, media_type=content_type)


# ---------------------------------------------------------------------
# APPEND THESE to src/perfagent/api/docs.py (your x-access registry)
# ---------------------------------------------------------------------
# ROUTE_METADATA.update({
#     "GET /metrics": {"x-access": "read", "x-uses-ai": False,
#                      "summary": "Prometheus metrics scrape"},
#     "GET /reporting/runs": {"x-access": "read", "x-uses-ai": False,
#                             "summary": "Role-scoped run history"},
#     "GET /reporting/trend": {"x-access": "read", "x-uses-ai": False,
#                              "summary": "Metric trend over time"},
#     "GET /reporting/coverage": {"x-access": "read", "x-uses-ai": False,
#                                 "summary": "Flow coverage vs. declared"},
# })
