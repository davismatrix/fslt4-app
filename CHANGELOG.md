# Changelog

Notable changes to this repository are tracked here. Add new entries under
Unreleased as work is completed, grouped by Added, Changed, Fixed, or Removed.
When publishing a release, move those entries under its version and release date
(`YYYY-MM-DD`).

This initial record summarizes work implemented before the changelog was added.
No release versions or historical release dates have been assigned.

## [Unreleased]

### Added

- Python/FastAPI backend with SQLite persistence, scrypt password hashing,
  expiring sessions, and administrator/member access controls.
- Administrator setup command and member account creation.
- React member portal with authenticated donation slip downloads and year filtering.
- Individual PDF uploads for administrators, with file-size checks and duplicate
  member/year protection.
- Administrator batch uploads using a ZIP of PDFs and a `members.csv` mapping.
  Includes validation previews, member matching, duplicate detection, archive
  limits, atomic confirmation, and upload audit records.
- Donation slip preview dialog with authenticated PDF access, download fallback,
  access auditing, and temporary browser URL cleanup.
- SMTP welcome notifications for new members, configurable church branding and
  portal URL, and administrator-visible notification status. Passwords are
  excluded from email; account creation succeeds even if delivery fails.
- Administrator member management with search, access status, slip counts,
  access revocation/restoration, and account deletion.
- Administrator controls to preview, download, replace, and delete existing
  donation slips, with confirmations for destructive actions.
- Immediate session invalidation on member access changes, automatic migration
  for existing accounts, and management audit records.
- Capacitor configuration for iOS and Android, including native PDF sharing.
- API and notification tests covering authorization, document isolation, batch
  validation, preview access, email handling, and member management.
- Setup, SMTP, mobile packaging, batch upload, and member management documentation.
- This changelog and a README link for tracking future changes.

### Changed

- Made the administrator Church donation slips section collapsible, including its
  year filter, with a keyboard-accessible toggle. Member documents remain visible.

- Updated portal branding from Grace Church to Love Assembly.
- Replaced “tax slips” with “donation slips” across app text, email content,
  documentation, and generated download filenames.

### Fixed

- Batch imports now accept a single enclosing folder and ignore macOS ZIP metadata
  such as `.DS_Store` and `__MACOSX`, while rejecting unsafe or ambiguous paths.
- CSV imports now support UTF-8, BOM-marked UTF-16, and Windows-1252 text, with
  actionable errors for binary workbooks and invalid input.
