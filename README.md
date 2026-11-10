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

1. In Church office, create a member. Leave the password blank to email them a 7-day link to choose their own password (recommended, requires SMTP), or enter a temporary password to share privately; it must be changed at first sign-in.
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

Before handling real tax documents, add HTTPS hosting, encrypted storage/backups, administrator MFA, and an agreed retention policy. Configure production origins and operational monitoring. PDFs currently receive a file-header check, not malware scanning. This is an MVP, not a completed production security review.

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

Edit the backend `.env` in the repository root, using `.env.example` as a template. The backend loads `.env` automatically at startup, including when using `manage.py`; existing exported environment variables take precedence. Restart the backend after changes. This is separate from `frontend/.env`. Quote values containing spaces or `#`, and do not commit credentials. Required SMTP configuration: `SMTP_HOST`, `SMTP_FROM`, and `PORTAL_URL` are required. Set `SMTP_USERNAME` and `SMTP_PASSWORD` for authenticated SMTP. `SMTP_SECURITY=starttls` defaults to port 587; `ssl` defaults to 465. Both modes verify TLS certificates. `CHURCH_NAME` defaults to Love Assembly. Use a sender authorized by your email provider and your public HTTPS portal URL.

Member creation returns `notification`: `sent` (SMTP server accepted the message), `not_configured`, or `failed`. The admin sees the result. Email failure does not undo the new account or cause a duplicate-account retry. There is currently no automatic retry or resend feature. SMTP acceptance does not guarantee inbox delivery; check your provider's delivery logs for bounces or spam filtering. Actual delivery requires working SMTP settings and has not been verified by the automated tests.

If a CSV encoding error occurs, use Excel **Save As → CSV UTF-8 (Comma delimited)**, then recreate the ZIP. An `.xlsx` workbook must be exported, not renamed to `.csv`.

## Preview donation slips

Select **Preview** beside an available donation slip to open it in a dialog. The dialog includes Download PDF and Close preview controls; Escape also closes it. Members can preview only their own documents; administrators can preview all uploaded slips. Preview access is audited, responses disable caching, and temporary browser URLs are revoked when the dialog closes. The authenticated PDF request does not place session tokens in URLs.

Inline viewing uses the browser's built-in PDF support. If the browser or mobile WebView cannot render the document, use Download PDF to view or save it through the existing download/share flow. Browser and native device rendering require manual verification.

## Passwords and account recovery

Passwords must be 12–128 characters, must not contain the account's email name, must not be a common password, and must not appear in the [Have I Been Pwned](https://haveibeenpwned.com/Passwords) breach corpus. The same rules apply to member creation, password changes, resets, invitations, and `manage.py`.

The breach check uses k-anonymity: only the first 5 hex characters of the password's SHA-1 hash are sent to `api.pwnedpasswords.com`, with response padding enabled. If the service is unreachable within 3 seconds, the password is accepted and a warning is logged. Set `PASSWORD_BREACH_CHECK=off` to disable it, for example on servers without outbound internet access.

- **Invitations (recommended).** Create a member with the password left blank. They receive a single-use link valid for 7 days to choose their own password, so nobody else ever knows it. Member management shows them as **Invited**, with **Resend invite** (which cancels earlier links). Invited members can also use **Forgot password?**.
- **Temporary passwords.** Members created with a password, and members whose password an administrator resets, must choose a new password before using the portal. Until then only `/api/me`, `/api/logout`, and `/api/password` accept their session.
- **Change password.** Signed-in users select **Change password** in the header. The current password is required, attempts are throttled like sign-in, and all other sessions are signed out.
- **Forgot password.** **Forgot password?** on the sign-in page emails a single-use link valid for 30 minutes. The response is the same whether or not the account exists, and email is sent after the response. A new link invalidates the previous one. Completing a reset signs out all sessions. Revoked accounts cannot reset.
- **Administrator reset.** In Member management, **Reset password** generates a temporary password, signs the member out, and shows it once for private sharing. The action is recorded in `management_audit`.
- **Administrator lockout.** Run `python manage.py reset-password` on the server. `python manage.py` (create administrator) asks for confirmation and applies the password rules.
- **Change notifications.** Members are emailed when their password is changed or reset, or when the office issues a temporary password, so an unexpected change is noticed. Accepting an invitation does not send one.

Invitation and reset links have the form `PORTAL_URL/password#invite=…` or `#reset=…`. The token is in the URL fragment, so it is not sent to servers or in Referer headers, and the app removes it from the address bar once read. Configure your web host to serve `index.html` for `/password` (the Vite dev server already does).

Self-service password events are recorded in `account_audit`. Existing databases gain `must_change_password` and `invite_pending` columns (existing accounts are unaffected) and `password_resets`/`account_audit` tables automatically.

### Sign-in throttling and reverse proxies

Each account allows 10 attempts per client address and 100 across all addresses per 15 minutes; each client address allows 50 attempts. A successful sign-in clears that client's attempts for the account, so normal use and a mistyped password never accumulate into a lockout, and someone guessing from one network cannot lock a member out elsewhere.

Behind a reverse proxy or load balancer, set `TRUSTED_PROXIES` to the comma-separated addresses of the proxies that connect to the API (for example `127.0.0.1`). The API then uses the nearest `X-Forwarded-For` address that is not a trusted proxy. Without it, every request appears to come from the proxy and all users share one client limit. `X-Forwarded-For` is ignored from any other peer, so it cannot be spoofed to evade limits.

### Opening invitation and reset links in the mobile app

Links open the web portal by default. To open them in the installed app instead, the portal domain (the host in `PORTAL_URL`) must prove it is associated with the app. Universal links and App Links need a real HTTPS domain; development tunnels and `localhost` will not work. The app's `appUrlOpen` listener (via `@capacitor/app`) then shows the set-password screen.

1. **Web host.** Copy the templates in `frontend/deep-links/` into `frontend/public/.well-known/` and fill them in:
   - `apple-app-site-association`: replace `YOUR_TEAM_ID` with your Apple Developer Team ID.
   - `assetlinks.json`: replace the fingerprint with your Android release signing certificate's SHA-256 (`keytool -list -v -keystore your.keystore`, or Play Console → App integrity when using Play App Signing).

   Serve both at `https://<portal-host>/.well-known/…` over HTTPS, with no redirects and `Content-Type: application/json`.
2. **iOS.** In Xcode, open the App target → **Signing & Capabilities** → **+ Capability** → **Associated Domains**, and add `applinks:<portal-host>`. This requires a paid Apple Developer account; personal (free) teams cannot sign the capability, which is why it is not enabled in the checked-in project.
3. **Android.** After `npx cap add android`, add this inside the main `<activity>` in `android/app/src/main/AndroidManifest.xml`:

   ```xml
   <intent-filter android:autoVerify="true">
       <action android:name="android.intent.action.VIEW" />
       <category android:name="android.intent.category.DEFAULT" />
       <category android:name="android.intent.category.BROWSABLE" />
       <data android:scheme="https" android:host="your-portal-host" android:path="/password" />
   </intent-filter>
   ```
4. Run `npm run mobile:sync`, reinstall the app, and test by tapping a link in Mail or Gmail. iOS does not open universal links typed or pasted into Safari's address bar.

## Admin member management

Sign in as an administrator and open **Church office → Member management**. Search all members by name or email; each row shows access status and uploaded slip count.

- **Revoke access** blocks sign-in, invalidates all current sessions, and keeps donation slips. **Restore access** allows a fresh sign-in; previous sessions stay invalid.
- **Delete member** permanently removes the account, its sessions, and all its donation slips after confirmation. Use revoke access when records should be retained.
- **Manage slips** lists the selected member's documents. Preview or download each document, replace its PDF (same member and year, up to 10 MB), or permanently delete it. Replacement and deletion require confirmation.

All management endpoints enforce administrator access. Administrator accounts cannot be revoked or deleted through the member endpoints. Existing databases automatically gain an `active` column, defaulting current accounts to active. Management events are recorded in `management_audit`; deleted PDF bytes are no longer available through the application, but historical backups may retain copies. Revocation cannot recall PDFs already downloaded or opened on a member's device.


## Security hardening and upgrade notes

Before upgrading an existing installation, stop the backend and back up `data/church.db` (or the database under `CHURCH_DATA_DIR`). Startup automatically migrates user and slip IDs to SQLite AUTOINCREMENT, preserving current rows and reserving IDs still referenced by historical audit records. Future deletions do not free IDs for reuse. This cannot reconstruct account identities already confused by ID reuse before the upgrade. Restart the backend and rebuild/reload the frontend together.

Batch previews now return an administrator-bound, single-use `preview_token`, valid for 15 minutes. Confirmation requires this token plus the same ZIP digest. The backend compares the reviewed account IDs, names, emails, and access status with their current values inside the import transaction. Changed assignments, missing/expired tokens, and replayed confirmations are rejected without saving slips. Existing browser previews must be repeated after upgrading. No PDFs are stored in preview records; expired records are removed during subsequent previews.

Login attempts are limited to 10 per normalized email and 50 per client IP in a rolling 15-minute window, including successful attempts. Limits are shared through SQLite across backend restarts. A blocked request returns HTTP 429 and `Retry-After: 900`. Password hashing happens outside the database write transaction, and account access is checked again before issuing a session. IP attribution uses the server's request client address; configure trusted proxy handling correctly when deploying behind a reverse proxy. Clients on a shared IP share its limit.

Expired or revoked sessions now return the frontend to sign-in on the next authenticated request and clear loaded account data and previews. Sign out clears local state even if the backend is unavailable. A network failure may prevent server-side logout; the server token still expires on its normal schedule.

Frontend session-handling regression tests can be run with:

```sh
cd frontend
npm test
```


## Mobile layout

On small screens the portal uses stacked forms, labeled cards for member and
batch tables, larger touch controls, and shortcuts to donation slips and the
church office. The PDF preview fills the screen and respects iPhone safe areas.
After frontend changes, run `npm run build` and `npx cap copy ios` from `frontend`,
then stop and rerun the app in Xcode to see the updated native bundle.
