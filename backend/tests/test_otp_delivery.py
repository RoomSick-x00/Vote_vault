"""Provider boundary and API flow tests; no real messages are sent."""
from io import BytesIO
from openpyxl import Workbook
from helpers import build_open_election


def identify(client, setup):
    response = client.post(f"/api/v1/vote/{setup['code']}/identify", json={"rollNo": "R001"})
    assert response.status_code == 200
    return response.json()["identifyToken"]


def test_smtp_sends_and_never_returns_the_code(client, app, monkeypatch):
    from app.services import otp_delivery
    sent = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self, **kwargs): pass
        def login(self, user, password): pass
        def send_message(self, message): sent.append(message)
    monkeypatch.setattr(otp_delivery.smtplib, "SMTP", SMTP)
    settings = app.state.settings
    settings.otp_email_provider = "smtp"; settings.smtp_host = "smtp.example.com"
    settings.smtp_from = "vote@example.com"
    setup = build_open_election(client)
    token = identify(client, setup)
    response = client.post("/api/v1/vote/otp/request", json={"identifyToken": token, "channel": "email", "contact": "r001@campus.edu"})
    assert response.status_code == 200 and response.json()["devCode"] is None
    assert len(sent) == 1 and sent[0]["To"] == "r001@campus.edu"
    import re
    code = re.search(r"\b\d{6}\b", sent[0].get_content()).group()
    verified = client.post("/api/v1/vote/otp/verify", json={"identifyToken": token, "otp": code})
    assert verified.status_code == 200


def test_delivery_failure_can_be_retried_without_cooldown(client, app, monkeypatch):
    from app.services import otp_delivery
    class BrokenSMTP:
        def __init__(self, *args, **kwargs): raise OSError("offline")
    monkeypatch.setattr(otp_delivery.smtplib, "SMTP", BrokenSMTP)
    settings = app.state.settings
    settings.otp_email_provider = "smtp"; settings.smtp_host = "smtp.example.com"; settings.smtp_from = "vote@example.com"
    setup = build_open_election(client); token = identify(client, setup)
    payload = {"identifyToken": token, "channel": "email", "contact": "r001@campus.edu"}
    response = client.post("/api/v1/vote/otp/request", json=payload)
    assert response.status_code == 502 and response.json()["error"]["code"] == "OTP_DELIVERY_FAILED"
    settings.otp_email_provider = "development"
    assert client.post("/api/v1/vote/otp/request", json=payload).status_code == 200


def test_twilio_verify_flow_uses_provider_code(client, app, monkeypatch):
    from app.services import otp_delivery
    from helpers import auth, ORGANIZER
    calls = []
    class Response:
        def __init__(self, result): self.result = result
        def raise_for_status(self): pass
        def json(self): return self.result
    def post(url, **kwargs):
        calls.append((url, kwargs["data"]))
        return Response({"sid": "VE" + "a" * 32} if url.endswith("/Verifications") else {"status": "approved" if kwargs["data"]["Code"] == "123456" else "pending"})
    monkeypatch.setattr(otp_delivery.httpx, "post", post)
    settings = app.state.settings
    settings.otp_phone_provider = "twilio_verify"; settings.twilio_account_sid = "AC" + "a" * 32
    settings.twilio_auth_token = "test"; settings.twilio_verify_service_sid = "VA" + "b" * 32
    setup = build_open_election_with_phone(client)
    token = identify(client, setup)
    response = client.post("/api/v1/vote/otp/request", json={"identifyToken": token, "channel": "phone", "contact": "+91 98765 43210"})
    assert response.status_code == 200 and response.json()["devCode"] is None
    assert calls[0][1]["To"] == "+919876543210"
    wrong = client.post("/api/v1/vote/otp/verify", json={"identifyToken": token, "otp": "000000"})
    assert wrong.status_code == 401
    good = client.post("/api/v1/vote/otp/verify", json={"identifyToken": token, "otp": "123456"})
    assert good.status_code == 200 and calls[-1][1]["VerificationSid"] == "VE" + "a" * 32


def build_open_election_with_phone(client):
    from helpers import build_ready_election, open_election, auth, ORGANIZER
    rows = [{"name": "One", "rollNo": "R001", "email": "r001@campus.edu", "phone": "+919876543210"}]
    setup = build_ready_election(client, roster_rows=rows)
    response = client.put(f"/api/v1/elections/{setup['election_id']}/voter-schema", json={"identityColumns": ["rollNo"], "otpChannels": ["phone"]}, headers=auth(ORGANIZER))
    assert response.status_code == 200
    open_election(client, setup['election_id'])
    return setup


def test_excel_import_and_bad_file(client):
    from helpers import create_organization, create_election, auth, ORGANIZER
    election = create_election(client, create_organization(client)["organization_id"])
    url = f"/api/v1/elections/{election['election_id']}/voters/upload"
    wb = Workbook(); ws = wb.active
    ws.append(["name", "rollNo", "email", "phone"])
    ws.append(["Test Voter", "A01", "voter@example.com", "+919876543210"])
    out = BytesIO(); wb.save(out)
    response = client.post(url, files={"file": ("voters.xlsx", out.getvalue())}, headers=auth(ORGANIZER))
    assert response.status_code == 200 and response.json()["imported"] == 1
    bad = client.post(url, files={"file": ("voters.xlsx", b"not a workbook")}, headers=auth(ORGANIZER))
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_FILE"
    legacy = client.post(url, files={"file": ("voters.xls", b"invalid")}, headers=auth(ORGANIZER))
    assert legacy.status_code == 422


def test_development_provider_fails_closed_in_production(client, app):
    settings = app.state.settings
    settings.app_env = "production"
    setup = build_open_election(client); token = identify(client, setup)
    response = client.post("/api/v1/vote/otp/request", json={"identifyToken": token, "channel": "email", "contact": "r001@campus.edu"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "OTP_DELIVERY_NOT_CONFIGURED"


def test_import_reports_invalid_and_duplicate_contacts(client):
    from helpers import create_organization, create_election, auth, ORGANIZER
    election = create_election(client, create_organization(client)["organization_id"])
    content = ("name,rollNo,email,phone\n"
               "One,A01,one@example.com,+919876543210\n"
               "\nTwo,A02,broken-email,+919876543211\n"
               "Three,A03,three@example.com,+91 98765 43210\n")
    url = f"/api/v1/elections/{election['election_id']}/voters/upload"
    response = client.post(url, files={"file": ("voters.csv", content.encode())}, headers=auth(ORGANIZER))
    assert response.status_code == 200
    report = response.json()
    assert report["imported"] == 1 and report["skipped"] == 2
    assert [error["row"] for error in report["errors"]] == [4, 5]
