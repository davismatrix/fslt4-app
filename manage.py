"""Create the first administrator, or reset an administrator password, without putting a password in shell history.

Usage: python manage.py                 create an administrator
       python manage.py reset-password  set a new password for an existing administrator
"""
import sqlite3
import sys
from getpass import getpass
from app import db, password_hash, password_problem
from notifications import send_password_changed


def prompt_password(email):
    password = getpass('Password (at least 12 characters): ')
    if password != getpass('Confirm password: '):
        raise SystemExit('Passwords do not match.')
    problem = password_problem(password, email)
    if problem:
        raise SystemExit(problem)
    return password


def create_admin():
    name = input('Administrator name: ').strip()
    email = input('Administrator email: ').strip().lower()
    if not name or '@' not in email:
        raise SystemExit('Name and a valid email are required.')
    password = prompt_password(email)
    try:
        with db() as con:
            con.execute("INSERT INTO users(name,email,password,role) VALUES (?,?,?,'admin')", (name,email,password_hash(password)))
    except sqlite3.IntegrityError:
        raise SystemExit('An account already exists for this email. Use: python manage.py reset-password')
    print('Administrator created.')


def reset_admin_password():
    email = input('Administrator email: ').strip().lower()
    with db() as con:
        user = con.execute("SELECT id,name FROM users WHERE email=? AND role='admin'", (email,)).fetchone()
    if not user:
        raise SystemExit('No administrator has this email.')
    password = prompt_password(email)
    with db() as con:
        con.execute('UPDATE users SET password=?, must_change_password=0, active=1 WHERE id=?', (password_hash(password), user['id']))
        con.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
        con.execute('DELETE FROM password_resets WHERE user_id=?', (user['id'],))
        con.execute("INSERT INTO account_audit(user_id,action) VALUES (?,'admin_password_reset_cli')", (user['id'],))
    print('Administrator password updated. Existing sessions were signed out.')
    print('Password-change email:', send_password_changed(user['name'], email))


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else 'create-admin'
    if command == 'create-admin':
        create_admin()
    elif command == 'reset-password':
        reset_admin_password()
    else:
        raise SystemExit(__doc__)
