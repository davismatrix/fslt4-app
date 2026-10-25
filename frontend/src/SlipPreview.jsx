import React, {useEffect, useRef, useState} from 'react';

export default function SlipPreview({slip, api, onClose, onDownload, busy}) {
  const dialog = useRef(null);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    const previousFocus = document.activeElement;
    const controller = new AbortController();
    let objectUrl;
    let active = true;
    dialog.current.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    (async () => {
      try {
        const response = await api(`/slips/${slip.id}/preview`, {signal: controller.signal});
        const blob = await response.blob();
        if (active) {
          objectUrl = URL.createObjectURL(blob);
          setUrl(objectUrl);
        }
      } catch (err) {
        if (active && err.name !== 'AbortError') setError(err.message);
      }
    })();
    return () => {
      active = false;
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [slip.id]);
  return <dialog ref={dialog} className="slip-preview" aria-labelledby="slip-preview-title" onCancel={onClose}>
    <div className="preview-header">
      <div><h2 id="slip-preview-title">{slip.year} Giving donation slip</h2><p>{slip.member_name}</p></div>
      <button type="button" className="outline" onClick={onClose} autoFocus>Close preview</button>
    </div>
    {error ? <p role="alert" className="error">{error}</p> : url ?
      <object className="pdf-viewer" data={url} type="application/pdf" aria-label={`${slip.year} donation slip PDF`}>
        <p>Your device cannot display PDFs here. Use Download to open or save this document.</p>
      </object> : <p role="status">Loading donation slip…</p>}
    <div className="preview-footer"><p>If the preview is blank or unsupported, download the PDF to view it.</p><button type="button" disabled={busy || !url} onClick={onDownload}>Download PDF</button></div>
  </dialog>;
}
