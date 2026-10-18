/* Движок студии в браузере: Python (Pyodide) + numpy + OpenCV + Pillow, тот же код assetkit, что в командной строке. */
'use strict';
const BASE = new URL('../', self.location).href;
importScripts(BASE + 'vendor/pyodide/pyodide.js');

let api = null;
const status = (text, pct) => postMessage({ type: 'status', text, pct });

const ready = (async () => {
  status('Запускаю Python…', 5);
  const py = await loadPyodide({ indexURL: BASE + 'vendor/pyodide/' });
  status('Загружаю numpy, OpenCV, Pillow…', 30);
  await py.loadPackage(['numpy', 'opencv-python', 'pillow'], { messageCallback: () => {} });
  status('Загружаю инструменты…', 75);
  const man = await (await fetch(BASE + 'assetkit/manifest.json', { cache: 'no-cache' })).json();
  const root = '/home/pyodide/';
  let i = 0;
  await Promise.all(man.files.map(async (f) => {
    const r = await fetch(BASE + f + '?v=' + man.version);
    if (!r.ok) throw new Error('нет файла ' + f);
    const data = new Uint8Array(await r.arrayBuffer());
    const dir = (root + f).replace(/\/[^/]*$/, '');
    py.FS.mkdirTree(dir); py.FS.writeFile(root + f, data);
    i++; if (i % 8 === 0) status('Загружаю инструменты…', 75 + Math.round(20 * i / man.files.length));
  }));
  py.runPython(`import sys\nsys.path.insert(0, '${root}')\nimport assetkit.api`);
  api = py.pyimport('assetkit.api');
  status('Готово', 100);
  return man.version;
})();

ready.then((v) => postMessage({ type: 'ready', version: v, engine: 'browser' }),
           (e) => postMessage({ type: 'fail', error: String(e && e.message || e) }));

self.onmessage = async (ev) => {
  const { id, cmd, args, blobs } = ev.data;
  try {
    await ready;
    const r = api.call_json(cmd, JSON.stringify(args || {}), blobs || []);
    const res = JSON.parse(r.get(0));
    const list = r.get(1); const out = [];
    for (let k = 0; k < list.length; k++) {
      const item = list.get(k); const buf = item.getBuffer('u8');
      out.push(buf.data.slice()); buf.release(); item.destroy();
    }
    list.destroy(); r.destroy();
    postMessage({ type: 'result', id, result: res, blobs: out }, out.map((b) => b.buffer));
  } catch (e) {
    postMessage({ type: 'result', id, result: { error: String(e && e.message || e) }, blobs: [] });
  }
};
