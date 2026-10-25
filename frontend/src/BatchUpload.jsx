import React, {useState} from 'react';

export default function BatchUpload({api, refresh, busy, action, setNotice}) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  return <section className="batch-upload">
    <h3>Batch upload donation slips</h3>
    <p>Upload a ZIP containing separate PDFs and a <code>members.csv</code> file together at the ZIP root or inside one enclosing folder. macOS metadata is ignored. Up to 100 slips, 10 MB per PDF, and 50 MB total (compressed and uncompressed).</p>
    <p>CSV format (members must already have accounts):</p>
    <pre>filename,email,year{'\n'}alice.pdf,alice@example.com,2025{'\n'}bob.pdf,bob@example.com,2025</pre>
    <form onSubmit={event => {
      event.preventDefault();
      action(async () => {
        setPreview(null);
        const result = await (await api('/batches/preview', {method:'POST', headers:{'Content-Type':'application/zip'}, body:file})).json();
        setPreview(result);
      });
    }}>
      <label>ZIP archive<input type="file" accept=".zip,application/zip" required disabled={busy} onChange={event => {setFile(event.target.files[0] || null); setPreview(null);}}/></label>
      <button disabled={busy || !file}>Validate and preview</button>
    </form>
    {preview && <div aria-live="polite">
      <h3>Review {preview.rows.length} receipt assignments</h3>
      {preview.errors.map((error,index) => <p className="error" key={index}>{error}</p>)}
      <div className="batch-table"><table><thead><tr><th>PDF</th><th>Member</th><th>Year</th><th>Validation</th></tr></thead><tbody>
        {preview.rows.map(row => <tr key={row.row}><td>{row.filename}</td><td>{row.member_name}<br/>{row.email}</td><td>{row.year}</td><td>{row.errors.length ? row.errors.join('; ') : 'Ready'}</td></tr>)}
      </tbody></table></div>
      <p>{preview.valid ? 'Check each assignment before confirming. All slips will be saved together.' : 'Fix the errors, select the corrected ZIP, and preview again. No slips have been saved.'}</p>
      <button disabled={busy || !preview.valid} onClick={() => action(async () => {
        const result = await (await api(`/batches/confirm?digest=${encodeURIComponent(preview.digest)}`, {method:'POST', headers:{'Content-Type':'application/zip'}, body:file})).json();
        setPreview(null);
        setFile(null);
        setNotice(`${result.uploaded} donation slips uploaded successfully.`);
        await refresh();
      })}>Confirm upload of {preview.rows.length} slips</button>
    </div>}
  </section>;
}
