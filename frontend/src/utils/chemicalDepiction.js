// Use the same isolated Ketcher / Indigo runtime as the input editor. Rendering
// stays in this browser; SMILES never go to a third-party image service.
let frame, loading, queue = Promise.resolve(), idleTimer;
function dispose() { frame?.remove(); frame = null; loading = null; }
function renderer() {
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    frame = document.createElement('iframe');
    frame.title = 'Chemical depiction renderer';
    frame.setAttribute('aria-hidden', 'true');
    frame.setAttribute('inert', '');
    frame.tabIndex = -1;
    frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:800px;height:500px;visibility:hidden;pointer-events:none';
    const timeout = setTimeout(() => done(new Error('Renderer unavailable')), 45000);
    function done(error) {
      clearTimeout(timeout);
      window.removeEventListener('message', ready);
      if (error) { dispose(); reject(error); }
      else resolve(frame.contentWindow.ketcher);
    }
    function ready(event) {
      if (event.origin !== location.origin || event.source !== frame?.contentWindow || event.data?.source !== 'enzymind-ketcher') return;
      if (event.data.event === 'ready') done();
      else if (event.data.event === 'load-error') done(new Error('Renderer unavailable'));
    }
    window.addEventListener('message', ready);
    frame.src = `${import.meta.env.BASE_URL}ketcher/index.html`;
    document.body.append(frame);
  });
  return loading;
}
export function chemicalDepiction(smiles) {
  const job = queue.then(async () => {
    clearTimeout(idleTimer);
    let timeout;
    try {
      const ketcher = await renderer();
      const blob = await Promise.race([
        ketcher.generateImage(smiles, { outputFormat: 'svg', backgroundColor: '255,255,255' }),
        new Promise((_, reject) => { timeout = setTimeout(() => { dispose(); reject(new Error('Rendering timed out')); }, 30000); }),
      ]);
      return blob;
    } finally { clearTimeout(timeout); idleTimer = setTimeout(dispose, 30000); }
  });
  queue = job.catch(() => {});
  return job;
}
