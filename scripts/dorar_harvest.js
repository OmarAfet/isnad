// Harvest hadith rulings from dorar.net, the platform the challenge Reference Framework names
// for hadith grading.
//
// WHY THIS IS JAVASCRIPT AND NOT PYTHON: dorar.net sits behind Cloudflare and answers any
// automated request with HTTP 403 — verified with curl from two machines. A real browser session
// passes. Navigating the tab to dorar.net first also makes /dorar_api.json same-origin, which
// removes the CORS problem that would otherwise block reading the response.
//
// HOW TO RUN: open https://dorar.net/hadith in a browser, serve data/dorar/queries.json over
// 127.0.0.1:8788 with _tools/sink.py (it sends the CORS headers python3 -m http.server does not),
// paste this file into the console, then call:
//     await __harvest(0, 22, 500)      // start, end, delay in ms
// Results POST back to the sink. Keep batches small: dorar answers in ~5 s, and this is someone
// else's public service — the delay is there on purpose.

window.__dorar = {
  // The API returns HTML inside JSON: {"ahadith":{"result":"<div class=hadith>…"}}
  parse(html) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const out = [];
    doc.querySelectorAll('div.hadith').forEach(h => {
      let info = h.nextElementSibling;
      while (info && !(info.classList && info.classList.contains('hadith-info'))) {
        info = info.nextElementSibling;
      }
      const txt = (h.innerText || '').replace(/^\s*\d+\s*-\s*/, '').replace(/\s+/g, ' ').trim();
      const it = info ? (info.innerText || '') : '';
      const g = label => {
        const m = it.match(new RegExp(label + '\\s*:?\\s*([^\\n]*)'));
        return m ? m[1].replace(/\s+/g, ' ').trim() : null;
      };
      out.push({
        text: txt,
        rawi: g('الراوي'),            // the Companion who transmitted it
        muhaddith: g('المحدث'),       // the scholar who ruled on it
        source: g('المصدر'),          // the book the ruling appears in
        page: g('الصفحة أو الرقم'),   // page or hadith number in that book
        ruling: g('خلاصة حكم المحدث'),// the ruling itself, free text
      });
    });
    return out;
  },

  async query(skey) {
    const r = await fetch('/dorar_api.json?skey=' + encodeURIComponent(skey),
                          { credentials: 'include' });
    if (!r.ok) return { skey, error: 'http ' + r.status };
    const j = await r.json();
    return { skey, results: this.parse((j.ahadith && j.ahadith.result) || '') };
  },
};

window.__harvest = async function (start, end, delayMs) {
  const qs = await (await fetch('http://127.0.0.1:8788/queries.json')).json();
  const slice = qs.slice(start, end);
  const out = [];
  let errs = 0;
  const flush = () => fetch('http://127.0.0.1:8788/s-' + String(start).padStart(4, '0'), {
    method: 'POST', mode: 'no-cors', headers: { 'Content-Type': 'text/plain' },
    body: JSON.stringify(out),
  });
  for (const q of slice) {
    try {
      const a = await window.__dorar.query(q.skey);
      out.push({ ...q, dorar: (a.results || []).slice(0, 8),
                 dorar_total: (a.results || []).length, error: a.error || null });
      if (a.error) errs++;
    } catch (e) { out.push({ ...q, dorar: [], error: String(e) }); errs++; }
    if (out.length % 6 === 0) await flush();   // survive a client-side timeout
    await new Promise(r => setTimeout(r, delayMs || 800));
  }
  await flush();
  return `rows=${out.length} errors=${errs} hits=${out.filter(r => r.dorar.length).length}`;
};
