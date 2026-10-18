# AI project email

Use **Email** in a repository workspace to enter one recipient address and,
optionally, a purpose such as “ask for feedback on the recovery approach”. Choose
**Generate & send**. AI writes a plain-text subject and body from that purpose and
the latest completed discussion shown in the form, then the application sends it
without another review step. When no purpose is entered, it summarizes that
discussion and asks for feedback. Without a completed discussion, a purpose is
required.

The message and status remain in **Recent emails**. Provider acceptance is shown
as **Email accepted by provider**; it does not confirm inbox delivery or reading.
This connector sends messages only: it does not read mail or watch for replies.
It supports one recipient per request, with no CC, BCC or attachments.

## Configure the sender once

The connector uses the standard-library SMTP client, with authenticated SSL or
STARTTLS and certificate verification. Configure the email provider on the
computer running Company Brain. The SMTP account must permit password/app-password
authentication; OAuth-only tenants require a different adapter.

Create a private JSON file outside tracked source, for example
`.secrets/email.local.json`:

```json
{
  "sender": "you@example.com",
  "host": "smtp.your-provider.example",
  "port": 465,
  "security": "ssl",
  "username": "you@example.com",
  "password": "replace-with-your-provider-app-password"
}
```

Use your provider's actual host and credentials. `security` must be `ssl` (commonly
port 465) or `starttls` (commonly port 587). The sender must be authorized by that
account. On macOS/Linux, restrict the file before starting the app:

```sh
chmod 600 .secrets/email.local.json
export BRAIN_EMAIL_CONFIG="$PWD/.secrets/email.local.json"
# Start Company Brain with your normal config/data/model arguments in this shell.
```

On Windows, set `BRAIN_EMAIL_CONFIG` to the file's absolute path and restrict its
Windows file permissions to the application operator. POSIX mode checks apply on
macOS/Linux only. The app reads configuration from the server environment, not
the browser. Restart the server after setting the environment variable.

For Gmail accounts that support app passwords, use `smtp.gmail.com`, port 465 and
`ssl`, with the full Gmail address and an app password. App passwords require
2-Step Verification and may be unavailable for some managed or protected accounts.
Follow [Google's app-password instructions](https://support.google.com/accounts/answer/185833)
and [mail-client guidance](https://support.google.com/mail/answer/7126229).
Do not enter a Google account password into the application.

Open **Email → Check sender connection** to authenticate without sending a test
message. The UI reports sender configuration separately from verified SMTP
authentication. An available configuration does not guarantee delivery permission.

## Context and delivery behavior

Generation uses the selected repository name/URL, the chosen completed question,
its answer claims and limitations, and the optional purpose. It does not fetch
additional private/team memory, source files, documents or the mailbox. Content
already quoted in that discussion can appear in the email. The **Generate & send**
button authorizes emailing that discussion to the entered recipient. The AI
composer has no sending tools and cannot choose or change the recipient; the
backend binds the envelope to the submitted address. Chat directs email requests
to this panel and does not claim to have sent messages itself.

Credentials are read from the private config file only. They are excluded from
AI prompts, browser responses, email history and generated artifacts. Application
SQLite state retains recipient, purpose, context snapshot and generated message;
keep the application data directory private and ignored by Git.

Each submit uses a stable request ID. Repeating it returns the same job; the
backend consumes queued jobs once. Requests are not retried automatically after
provider errors, interruptions or server restart. A lost connection during message
submission is reported as **unknown** because the provider may already have
accepted it. Check the provider/recipient before starting a new email in that case.
SMTP sent mail may not appear in the provider's Sent folder; that depends on the
provider, not this connector.

Tests cover the actual generation adapter boundary, TLS SMTP adapter, application
endpoints, recipient/header validation, request deduplication, background failures,
restart recovery and provider acceptance/rejection. They use local SMTP fixtures
and do not email real people. Live delivery requires the operator's sender setup.
See [Python's SMTP documentation](https://docs.python.org/3/library/smtplib.html)
for transport behavior.
