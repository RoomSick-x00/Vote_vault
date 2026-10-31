"""Voter roster + OTP + voter-session services.

Voters are uploaded by the organizer and are NOT Supabase accounts. Identity:
the election's `voterSchema.identityColumns` (name and/or rollNo) matched
against the roster; proof: a 6-digit OTP delivered to the roster's contact for
the election's `otpChannels` (dev mode returns the code in the response —
documented honestly; production needs a real sender). On verify, the voter
gets a short-lived backend-issued session token (scope "voter") that only
voting endpoints accept.

The roster is private organizer data. `has_voted` is never stored — it derives
from the ballots table.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import re
import secrets
import uuid
from zipfile import BadZipFile
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.base import utcnow
from app.errors import ApiError
from app.models import Election, Voter, VoterOtpChallenge

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
CANONICAL_ORDER = ["name", "rollNo", "email", "phone"]
OTP_TTL_SECONDS = 600
OTP_RESEND_AFTER_SECONDS = 30
OTP_MAX_ATTEMPTS = 5
IDENTIFY_TOKEN_TTL_SECONDS = 600
VOTER_SESSION_TTL_SECONDS = 2 * 3600

COLUMN_ALIASES = {
    "name": ("name", "full name", "fullname", "student name", "voter name", "candidate name"),
    "rollNo": (
        "rollno", "roll no", "roll number", "roll", "rollno.",
        "admin no", "adminno", "admin number", "admin", "adm no", "admno",
        "reg no", "regno", "registration no", "registration number", "usn", "student id", "id no",
    ),
    "email": ("email", "email address", "mail", "gmail", "gmail id", "email id", "e-mail", "e mail", "college email"),
    "phone": ("phone", "phone number", "mobile", "mobile number", "contact", "contact no", "whatsapp", "phone no", "phone.", "tel", "tel no"),
}


def generate_election_code(existing: set[str]) -> str:
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    while code in existing:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return code


def validate_voter_schema(schema: dict) -> dict:
    if not isinstance(schema, dict):
        raise ApiError(422, "VALIDATION_ERROR", "voter_schema must be an object.")
    identity = schema.get("identityColumns")
    channels = schema.get("otpChannels")
    if not identity or not all(c in ("name", "rollNo") for c in identity):
        raise ApiError(422, "VALIDATION_ERROR", "voter_schema.identityColumns must be non-empty 'name'/'rollNo'.")
    if not channels or not all(c in ("email", "phone") for c in channels):
        raise ApiError(422, "VALIDATION_ERROR", "voter_schema.otpChannels must be non-empty 'email'/'phone'.")
    return {"identityColumns": list(dict.fromkeys(identity)), "otpChannels": list(dict.fromkeys(channels))}


def normalize_header(header: str) -> str | None:
    key = (header or "").strip().lower()
    for canonical, aliases in COLUMN_ALIASES.items():
        if key in aliases:
            return canonical
    return None


def _headers(values) -> list[str | None]:
    headers = [normalize_header(str(value)) if value is not None else None for value in values]
    known = [value for value in headers if value]
    if not known:
        raise ApiError(422, "INVALID_FILE", "No recognized columns. Use headers such as name, rollNo, email, phone.")
    if len(known) != len(set(known)):
        raise ApiError(422, "INVALID_FILE", "The file contains duplicate columns for the same field.")
    return headers


def parse_roster_file(filename: str, content: bytes) -> list[dict[str, str]]:
    """Parse CSV or XLSX into row dicts keyed by canonical column names."""
    lowered = (filename or "").lower()
    if lowered.endswith(".xls"):
        raise ApiError(422, "INVALID_FILE", "Legacy .xls is not supported. Save the file as .xlsx or CSV.")
    if lowered.endswith(".xlsx"):
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover
            raise ApiError(422, "INVALID_FILE", "XLSX support requires the openpyxl package.") from exc
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
            workbook.close()
        except (BadZipFile, ValueError, KeyError, OSError) as exc:
            raise ApiError(422, "INVALID_FILE", "Could not read this Excel file. Upload a valid .xlsx file.") from exc
        if not rows:
            return []
        headers = _headers(rows[0])
        return [
            {**{canon: ("" if cell is None else str(cell).strip())
             for canon, cell in zip(headers, row) if canon}, "__row__": index}
            for index, row in enumerate(rows[1:], start=2)
            if any(cell is not None and str(cell).strip() for cell in row)
        ]

    if not lowered.endswith(".csv"):
        raise ApiError(422, "INVALID_FILE", "Upload a CSV or .xlsx file.")
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    parsed: list[dict[str, str]] = []
    raw_rows = [(reader.line_num, row) for row in reader if any(cell.strip() for cell in row)]
    if not raw_rows:
        return []
    headers = _headers(raw_rows[0][1])
    for index, row in raw_rows[1:]:
        entry = {canon: cell.strip() for canon, cell in zip(headers, row) if canon}
        if entry:
            entry["__row__"] = index
            parsed.append(entry)
    return parsed


def import_roster(db: Session, election: Election, filename: str, content: bytes) -> dict:
    schema = election.voter_schema or {}
    required = set(schema.get("identityColumns", [])) | {
        {"email": "email", "phone": "phone"}[c] for c in schema.get("otpChannels", [])
    }
    try:
        rows = parse_roster_file(filename, content)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ApiError(422, "INVALID_FILE", f"Could not parse the file: {exc}") from exc
    if not rows:
        raise ApiError(422, "INVALID_FILE", "The file contains no data rows.")

    errors: list[dict] = []
    valid: list[tuple[int, dict]] = []
    for fallback_index, row in enumerate(rows, start=2):
        index = row.pop("__row__", fallback_index)
        missing = [col for col in required if not row.get(col)]
        if missing:
            errors.append({"row": index, "message": f"missing required column(s): {', '.join(missing)}"})
            continue
        if not (row.get("name") or row.get("rollNo")) or not (row.get("email") or row.get("phone")):
            errors.append({"row": index, "message": "each voter needs a name or roll number and an email or phone number"})
            continue
        if row.get("email"):
            try:
                row["email"] = validate_email(row["email"], check_deliverability=False).normalized
            except EmailNotValidError:
                errors.append({"row": index, "message": "invalid email address"})
                continue
        valid.append((index, row))

    existing_rollnos = set(
        db.scalars(select(Voter.roll_no).where(Voter.election_id == election.id, Voter.roll_no.is_not(None)))
    )
    existing_emails = set(
        db.scalars(select(Voter.email).where(Voter.election_id == election.id, Voter.email.is_not(None)))
    )
    existing_phones = {re.sub(r"[\s()\-]", "", value) for value in db.scalars(
        select(Voter.phone).where(Voter.election_id == election.id, Voter.phone.is_not(None))
    )}

    imported = 0
    for index, row in valid:
        roll_no = row.get("rollNo") or None
        email = (row.get("email") or None)
        phone = re.sub(r"[\s()\-]", "", row.get("phone") or "") or None
        if roll_no and roll_no.lower() in {r.lower() for r in existing_rollnos}:
            errors.append({"row": index, "message": "duplicate roll number already in the roster"})
            continue
        if email and email.lower() in {e.lower() for e in existing_emails}:
            errors.append({"row": index, "message": "duplicate email already in the roster"})
            continue
        if phone and phone in existing_phones:
            errors.append({"row": index, "message": "duplicate phone number already in the voter file"})
            continue
        db.add(
            Voter(
                election_id=election.id,
                name=row.get("name") or None,
                roll_no=roll_no,
                email=email,
                phone=phone,
            )
        )
        imported += 1
        if roll_no:
            existing_rollnos.add(roll_no)
        if email:
            existing_emails.add(email)
        if phone:
            existing_phones.add(phone)

    db.commit()
    detected = sorted({canon for row in rows for canon in row}, key=CANONICAL_ORDER.index)
    return {
        "imported": imported,
        "skipped": len(rows) - imported,
        "errors": errors,
        "columns": detected,
    }


def voter_record(voter: Voter, db: Session) -> dict:
    from sqlalchemy import exists as sa_exists

    from app.models import Ballot

    has_voted = db.scalar(
        select(
            sa_exists().where(
                Ballot.election_id == voter.election_id,
                Ballot.voter_id == voter.id,
                Ballot.accepted.is_(True),
            )
        )
    )
    return {
        "id": str(voter.id),
        "name": voter.name,
        "rollNo": voter.roll_no,
        "email": voter.email,
        "phone": voter.phone,
        "hasVoted": bool(has_voted),
        "addedAt": voter.created_at.isoformat(timespec="seconds") + "Z",
    }


def check_voting_window(election: Election) -> None:
    """Polling-place window: opens_at/closes_at bound voter acceptance while open."""
    now = utcnow()
    if election.opens_at is not None and now < election.opens_at:
        raise ApiError(409, "ELECTION_NOT_OPEN", "The voting window has not opened yet.")
    if election.closes_at is not None and now > election.closes_at:
        raise ApiError(409, "ELECTION_CLOSED", "The voting window has closed.")


def match_voter(db: Session, election: Election, identity: dict) -> Voter:
    """Match the typed identity columns against the roster (exact, case-insensitive)."""
    columns = (election.voter_schema or {}).get("identityColumns", [])
    stmt = select(Voter).where(Voter.election_id == election.id)
    for column in columns:
        value = (identity.get(column) or "").strip()
        if not value:
            raise ApiError(422, "VALIDATION_ERROR", f"Identity column '{column}' is required.")
        attribute = Voter.name if column == "name" else Voter.roll_no
        stmt = stmt.where(func_lower(attribute) == value.lower())
    matches = list(db.scalars(stmt))
    if not matches:
        raise ApiError(404, "VOTER_NOT_FOUND", "No roster entry matches these details.")
    if len(matches) > 1:
        raise ApiError(409, "AMBIGUOUS_IDENTITY", "Multiple voters match; include the roll number.")
    return matches[0]


def func_lower(column):
    from sqlalchemy import func

    return func.lower(column)


def mask_contact(contact: str, channel: str) -> str:
    if channel == "email":
        local, _, domain = contact.partition("@")
        if not domain:
            return contact
        shown = local[:2] if len(local) > 2 else local
        return f"{shown}•••@{domain}"
    return f"••••{contact[-4:]}" if len(contact) > 4 else contact


# --- tokens -----------------------------------------------------------------


def _mint(secret: str, claims: dict, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {**claims, "iat": now, "exp": now + timedelta(seconds=ttl_seconds), "jti": secrets.token_hex(16)}
    return pyjwt.encode(payload, secret, algorithm="HS256")


def mint_identify_token(settings: Settings, election: Election, voter: Voter) -> str:
    return _mint(
        _voter_secret(settings),
        {"scope": "identify", "vtr": str(voter.id), "elc": str(election.id)},
        IDENTIFY_TOKEN_TTL_SECONDS,
    )


def mint_voter_session(settings: Settings, election: Election, voter: Voter) -> str:
    return _mint(
        _voter_secret(settings),
        {"scope": "voter", "vtr": str(voter.id), "elc": str(election.id)},
        VOTER_SESSION_TTL_SECONDS,
    )


def decode_scoped_token(settings: Settings, token: str, expected_scope: str) -> dict:
    try:
        claims = pyjwt.decode(
            token, _voter_secret(settings), algorithms=["HS256"], options={"require": ["exp", "jti"]}
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise ApiError(401, "UNAUTHENTICATED", "Session expired; identify again.") from exc
    except pyjwt.PyJWTError as exc:
        raise ApiError(401, "UNAUTHENTICATED", f"Invalid session token: {exc}") from exc
    if claims.get("scope") != expected_scope:
        raise ApiError(401, "UNAUTHENTICATED", "Wrong token type for this endpoint.")
    return claims


def _voter_secret(settings: Settings) -> str:
    secret = settings.voter_session_secret or settings.supabase_jwt_secret
    if not secret:
        raise ApiError(
            503,
            "VOTER_AUTH_NOT_CONFIGURED",
            "Voter sessions need SUPABASE_JWT_SECRET or VOTER_SESSION_SECRET configured.",
        )
    return secret


# --- OTP --------------------------------------------------------------------


def _hash_code(code: str, secret: str) -> str:
    return hmac.new(secret.encode(), code.encode(), hashlib.sha256).hexdigest()


def create_otp_challenge(
    db: Session, settings: Settings, election: Election, voter: Voter, identify_jti: str, channel: str, contact: str
) -> tuple[VoterOtpChallenge, str | None]:
    roster_contact = voter.email if channel == "email" else voter.phone
    normalize = (lambda value: re.sub(r"[\s()\-]", "", value)) if channel == "phone" else (lambda value: value.strip().lower())
    if not roster_contact or normalize(roster_contact) != normalize(contact):
        raise ApiError(403, "CONTACT_MISMATCH", f"This {channel} is not on the roster for your entry.")
    if election.status != "open":
        raise ApiError(409, "ELECTION_NOT_OPEN", "This election is not accepting voters.")
    check_voting_window(election)
    # Serialize requests for the same voter on databases that support row locks.
    db.execute(select(Voter.id).where(Voter.id == voter.id).with_for_update()).first()

    recent = db.scalars(
        select(VoterOtpChallenge)
        .where(
            VoterOtpChallenge.voter_id == voter.id,
        )
        .order_by(VoterOtpChallenge.expires_at.desc())
    ).first()
    if recent is not None and recent.consumed_at is None:
        elapsed = (utcnow() - recent.created_at).total_seconds()
        if elapsed < OTP_RESEND_AFTER_SECONDS:
            raise ApiError(429, "OTP_RESEND_TOO_SOON", f"Wait {OTP_RESEND_AFTER_SECONDS - int(elapsed)}s before requesting again.")

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    challenge = VoterOtpChallenge(
        election_id=election.id,
        voter_id=voter.id,
        identify_jti=identify_jti,
        channel=channel,
        contact=roster_contact,
        code_hash=_hash_code(code, _voter_secret(settings)),
        attempts=0,
        expires_at=utcnow() + timedelta(seconds=OTP_TTL_SECONDS),
    )
    db.add(challenge)
    # A provider failure must not leave an unusable challenge or start a resend cooldown.
    from app.services.otp_delivery import deliver_otp
    try:
        db.flush()
        dev_code, provider_marker = deliver_otp(settings, channel, normalize(roster_contact), code)
        if provider_marker:
            challenge.code_hash = provider_marker
        previous = db.scalars(select(VoterOtpChallenge).where(
            VoterOtpChallenge.voter_id == voter.id,
            VoterOtpChallenge.id != challenge.id,
            VoterOtpChallenge.consumed_at.is_(None),
        )).all()
        for old in previous:
            old.consumed_at = utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return challenge, dev_code


def consume_otp(db: Session, settings: Settings, identify_claims: dict, otp: str) -> tuple[Voter, Election]:
    election = db.get(Election, uuid.UUID(identify_claims["elc"]))
    voter = db.get(Voter, uuid.UUID(identify_claims["vtr"]))
    if election is None or voter is None or voter.election_id != election.id:
        raise ApiError(404, "NOT_FOUND", "Identify session is no longer valid.")
    if election.status != "open":
        raise ApiError(409, "ELECTION_NOT_OPEN", "This election is not accepting ballots.")
    check_voting_window(election)

    challenge = db.scalars(
        select(VoterOtpChallenge)
        .where(
            VoterOtpChallenge.voter_id == voter.id,
            VoterOtpChallenge.identify_jti == identify_claims["jti"],
            VoterOtpChallenge.consumed_at.is_(None),
        )
        .order_by(VoterOtpChallenge.expires_at.desc())
    ).first()
    if challenge is None:
        raise ApiError(404, "OTP_NOT_FOUND", "Request an OTP first.")
    if challenge.expires_at < utcnow():
        raise ApiError(410, "OTP_EXPIRED", "The code expired; request a new one.")
    if challenge.attempts >= OTP_MAX_ATTEMPTS:
        raise ApiError(429, "OTP_TOO_MANY_ATTEMPTS", "Too many wrong codes; request a new one.")

    challenge.attempts += 1
    if challenge.code_hash.startswith("tv:"):
        from app.services.otp_delivery import check_twilio_verify
        db.commit()  # Count attempts even if the provider is unavailable.
        valid = check_twilio_verify(settings, challenge.code_hash, otp.strip())
    else:
        valid = hmac.compare_digest(challenge.code_hash, _hash_code(otp.strip(), _voter_secret(settings)))
    if not valid:
        db.commit()
        raise ApiError(401, "OTP_INVALID", "Wrong code.")
    challenge.consumed_at = utcnow()
    db.commit()
    return voter, election


def voter_session_info(db: Session, election: Election, voter: Voter) -> dict:
    from app.models import Ballot, Candidate

    ballot = db.scalars(
        select(Ballot).where(
            Ballot.election_id == election.id, Ballot.voter_id == voter.id, Ballot.accepted.is_(True)
        )
    ).first()
    candidates = db.scalars(select(Candidate).where(Candidate.election_id == election.id).order_by(Candidate.chain_index))
    return {
        "election": public_election(election),
        "candidates": [
            {"id": str(c.id), "name": c.name, "description": c.description} for c in candidates
        ],
        "voterName": voter.name or voter.roll_no or "Voter",
        "hasVoted": ballot is not None,
        "receiptId": str(ballot.id) if ballot else None,
    }


def public_election(election: Election) -> dict:
    return {
        "id": str(election.id),
        "code": election.code,
        "title": election.title,
        "description": election.description,
        "status": election.status,
        "voterSchema": election.voter_schema,
    }
