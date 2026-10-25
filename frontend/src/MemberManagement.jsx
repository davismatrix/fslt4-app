import React, {useState} from 'react';

export default function MemberManagement({members, slips, api, refresh, action, busy, setNotice, onPreview, onDownload}) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const member = members.find(item => item.id === selected);
  const memberSlips = slips.filter(slip => slip.member_id === selected);
  function changeAccess(item) {
    const active = !item.active;
    if (!window.confirm(`${active ? 'Restore' : 'Revoke'} access for ${item.name}? ${active ? 'They will need to sign in again.' : 'They will be signed out and unable to sign in. Their slips will be kept.'}`)) return;
    action(async () => {
      await api(`/members/${item.id}/access`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({active})});
      await refresh();
      setNotice(`Access ${active ? 'restored' : 'revoked'} for ${item.name}.`);
    });
  }
  function removeMember(item) {
    if (!window.confirm(`Permanently delete ${item.name} (${item.email}) and all ${item.slip_count} donation slips? This cannot be undone. To keep their slips, revoke access instead.`)) return;
    action(async () => {
      await api(`/members/${item.id}`, {method:'DELETE'});
      setSelected(null);
      await refresh();
      setNotice('Member account and donation slips deleted.');
    });
  }
  function removeSlip(slip) {
    if (!window.confirm(`Permanently delete the ${slip.year} donation slip for ${member.name}? This cannot be undone.`)) return;
    action(async () => {
      await api(`/slips/${slip.id}`, {method:'DELETE'});
      await refresh();
      setNotice('Donation slip deleted.');
    });
  }
  return <section className="member-management">
    <h2>Member management</h2>
    <p>View members, control access, and manage uploaded donation slips.</p>
    <label>Search members<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Name or email"/></label>
    <div className="batch-table"><table><thead><tr><th>Member</th><th>Access</th><th>Slips</th><th>Actions</th></tr></thead><tbody>
      {members.filter(item => `${item.name} ${item.email}`.toLowerCase().includes(search.toLowerCase())).map(item => <tr key={item.id}>
        <td>{item.name}<br/>{item.email}</td><td>{item.active ? 'Active' : 'Revoked'}</td><td>{item.slip_count}</td>
        <td><div className="management-actions">
          <button className="outline" disabled={busy} onClick={() => setSelected(item.id)}>Manage slips</button>
          <button className="outline" disabled={busy} onClick={() => changeAccess(item)}>{item.active ? 'Revoke access' : 'Restore access'}</button>
          <button className="outline danger" disabled={busy} onClick={() => removeMember(item)}>Delete member</button>
        </div></td>
      </tr>)}
    </tbody></table></div>
    {!members.length && <p>No member accounts yet.</p>}
    {member && <div className="member-slips">
      <div className="section-title"><h3>Donation slips for {member.name}</h3><button className="outline" onClick={() => setSelected(null)}>Close</button></div>
      {!memberSlips.length && <p>No uploaded donation slips for this member.</p>}
      {memberSlips.map(slip => <div className="managed-slip" key={slip.id}>
        <h3>{slip.year} donation slip</h3>
        <div className="management-actions">
          <button className="outline" disabled={busy} onClick={() => onPreview(slip)}>Preview</button>
          <button className="outline" disabled={busy} onClick={() => onDownload(slip)}>Download</button>
          <button className="outline danger" disabled={busy} onClick={() => removeSlip(slip)}>Delete slip</button>
        </div>
        <form onSubmit={event => {
          event.preventDefault();
          const form = event.currentTarget;
          const file = new FormData(form).get('pdf');
          if (!window.confirm(`Replace the ${slip.year} donation slip for ${member.name}? The previous PDF will be overwritten.`)) return;
          action(async () => {
            await api(`/slips/${slip.id}/replace`, {method:'POST', headers:{'Content-Type':'application/pdf'}, body:file});
            form.reset();
            await refresh();
            setNotice('Donation slip replaced.');
          });
        }}>
          <label>Replacement PDF (up to 10 MB)<input name="pdf" type="file" accept="application/pdf" required disabled={busy}/></label>
          <button disabled={busy}>Replace PDF</button>
        </form>
      </div>)}
    </div>}
  </section>;
}
