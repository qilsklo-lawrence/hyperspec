"""Identity and isolation primitives for Hyperspec.

Principals
----------
Every browser session acts as exactly one *principal*:

    orcid:<ORCiD>   established only by a valid Crucible-signed /import token
    anon:<uuid4>    minted server-side on first visit; lives in the signed cookie

The principal string is the sole key that selects which datasets a request
may see or touch — it is never accepted from request parameters, only from
the signed session cookie (or, for orcid, the verified import token).

Import tokens
-------------
Crucible Graph Explorer signs {orcid, name, object|signed_url, filename,
crucible_dsid} with the shared HYPERSPEC_SSO_SECRET (itsdangerous, salt
'hyperspec-sso'). Tokens expire after TOKEN_MAX_AGE seconds; a replay only
re-imports the same file into the same user's own namespace.
"""

import re
import uuid

from flask import session
from itsdangerous import BadSignature, URLSafeTimedSerializer

ORCID_RE = re.compile(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$')
TOKEN_MAX_AGE = 120  # seconds


def make_serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt='hyperspec-sso')


def verify_import_token(serializer: URLSafeTimedSerializer, token: str) -> dict:
    """Return the token payload, raising BadSignature/SignatureExpired otherwise.

    The ORCiD is format-validated here because it becomes part of GCS object
    paths — nothing outside this shape ever reaches a storage path.
    """
    payload = serializer.loads(token, max_age=TOKEN_MAX_AGE)
    if not isinstance(payload, dict) or not ORCID_RE.match(payload.get('orcid') or ''):
        raise BadSignature('malformed import token payload')
    return payload


def get_principal() -> str:
    """Current session principal; mints a fresh anonymous one if absent/invalid."""
    p = session.get('principal') or ''
    if p.startswith('anon:') or (p.startswith('orcid:') and ORCID_RE.match(p[6:])):
        return p
    p = 'anon:' + uuid.uuid4().hex
    session['principal'] = p
    session.permanent = True
    return p


def login_orcid(orcid: str, name: str | None = None) -> None:
    """Switch the session to a Crucible-verified ORCiD principal."""
    session['principal'] = f'orcid:{orcid}'
    if name:
        session['display_name'] = name
    # Anonymous registry (if any) belongs to the anon principal, not this user
    session.pop('registry', None)
    session.permanent = True


def is_orcid(principal: str) -> bool:
    return principal.startswith('orcid:')


def orcid_of(principal: str) -> str:
    return principal.split(':', 1)[1]
