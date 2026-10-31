# Test real voter OTP delivery

VoteVault accepts CSV or `.xlsx` voter files. Use header names `name,rollNo,email,phone`; choose name and/or roll number as the identity, and email and/or phone as the verification channel. Phone numbers for Twilio must include the country code, such as `+919876543210`. In Excel, format phone and roll-number columns as text so Excel does not strip a leading `+` or zeros. Save old `.xls` workbooks as `.xlsx`. Import errors are reported by row. Do not commit real voter files.

## Configure email and SMS

Create `backend/.env` locally from `backend/.env.example`; it is gitignored. Configure a fresh database, organizer authentication, chain, and a long random `VOTER_SESSION_SECRET` as described in `JUDGE-DEMO.md`. Do not paste credentials into source files or chat. Set these values in `backend/.env`:

```ini
APP_ENV=development
OTP_EMAIL_PROVIDER=smtp
SMTP_HOST=<your SMTP host>
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=<your SMTP login>
SMTP_PASSWORD=<your SMTP app password or credential>
SMTP_FROM=<verified sender address>

OTP_PHONE_PROVIDER=twilio_verify
TWILIO_ACCOUNT_SID=<Twilio account SID>
TWILIO_AUTH_TOKEN=<Twilio auth token>
TWILIO_VERIFY_SERVICE_SID=<Twilio Verify service SID>
```

For implicit TLS, use `SMTP_SECURITY=ssl` with the SMTP provider's SSL port (commonly 465). SMTP app passwords and verified senders depend on the email provider. Twilio Verify provides the SMS code and checks it; the backend does not return it to the browser. Create a Verify service with six-digit codes and verify the test recipient in the Twilio console. [Twilio's trial documentation](https://www.twilio.com/docs/usage/tutorials/how-to-use-your-free-trial-account) describes trial expiration, quota, verified-recipient and geographic limits. A trial may not support the desired country or number; consult the provider before relying on it. For India, [Twilio's SMS guidelines](https://www.twilio.com/en-us/guidelines/in/sms) describe domestic and international routing rules.

Restart the backend after changing settings. If a provider rejects a request, the page reports an error and the failed challenge is rolled back. A successful provider request means the provider accepted it; it does not prove that the message reached the recipient. Check spam, the SMS account logs, and trial restrictions if it does not arrive. No real provider has been exercised without user-supplied credentials.

`development` is an explicit local provider that displays codes on screen only when `APP_ENV` is `development` or `test`; it fails closed in other environments. Select `smtp` and `twilio_verify` to test real delivery. Existing demo instances must be restarted to pick up configuration and code changes. Never use the synthetic organizer auth adapter outside disposable local testing; use configured Supabase auth for real accounts.

## Check the flow

Start a fresh local chain and deploy, start the backend and frontend as in `JUDGE-DEMO.md`, then create a new election. Upload a file containing only consenting test participants and select the appropriate verification columns. Open voting and use the election link. Each participant enters their matching identity and registered contact, then enters the code actually received. Cast a ballot, wait for its chain receipt, close the election, and inspect the audit records. A new election and database are advisable when resetting the local chain.

This remains an election prototype: the backend stores voter identity alongside ballot choice, and matching commitments do not independently prove tally correctness. Use only consenting test data, not a consequential election.
