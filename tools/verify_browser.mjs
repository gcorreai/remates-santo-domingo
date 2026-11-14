import { spawn } from 'node:child_process';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

const catalogue = JSON.parse(await readFile(resolve('data/catalog.json'), 'utf8'));
const expectedLinks = catalogue.reduce((count, record) => count + 1 + (record.maps_url !== null ? 1 : 0), 0);
const profile = await mkdtemp(join(process.env.TMPDIR, 'remates-cdp-'));
const child = spawn('chromium', ['--headless', '--no-sandbox', '--disable-gpu', '--no-first-run', '--disable-background-networking', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank']);
let socket;
try {
  const endpoint = await new Promise((resolve, reject) => {
    let stderr = '';
    const timeout = setTimeout(() => reject(new Error('DevTools timeout')), 15000);
    child.stderr.on('data', data => {
      stderr += data;
      const found = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (found) { clearTimeout(timeout); resolve(found[1]); }
    });
    child.on('error', reject);
  });
  socket = new WebSocket(endpoint);
  await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
  let nextId = 0;
  const pending = new Map();
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const item = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) item.reject(new Error(JSON.stringify(message.error)));
      else item.resolve(message.result);
    }
  });
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  await send('Page.enable', {}, sessionId);
  for (const width of [320, 390, 768, 1440]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 }, sessionId);
    await send('Page.navigate', { url: process.env.SITE_URL || pathToFileURL(resolve('docs/index.html')).href }, sessionId);
    let result;
    for (let attempt = 0; attempt < 100; attempt++) {
      result = await send('Runtime.evaluate', { returnByValue: true, expression: `(() => {
        if(document.readyState !== 'complete' || !document.querySelector('article')) return null;
        const links = [...document.querySelectorAll('article a')];
        return {width: innerWidth, overflow: document.documentElement.scrollWidth > innerWidth,
          cards: document.querySelectorAll('article').length, links: links.length,
          minTargetHeight: Math.min(...links.map(a => a.getBoundingClientRect().height)),
          columns: getComputedStyle(document.querySelector('.directory')).gridTemplateColumns,
          stylesheetLoaded: document.styleSheets.length === 1 && getComputedStyle(document.body).margin === '0px'};
      })()` }, sessionId);
      if (result.result.value) break;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    const report = result.result.value;
    console.log(JSON.stringify(report));
    assert.equal(report.width, width);
    assert.equal(report.overflow, false);
    assert.equal(report.cards, catalogue.length);
    assert.equal(report.links, expectedLinks);
    assert.ok(report.minTargetHeight >= 44);
    assert.ok(report.stylesheetLoaded);
  }
  await send('Browser.close');
} finally {
  socket?.close();
  child.kill();
  await new Promise(resolve => setTimeout(resolve, 500));
  await rm(profile, { recursive: true, force: true });
}
