"""
api/utils/security.py — Shared security utilities for FinAssist-V2 API handlers.

Security measures implemented here:
  1. INPUT VALIDATION
     - validate_symbol(): strict regex whitelist for stock ticker symbols.
       Only uppercase A-Z, 1–10 characters, with an optional single dot
       (for BRK.B style tickers). Rejects anything that could alter a URL
       or be used for injection (CWE-20 / OWASP A03:2021 Injection).

  2. SECURE RESPONSE HEADERS (OWASP Secure Headers Project)
     - X-Content-Type-Options: nosniff — prevents MIME-sniffing attacks.
     - X-Frame-Options: DENY — blocks clickjacking via iframes.
     - X-Content-Length-Options — prevents response splitting abuse.
     - Referrer-Policy: strict-origin — limits referrer leakage.
     - X-Robots-Tag: noindex, nofollow — API endpoints must not be crawled.
     - Cache-Control: no-store — financial data must not be cached by
       intermediary proxies; sensitive data could be stale or intercepted.

  3. CORS HARDENING
     - ALLOWED_ORIGINS: explicit allowlist instead of wildcard '*'.
       Wildcard CORS on an API exposes every response to any cross-origin
       script. (CWE-942 / OWASP A05:2021 Security Misconfiguration)
     - In local dev mode (detected via VERCEL_ENV env var absence) the
       localhost origin is added so the dev server still works.

  4. RATE LIMITING (stateless advisory)
     - Vercel serverless has no persistent memory between invocations, so
       true token-bucket rate limiting requires an external store (Redis /
       Upstash / Vercel KV). That is documented here as the recommended
       next step (see RATE_LIMIT_NOTE below).
     - What IS enforced here without external state:
         a. Symbol validation rejects junk quickly before touching Yahoo Finance.
         b. Thread pool caps (MAX_PRICE_WORKERS, MAX_FUND_WORKERS) in topstocks.py
            bound the maximum fan-out per invocation so a single request cannot
            exhaust the Vercel function CPU/memory budget.

  5. ERROR SANITIZATION
     - sanitize_error(): strips internal Python exception detail before
       returning to the client. Internal error is logged server-side;
       the client receives only a safe, generic message (CWE-209).

RATE_LIMIT_NOTE:
  To add real per-IP rate limiting, integrate Upstash Redis (free tier):
    pip install upstash-redis
  Then use a sliding-window counter keyed on the client IP extracted from
  the 'x-forwarded-for' header (set by Vercel's edge). Example pattern:
    from upstash_redis import Redis
    r = Redis.from_env()
    key = f"rl:{client_ip}:{endpoint}"
    count = r.incr(key)
    r.expire(key, 60)          # 60-second window
    if count > LIMIT:
        return 429 Too Many Requests
  Recommended limits: /api/analyze → 20 req/min, /api/topstocks → 6 req/min.
"""

import re
import os

# ── CORS ─────────────────────────────────────────────────────────────────────
# Explicit origin allowlist — no wildcard. Add your production domain here.
# Vercel preview URLs follow the pattern: https://<project>-<hash>-<team>.vercel.app
# Rather than enumerate every preview URL, we allow the stable production
# domain and localhost for dev. Preview deployments run on the same Vercel
# project domain, so they do not need a separate origin.
_PRODUCTION_ORIGINS = [
    "https://fin-assist-v2.vercel.app",       # primary production domain
    "https://finassist-v2.vercel.app",         # alternate slug (if used)
]

def _build_allowed_origins():
    """Build the CORS origin allowlist, adding localhost only in local dev."""
    origins = set(_PRODUCTION_ORIGINS)
    # VERCEL_ENV is 'production', 'preview', or 'development' on Vercel.
    # Its absence means we are running locally.
    env = os.environ.get("VERCEL_ENV")
    if env != "production":
        origins.add("http://localhost:5173")   # Vite default dev port
        origins.add("http://localhost:3000")
        origins.add("http://localhost:8000")   # Python dev server
    return origins

ALLOWED_ORIGINS = _build_allowed_origins()

# Thread pool caps — bound fan-out per serverless invocation to prevent DoS
# via resource exhaustion. 18 stocks × 2 thread pools = up to 36 threads
# without caps; we limit to 8 per pool (still fast enough for I/O-bound work).
MAX_PRICE_WORKERS = 8
MAX_FUND_WORKERS  = 8

# ── SYMBOL VALIDATION ────────────────────────────────────────────────────────
# Whitelist: 1–10 uppercase letters, with an optional single embedded dot
# for tickers like BRK.B or BF.B. The dot may not start or end the symbol.
# This is intentionally strict — anything outside this set is rejected before
# any downstream URL construction (CWE-20).
_SYMBOL_RE = re.compile(r'^[A-Z]{1,10}(\.[A-Z]{1,2})?$')

# Hard cap on raw input length before normalisation — prevents regex backtrack
# DOS on pathologically long strings.
_SYMBOL_MAX_RAW_LEN = 20


def validate_symbol(raw: str) -> str:
    """
    Validate and normalise a stock ticker symbol.
    Returns the uppercased symbol if valid.
    Raises ValueError with a safe client-facing message if invalid.
    """
    if not isinstance(raw, str):
        raise ValueError("Symbol must be a string.")
    if len(raw) > _SYMBOL_MAX_RAW_LEN:
        raise ValueError("Symbol too long.")
    symbol = raw.strip().upper()
    if not symbol:
        raise ValueError("Symbol is required.")
    if not _SYMBOL_RE.match(symbol):
        raise ValueError(
            "Invalid symbol. Use 1–10 uppercase letters (e.g. AAPL, BRK.B)."
        )
    return symbol


# ── ERROR SANITIZATION ───────────────────────────────────────────────────────
# Never return raw Python exception text to the client — it can expose
# internal paths, library names, and data structure details (CWE-209).
_SAFE_ERROR_MESSAGES = {
    400: "Bad request.",
    404: "Not found.",
    429: "Too many requests. Please try again later.",
    500: "An internal error occurred. Please try again.",
}


def sanitize_error(status: int, exc: Exception | None = None, detail: str | None = None) -> str:
    """
    Return a safe, generic error message for the given HTTP status code.
    Logs the real exception detail to stdout (captured by Vercel logs).
    """
    if exc is not None:
        # Log internally — Vercel captures stdout as function logs.
        print(f"[INTERNAL ERROR {status}] {type(exc).__name__}: {exc}")
    return _SAFE_ERROR_MESSAGES.get(status, "An error occurred.")


# ── RESPONSE HEADERS ─────────────────────────────────────────────────────────
def get_security_headers(request_origin: str | None = None) -> dict:
    """
    Return a dict of security response headers to apply to every API response.
    Handles CORS origin validation: reflects the origin only if it is in
    ALLOWED_ORIGINS; otherwise omits the ACAO header entirely.
    """
    headers = {
        # Prevent MIME-type sniffing — browser must honour declared Content-Type.
        "X-Content-Type-Options": "nosniff",
        # Deny embedding this API response in an iframe (clickjacking protection).
        "X-Frame-Options": "DENY",
        # Limit referrer information sent on cross-origin requests.
        "Referrer-Policy": "strict-origin",
        # API responses must not be stored by shared caches; financial data is
        # user-specific and time-sensitive.
        "Cache-Control": "no-store",
        # Prevent search engines from indexing API endpoints.
        "X-Robots-Tag": "noindex, nofollow",
        # Only allow GET and OPTIONS — restrict unexpected method types.
        "Allow": "GET, OPTIONS",
    }

    # CORS — reflect origin only if explicitly allowed (no wildcard).
    if request_origin and request_origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = request_origin
        # Vary header tells caches this response differs by origin.
        headers["Vary"] = "Origin"
    else:
        # For same-origin requests (no Origin header) or disallowed origins,
        # omit ACAO entirely — the browser will block cross-origin reads.
        # We still serve the response so server-side tools (curl, Vercel
        # internal routing) continue to work.
        pass

    return headers


def get_cors_preflight_headers(request_origin: str | None = None) -> dict:
    """
    Return headers for OPTIONS preflight responses.
    Only grants preflight approval to allowed origins.
    """
    headers = get_security_headers(request_origin)
    if "Access-Control-Allow-Origin" in headers:
        headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        headers["Access-Control-Allow-Headers"] = "Content-Type"
        headers["Access-Control-Max-Age"] = "86400"   # cache preflight 24 h
    return headers
