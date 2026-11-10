import React, {useState} from 'react';

const json = body => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});

// Checked again on the server; this only gives earlier feedback.
export function passwordMismatch(data) {
  return data.password !== data.confirm ? 'The new passwords do not match.' : '';
}

export function generatePassword() {
  const words = 'amber brook cedar dawn ember fern grove harbor iris juniper kestrel linen meadow north olive pebble quill river sage tide umber violet willow yarrow'.split(' ');
  const pick = new Uint32Array(4);
  crypto.getRandomValues(pick);
  return [...pick].map((n, i) => i === 3 ? String(n % 900 + 100) : words[n % words.length]).join('-');
}

function NewPasswordFields() {
  return <>
    <label>New password<input name="password" type="password" minLength={12} maxLength={128} autoComplete="new-password" required/></label>
    <label>Confirm new password<input name="confirm" type="password" minLength={12} maxLength={128} autoComplete="new-password" required/></label>
    <small>Use at least 12 characters. A short phrase of unrelated words works well. Avoid your email address and passwords used on other sites; known breached passwords are rejected.</small>
  </>;
}

export function ChangePassword({api, action, busy, required, onChanged, onCancel}) {
  const [problem, setProblem] = useState('');
  function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    const mismatch = passwordMismatch(data);
    setProblem(mismatch);
    if (mismatch) return;
    action(async () => {
      const user = await (await api('/password', json({current_password:data.current, new_password:data.password}))).json();
      form.reset();
      onChanged(user);
    });
  }
  return <section className="login password-panel">
    <span className="eyebrow">ACCOUNT SECURITY</span>
    <h2>{required ? 'Choose your own password' : 'Change your password'}</h2>
    <p>{required ? 'You signed in with a temporary password from the church office. Choose a new password to continue.' : 'Other devices will be signed out after the change.'}</p>
    {problem && <p className="error" role="alert">{problem}</p>}
    <form onSubmit={submit}>
      <label>{required ? 'Temporary password' : 'Current password'}<input name="current" type="password" autoComplete="current-password" required/></label>
      <NewPasswordFields/>
      <button disabled={busy}>Save new password</button>
      {onCancel && <button type="button" className="outline" onClick={onCancel}>Cancel</button>}
    </form>
  </section>;
}

export function ForgotPassword({api, action, busy, setNotice, onBack}) {
  function submit(event) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    action(async () => {
      await api('/password-reset', json({email:data.email}));
      setNotice('If an active account uses that email, a reset link is on its way. It expires in 30 minutes. If nothing arrives, contact the church office.');
      onBack();
    });
  }
  return <section className="login">
    <span className="eyebrow">FORGOT PASSWORD</span>
    <h2>Reset your password</h2>
    <p>Enter your sign-in email and we will send you a link to choose a new password.</p>
    <form onSubmit={submit}>
      <label>Email address<input name="email" type="email" autoComplete="username" autoCapitalize="none" spellCheck={false} required placeholder="you@example.com"/></label>
      <button disabled={busy}>Send reset link</button>
      <button type="button" className="outline" onClick={onBack}>Back to sign in</button>
    </form>
  </section>;
}

export function ResetPassword({token, invite, api, action, busy, setNotice, onDone}) {
  const [problem, setProblem] = useState('');
  function submit(event) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const mismatch = passwordMismatch(data);
    setProblem(mismatch);
    if (mismatch) return;
    action(async () => {
      await api('/password-reset/confirm', json({token, password:data.password}));
      onDone();
      setNotice(invite ? 'Your password is set. Sign in to view your donation slips.' : 'Your password has been updated. Sign in with your new password.');
    });
  }
  return <section className="login password-panel">
    <span className="eyebrow">{invite ? 'WELCOME' : 'RESET PASSWORD'}</span>
    <h2>{invite ? 'Choose your password' : 'Choose a new password'}</h2>
    {invite && <p>Set a password to finish creating your member portal account.</p>}
    {problem && <p className="error" role="alert">{problem}</p>}
    <form onSubmit={submit}>
      <NewPasswordFields/>
      <button disabled={busy}>Set new password</button>
      <button type="button" className="outline" onClick={onDone}>Back to sign in</button>
    </form>
  </section>;
}
