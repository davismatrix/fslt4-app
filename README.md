# Love Assembly Church member portal

See [CHANGELOG.md](CHANGELOG.md) for notable changes and update history.

A local MVP with a Python/FastAPI API, React frontend, SQLite persistence, and Capacitor configuration for iOS and Android. Grace Church is placeholder branding.

## Run locally

Python 3.11+ and Node 22+ recommended.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py
uvicorn app:app --reload
```

In another terminal:

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with the administrator you created. API documentation is at http://localhost:8000/docs.

1. In Church office, create a member with an initial password of at least 12 characters. Share credentials privately.
2. Upload an existing PDF donation slip for that member and tax year (10 MB maximum). Duplicate member/year uploads are rejected.
3. Sign out and sign in as that member to download the PDF. Members cannot list or download other members' documents.

The app distributes church-prepared receipts; it does not calculate donations or generate legally compliant tax receipts. No sample accounts or real member data are included.

## Mobile apps

The same React frontend can be packaged using Capacitor. Native downloads use the filesystem and OS share sheet; temporary cached PDFs are removed after sharing.

Set `VITE_API_URL` in `frontend/.env` to your deployed HTTPS backend origin. Configure backend `ALLOWED_ORIGINS` with the frontend's exact origins. The defaults include local web and Capacitor origins.

```sh
cd frontend
npm install
npm run build
npx cap add ios
npx cap add android
npm run mobile:sync
npx cap open ios
# or
npx cap open android
```

Xcode and Android Studio plus their platform SDKs are required. Use your own app ID in `capacitor.config.json` before adding platforms. Native projects, signing, device verification, and store submissions are not included in this starter. Rebuild and sync after changing the API origin or frontend.

## Data and deployment

The API stores users, hashed opaque sessions, PDF bytes, and upload/download audit records in `data/church.db`. Passwords use scrypt; sessions expire after one hour and are held only in frontend memory. Refreshing the app requires signing in again. `CHURCH_DATA_DIR` selects persistent storage. Keep that directory private and back it up; never serve it as static content. Use a single API instance with this SQLite starter.

Before handling real tax documents, add HTTPS hosting, encrypted storage/backups, login rate limiting, account recovery/password changes, administrator MFA, and an agreed retention policy. Configure production origins and operational monitoring. PDFs currently receive a file-header check, not malware scanning. This is an MVP, not a completed production security review.

## Verification

```sh
pip install pytest httpx
python -m pytest -q
cd frontend
npm run build
```

API tests cover authentication, member document isolation, administrator restrictions, logout, invalid uploads, and duplicate receipts.

Framework references: [FastAPI](https://fastapi.tiangolo.com/) and [Capacitor setup](https://capacitorjs.com/docs/getting-started).

## Admin batch upload

Sign in as an administrator and open **Church office → Batch upload donation slips**. Create a ZIP with all PDFs and `members.csv` together at its root or inside one enclosing folder (macOS metadata is ignored). Use a text CSV with this exact header (UTF-8, BOM-marked UTF-16, and Windows-1252 are supported):

```csv
filename,email,year
alice.pdf,alice@example.com,2025
bob.pdf,bob@example.com,2025
```

Members must already have accounts. Match filenames exactly; email matching ignores case. Each file must map to one member/year, and every ZIP file must be listed. Limits: 100 receipts, 10 MB per PDF, 50 MB compressed and uncompressed, 128 KB CSV. Encrypted archives are rejected.

Choose the ZIP and select **Validate and preview**. Review each member assignment, then **Confirm upload**. Fix validation errors and preview the corrected ZIP before confirming. Existing member/year receipts are never overwritten. Confirmation revalidates the archive and saves all documents and audit entries atomically; any conflict saves none. Preview does not persist files. Both batch endpoints enforce administrator authorization independently of the frontend.

## New member welcome emails

After an administrator creates a member, the backend sends a welcome notification using SMTP. The email includes the church name, portal URL, and sign-in email; it never includes the password or tax documents. Share the initial password privately.

Configure the backend process environment using the variables in `.env.example` (the file is documentation and is not loaded automatically): `SMTP_HOST`, `SMTP_FROM`, and `PORTAL_URL` are required. Set `SMTP_USERNAME` and `SMTP_PASSWORD` for authenticated SMTP. `SMTP_SECURITY=starttls` defaults to port 587; `ssl` defaults to 465. Both modes verify TLS certificates. `CHURCH_NAME` defaults to Love Assembly. Use a sender authorized by your email provider and your public HTTPS portal URL.

Member creation returns `notification`: `sent` (SMTP server accepted the message), `not_configured`, or `failed`. The admin sees the result. Email failure does not undo the new account or cause a duplicate-account retry. There is currently no automatic retry or resend feature. SMTP acceptance does not guarantee inbox delivery; check your provider's delivery logs for bounces or spam filtering. Actual delivery requires working SMTP settings and has not been verified by the automated tests.

If a CSV encoding error occurs, use Excel **Save As → CSV UTF-8 (Comma delimited)**, then recreate the ZIP. An `.xlsx` workbook must be exported, not renamed to `.csv`.

## Preview donation slips

Select **Preview** beside an available donation slip to open it in a dialog. The dialog includes Download PDF and Close preview controls; Escape also closes it. Members can preview only their own documents; administrators can preview all uploaded slips. Preview access is audited, responses disable caching, and temporary browser URLs are revoked when the dialog closes. The authenticated PDF request does not place session tokens in URLs.

Inline viewing uses the browser's built-in PDF support. If the browser or mobile WebView cannot render the document, use Download PDF to view or save it through the existing download/share flow. Browser and native device rendering require manual verification.

## Admin member management

Sign in as an administrator and open **Church office → Member management**. Search all members by name or email; each row shows access status and uploaded slip count.

- **Revoke access** blocks sign-in, invalidates all current sessions, and keeps donation slips. **Restore access** allows a fresh sign-in; previous sessions stay invalid.
- **Delete member** permanently removes the account, its sessions, and all its donation slips after confirmation. Use revoke access when records should be retained.
- **Manage slips** lists the selected member's documents. Preview or download each document, replace its PDF (same member and year, up to 10 MB), or permanently delete it. Replacement and deletion require confirmation.

All management endpoints enforce administrator access. Administrator accounts cannot be revoked or deleted through the member endpoints. Existing databases automatically gain an `active` column, defaulting current accounts to active. Management events are recorded in `management_audit`; deleted PDF bytes are no longer available through the application, but historical backups may retain copies. Revocation cannot recall PDFs already downloaded or opened on a member's device.
