"""Validate the initial managed workload envelope before any target is contacted."""

from urllib.parse import urlsplit

from perfagent.contracts.load_model import LoadModel


def https_origin(value: str) -> str | None:
    try:
        url = urlsplit(value)
        port = url.port
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.netloc.endswith(":")
            or any(char.isspace() or ord(char) < 32 for char in value)
            or "\\" in value
            or "%" in url.netloc
        ):
            return None
    except ValueError:
        return None
    host = url.hostname
    if ":" in host:
        host = f"[{host}]"
    return f"https://{host}" + (f":{port}" if port not in (None, 443) else "")


def admission_checks(
    model: LoadModel,
    metadata: dict,
    origins: list[str],
    *,
    max_vus: int,
    max_seconds: int,
    max_requests_per_second: int,
) -> list[dict]:
    profile = model.load_profile
    origin = https_origin(model.target_base_url)
    approved = {
        value
        for entry in origins
        if (value := https_origin(entry))
        and urlsplit(entry).path in ("", "/")
        and not urlsplit(entry).query
        and not urlsplit(entry).fragment
    }
    exact_rate = profile.target_request_rate
    scheduled = (
        profile.executor == "constant-arrival-rate"
        and len(model.scenarios) == 1
        and exact_rate is not None
        and profile.arrival_rate == exact_rate
    )
    return [
        {
            "name": "Approved origin",
            "ok": bool(origin and origin in approved and not model.insecure_tls),
            "detail": "Approve the project’s HTTPS origin and retain TLS verification.",
        },
        {
            "name": "Frozen script",
            "ok": bool(metadata.get("generated") and not metadata.get("script_edited")),
            "detail": "Managed admission requires a frozen, unedited generated k6 script.",
        },
        {
            "name": "Workload limits",
            "ok": bool(
                scheduled
                and exact_rate <= max_requests_per_second
                and profile.pre_allocated_vus <= max_vus
                and profile.total_seconds + profile.graceful_stop_seconds <= max_seconds
            ),
            "detail": f"One journey at a constant rate up to {max_requests_per_second} req/s, "
            f"{max_vus} VUs, and {max_seconds} s including graceful stop.",
        },
    ]
