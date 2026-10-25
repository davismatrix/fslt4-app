"""Create the first administrator without putting a password in shell history."""
from getpass import getpass
from app import db, password_hash

if __name__ == '__main__':
    name = input('Administrator name: ').strip()
    email = input('Administrator email: ').strip().lower()
    password = getpass('Password (at least 12 characters): ')
    if not name or '@' not in email or len(password) < 12:
        raise SystemExit('Name, valid email, and a password of at least 12 characters are required.')
    with db() as con:
        con.execute("INSERT INTO users(name,email,password,role) VALUES (?,?,?,'admin')", (name,email,password_hash(password)))
    print('Administrator created.')
