import React, {useEffect, useRef, useState} from 'react';

export default function AccountMenu({user, onChangePassword}) {
  const [open, setOpen] = useState(false);
  const container = useRef(null);
  const trigger = useRef(null);
  const firstItem = useRef(null);
  const initials = user.name.split(' ').map(n => n[0]).slice(0, 2).join('');
  useEffect(() => {
    if (!open) return;
    firstItem.current?.focus();
    function outside(event) {
      if (!container.current.contains(event.target)) setOpen(false);
    }
    function escape(event) {
      if (event.key === 'Escape') {
        setOpen(false);
        trigger.current.focus();
      }
    }
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);
  return <div className="account-menu" ref={container}>
    <button type="button" ref={trigger} className="avatar" aria-haspopup="menu" aria-expanded={open} aria-controls="account-menu-items" aria-label={`Account menu for ${user.name}`} onClick={() => setOpen(value => !value)}>{initials}</button>
    {open && <div id="account-menu-items" className="account-menu-items" role="menu" aria-label="Account">
      <div className="account-menu-identity"><strong>{user.name}</strong><span>{user.email}</span></div>
      <button type="button" role="menuitem" ref={firstItem} onClick={() => {setOpen(false); onChangePassword();}}>Change password</button>
    </div>}
  </div>;
}
