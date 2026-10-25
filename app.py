"""Church donation-slip API. Run: uvicorn app:app --reload."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from notifications import send_welcome

DATA = Path(os.environ.get('CHURCH_DATA_DIR', 'data'))
DATA.mkdir(parents=True, exist_ok=True)
app = FastAPI(title='Love Assembly Member Portal')
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5173,capacitor://localhost,http://localhost,https://localhost').split(','), allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])

@contextmanager
def db():
    con = sqlite3.connect(DATA / 'church.db')
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

with db() as con:
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, expires INTEGER);
    CREATE TABLE IF NOT EXISTS slips(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, year INTEGER NOT NULL, filename TEXT NOT NULL, pdf BLOB NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(member_id,year));
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, slip_id INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    if 'active' not in {row['name'] for row in con.execute('PRAGMA table_info(users)')}:
        con.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
    con.execute('CREATE TABLE IF NOT EXISTS management_audit(id INTEGER PRIMARY KEY, admin_id INTEGER, member_id INTEGER, action TEXT, slip_id INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP)')

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()

def public(user):
    return {k: user[k] for k in ('id', 'name', 'email', 'role', 'active')}

def current_user(request: Request):
    token = request.headers.get('Authorization', '').removeprefix('Bearer ')
    with db() as con:
        user = con.execute('SELECT users.* FROM users JOIN sessions ON users.id=sessions.user_id WHERE token=? AND expires>? AND users.active=1', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    if not user:
        raise HTTPException(401, 'Please sign in again.')
    return user

def admin(user=Depends(current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administrator access required.')
    return user

class Login(BaseModel):
    email: str
    password: str

class Member(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        import re
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', value):
            raise ValueError('Enter a valid email address.')
        return value

@app.post('/api/login')
def login(body: Login):
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        user = con.execute('SELECT * FROM users WHERE email=?', (body.email.strip().lower(),)).fetchone()
        # Hash even unknown accounts to avoid a fast account-existence signal.
        expected = user['password'] if user else password_hash('unavailable')
        if not hmac.compare_digest(password_hash(body.password, expected.split(':')[0]), expected) or not user or not user['active']:
            raise HTTPException(401, 'Email or password is incorrect.')
        token = secrets.token_urlsafe(32)
        con.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user['id'], time.time()+3600))
    return {'token': token, 'user': public(user)}

@app.post('/api/logout')
def logout(request: Request, user=Depends(current_user)):
    token = request.headers.get('Authorization', '').removeprefix('Bearer ')
    with db() as con:
        con.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))
    return {'ok': True}

@app.get('/api/me')
def me(user=Depends(current_user)):
    return public(user)

@app.get('/api/slips')
def slips(user=Depends(current_user)):
    with db() as con:
        rows = con.execute('SELECT slips.id,member_id,year,filename,created,users.name AS member_name FROM slips JOIN users ON users.id=member_id WHERE member_id=? OR ?=\'admin\' ORDER BY year DESC, users.name', (user['id'], user['role'])).fetchall()
    return [dict(row) for row in rows]

def slip_response(slip_id, user, preview=False):
    with db() as con:
        slip = con.execute("SELECT * FROM slips WHERE id=? AND (member_id=? OR ?='admin')", (slip_id, user['id'], user['role'])).fetchone()
        if not slip:
            raise HTTPException(404, 'Donation slip not found.')
        con.execute('INSERT INTO audit(user_id,action,slip_id) VALUES (?,?,?)', (user['id'], 'preview' if preview else 'download', slip_id))
    disposition = 'inline' if preview else 'attachment'
    return Response(bytes(slip['pdf']), media_type='application/pdf', headers={
        'Content-Disposition': f'{disposition}; filename="donation-slip-{slip["year"]}.pdf"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    })


@app.get('/api/slips/{slip_id}/download')
def download(slip_id: int, user=Depends(current_user)):
    return slip_response(slip_id, user)


@app.get('/api/slips/{slip_id}/preview')
def preview_slip(slip_id: int, user=Depends(current_user)):
    return slip_response(slip_id, user, preview=True)

@app.get('/api/members')
def members(user=Depends(admin)):
    with db() as con:
        return [{**public(row), 'slip_count': row['slip_count']} for row in con.execute("SELECT users.*, (SELECT count(*) FROM slips WHERE member_id=users.id) AS slip_count FROM users WHERE role='member' ORDER BY name")]

@app.post('/api/members', status_code=201)
def create_member(body: Member, user=Depends(admin)):
    with db() as con:
        try:
            cursor = con.execute("INSERT INTO users(name,email,password,role) VALUES (?,?,?,'member')", (body.name.strip(),body.email.strip().lower(),password_hash(body.password)))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'An account already exists for this email.')
    notification = send_welcome(body.name.strip(), body.email)
    return {'id': cursor.lastrowid, 'notification': notification}

@app.post('/api/members/{member_id}/slips/{year}', status_code=201)
async def upload(member_id: int, year: int, request: Request, user=Depends(admin)):
    if not 1900 <= year <= 2100:
        raise HTTPException(400, 'Enter a valid tax year.')
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, 'PDF must be under 10 MB.')
    if not data.startswith(b'%PDF-'):
        raise HTTPException(400, 'Upload a PDF document.')
    with db() as con:
        if not con.execute("SELECT id FROM users WHERE id=? AND role='member'", (member_id,)).fetchone():
            raise HTTPException(404, 'Member not found.')
        try:
            cursor = con.execute('INSERT INTO slips(member_id,year,filename,pdf) VALUES (?,?,?,?)', (member_id,year,f'donation-slip-{year}.pdf',bytes(data)))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'A slip already exists for this member and year.')
        con.execute("INSERT INTO audit(user_id,action,slip_id) VALUES (?,'upload',?)", (user['id'],cursor.lastrowid))
    return {'id': cursor.lastrowid}

# ZIPs are inspected in memory and never extracted to the filesystem.
BATCH_LIMIT = 50 * 1024 * 1024

async def read_batch(request):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > BATCH_LIMIT:
            raise HTTPException(413, 'ZIP must be under 50 MB.')
        data.extend(chunk)
    return bytes(data)


def decode_batch_csv(raw):
    guidance = 'Save members.csv as a text CSV (CSV UTF-8 in Excel), then recreate the ZIP. Renaming an Excel workbook to .csv does not convert it.'
    if raw.startswith((b'PK', b'\xd0\xcf\x11\xe0')):
        raise ValueError(guidance)
    try:
        if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
            text = raw.decode('utf-16')
        else:
            try:
                text = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = raw.decode('cp1252')
    except UnicodeError:
        raise ValueError(guidance) from None
    if any(ord(char) < 32 and char not in '\r\n\t' for char in text):
        raise ValueError(guidance)
    return text


def inspect_batch(data, con):
    import csv
    import io
    import zipfile

    rows, errors, documents = [], [], []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 1000:
                raise ValueError('ZIP contains too many entries.')
            if any(entry.flag_bits & 1 for entry in entries):
                raise ValueError('Encrypted ZIP files are not supported.')
            if sum(entry.file_size for entry in entries) > BATCH_LIMIT:
                raise ValueError('Uncompressed ZIP contents must be under 50 MB.')
            files = {}
            for entry in entries:
                name = entry.filename
                parts = name.rstrip('/').split('/')
                if name.startswith('/') or '\\' in name or any(part in ('', '.', '..') or ':' in part for part in parts):
                    raise ValueError('ZIP contains an unsafe file path.')
                if entry.is_dir() or '__MACOSX' in parts or parts[-1] == '.DS_Store' or parts[-1].startswith('._'):
                    continue
                if name in files:
                    raise ValueError('ZIP filenames must be unique.')
                files[name] = entry
            # Accept root files or a single enclosing folder without flattening paths.
            if files and all('/' in name for name in files):
                roots = {name.split('/')[0] for name in files}
                if len(roots) == 1:
                    files = {name.split('/', 1)[1]: entry for name, entry in files.items()}
            if any('/' in name for name in files):
                raise ValueError('Place members.csv and all PDFs together at the ZIP root or inside one enclosing folder.')
            if len(files) > 101:
                raise ValueError('ZIP must contain at most 100 PDFs and one CSV.')
            names = list(files)
            if 'members.csv' not in names:
                raise ValueError('ZIP must contain members.csv.')
            if files['members.csv'].file_size > 128 * 1024:
                raise ValueError('members.csv must be under 128 KB.')
            reader = csv.DictReader(io.StringIO(decode_batch_csv(archive.read(files['members.csv']))), strict=True)
            if reader.fieldnames != ['filename', 'email', 'year']:
                raise ValueError('CSV header must be filename,email,year.')
            used_files, used_members = set(), set()
            for number, record in enumerate(reader, 2):
                if len(rows) >= 100:
                    raise ValueError('A batch may contain at most 100 receipts.')
                filename = (record.get('filename') or '').strip()
                email = (record.get('email') or '').strip().lower()
                year_text = (record.get('year') or '').strip()
                problems = []
                member = con.execute("SELECT id,name FROM users WHERE email=? AND role='member'", (email,)).fetchone()
                if not member:
                    problems.append('Unknown member email')
                year = int(year_text) if year_text.isascii() and year_text.isdigit() and len(year_text) == 4 else 0
                if not 1900 <= year <= 2100:
                    problems.append('Invalid tax year')
                if None in record or any(value is None for value in record.values()):
                    problems.append('Expected exactly three CSV columns')
                if filename in used_files:
                    problems.append('PDF is mapped more than once')
                used_files.add(filename)
                key = (email, year)
                if key in used_members:
                    problems.append('Duplicate member and year in CSV')
                used_members.add(key)
                if member and con.execute('SELECT id FROM slips WHERE member_id=? AND year=?', (member['id'], year)).fetchone():
                    problems.append('Slip already exists for this member and year')
                pdf = None
                if filename not in names or not filename.lower().endswith('.pdf'):
                    problems.append('PDF file missing or filename is not a PDF')
                elif files[filename].file_size > 10 * 1024 * 1024:
                    problems.append('PDF exceeds 10 MB')
                else:
                    pdf = archive.read(files[filename])
                    if not pdf.startswith(b'%PDF-'):
                        problems.append('Invalid PDF header')
                rows.append({'row': number, 'filename': filename, 'email': email, 'year': year_text, 'member_name': member['name'] if member else '', 'errors': problems})
                if not problems:
                    documents.append((member['id'], year, filename, pdf))
            if not rows:
                errors.append('CSV must contain at least one receipt.')
            extras = set(names) - used_files - {'members.csv'}
            if extras:
                errors.append('ZIP contains files not mapped in the CSV: ' + ', '.join(sorted(extras)))
    except (ValueError, UnicodeError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, NotImplementedError, EOFError, csv.Error) as exc:
        raise HTTPException(400, 'Invalid batch: ' + str(exc))
    return {'rows': rows, 'errors': errors, 'valid': bool(rows) and not errors and all(not row['errors'] for row in rows), 'digest': hashlib.sha256(data).hexdigest()}, documents


@app.post('/api/batches/preview')
async def preview_batch(request: Request, user=Depends(admin)):
    data = await read_batch(request)
    with db() as con:
        result, _ = inspect_batch(data, con)
    return result


@app.post('/api/batches/confirm', status_code=201)
async def confirm_batch(request: Request, digest: str, user=Depends(admin)):
    data = await read_batch(request)
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), digest):
        raise HTTPException(409, 'ZIP changed. Preview it again before confirming.')
    with db() as con:
        # Serialize validation and insertion so concurrent uploads cannot partially import a batch.
        con.execute('BEGIN IMMEDIATE')
        result, documents = inspect_batch(data, con)
        if not result['valid']:
            raise HTTPException(409, 'Batch validation failed. Preview again to review the errors. No slips were saved.')
        for member_id, year, filename, pdf in documents:
            cursor = con.execute('INSERT INTO slips(member_id,year,filename,pdf) VALUES (?,?,?,?)', (member_id, year, filename, pdf))
            con.execute("INSERT INTO audit(user_id,action,slip_id) VALUES (?,'batch_upload',?)", (user['id'], cursor.lastrowid))
    return {'uploaded': len(documents)}


class MemberAccess(BaseModel):
    active: bool


def require_member(con, member_id):
    member = con.execute("SELECT * FROM users WHERE id=? AND role='member'", (member_id,)).fetchone()
    if not member:
        raise HTTPException(404, 'Member not found.')
    return member


def management_event(con, admin_id, member_id, action, slip_id=None):
    con.execute('INSERT INTO management_audit(admin_id,member_id,action,slip_id) VALUES (?,?,?,?)', (admin_id, member_id, action, slip_id))


@app.post('/api/members/{member_id}/access')
def member_access(member_id: int, body: MemberAccess, user=Depends(admin)):
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        require_member(con, member_id)
        con.execute('UPDATE users SET active=? WHERE id=?', (int(body.active), member_id))
        # Restoring access never restores an old session.
        con.execute('DELETE FROM sessions WHERE user_id=?', (member_id,))
        management_event(con, user['id'], member_id, 'restore_access' if body.active else 'revoke_access')
    return {'active': body.active}


@app.delete('/api/members/{member_id}')
def delete_member(member_id: int, user=Depends(admin)):
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        require_member(con, member_id)
        management_event(con, user['id'], member_id, 'delete_member')
        con.execute('DELETE FROM sessions WHERE user_id=?', (member_id,))
        con.execute('DELETE FROM slips WHERE member_id=?', (member_id,))
        con.execute('DELETE FROM users WHERE id=?', (member_id,))
    return {'ok': True}


@app.delete('/api/slips/{slip_id}')
def delete_slip(slip_id: int, user=Depends(admin)):
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        slip = con.execute('SELECT member_id FROM slips WHERE id=?', (slip_id,)).fetchone()
        if not slip:
            raise HTTPException(404, 'Donation slip not found.')
        management_event(con, user['id'], slip['member_id'], 'delete_slip', slip_id)
        con.execute('DELETE FROM slips WHERE id=?', (slip_id,))
    return {'ok': True}


@app.post('/api/slips/{slip_id}/replace')
async def replace_slip(slip_id: int, request: Request, user=Depends(admin)):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > 10 * 1024 * 1024:
            raise HTTPException(413, 'PDF must be under 10 MB.')
        data.extend(chunk)
    if not data.startswith(b'%PDF-'):
        raise HTTPException(400, 'Upload a PDF document.')
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        slip = con.execute('SELECT member_id FROM slips WHERE id=?', (slip_id,)).fetchone()
        if not slip:
            raise HTTPException(404, 'Donation slip not found.')
        con.execute('UPDATE slips SET pdf=?, created=CURRENT_TIMESTAMP WHERE id=?', (bytes(data), slip_id))
        management_event(con, user['id'], slip['member_id'], 'replace_slip', slip_id)
    return {'ok': True}
