"""Shared HTTP response guards for GitHub API calls."""
MAX_RESPONSE_BYTES = 50_000_000  # 50 MB hard cap; legitimate GitHub API responses are < 10 MB


def check_content_length(response) -> None:
    """Reject GitHub API responses advertising more than MAX_RESPONSE_BYTES.

    Raises ValueError if Content-Length exceeds the cap. Missing header
    or malformed value is allowed through — chunked / unknown-length
    responses cannot be guarded this way and must be accepted.
    """
    cl = response.headers.get("Content-Length")
    if cl is None:
        return
    try:
        n = int(cl)
    except ValueError:
        return  # malformed header is not our problem to police
    if n > MAX_RESPONSE_BYTES:
        raise ValueError(
            f"GitHub API response Content-Length={n} exceeds cap {MAX_RESPONSE_BYTES}"
        )
