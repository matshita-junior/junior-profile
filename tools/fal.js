// Runs a model on fal.ai and saves what it returns (images, video, audio).
// Requires Node.js 18+ and an API key from https://fal.ai/dashboard/keys in FAL_KEY.
//
//   FAL_KEY=... node tools/fal.js <model-id> [field ...] [--out dir]
//
//   node tools/fal.js fal-ai/flux/dev prompt="a hamster sipping tea, lofi anime" \
//     image_size=portrait_16_9 num_images:=2
//   node tools/fal.js fal-ai/kling-video/v2.1/standard/image-to-video \
//     prompt="the hamster waves at the camera" image_url@hamcup/assets/jaga-front.png duration=5
//
// Each field is one input of the model (see the API tab of its page on fal.ai):
// name=text sends a string, name:=json sends a number, true/false, array or object,
// and name@path sends a local file as a data URI. The request goes through fal's
// queue; the result JSON and every file it links to are written to
// fal-output/<request id>/ (or --out).
const fs = require('fs');
const path = require('path');

const MIME = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.gif': 'image/gif', '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime',
  '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4'
};

const args = process.argv.slice(2);
let outDir = 'fal-output';
const outFlag = args.indexOf('--out');
if (outFlag !== -1) outDir = args.splice(outFlag, 2)[1];
const [model, ...fields] = args;
const key = process.env.FAL_KEY;
if (!model) fail('usage: FAL_KEY=... node tools/fal.js <model-id> [name=text | name:=json | name@file ...] [--out dir]');
if (!key) fail('FAL_KEY is not set (create a key at https://fal.ai/dashboard/keys)');

const input = {};
for (const field of fields) {
  const m = field.match(/^(\w+)(:=|=|@)([\s\S]*)$/);
  if (!m) fail(`expected name=text, name:=json or name@file, got "${field}"`);
  const [, name, op, raw] = m;
  input[name] = op === '=' ? raw : op === ':=' ? JSON.parse(raw) : dataUri(raw);
}

(async () => {
  const job = await api(`https://queue.fal.run/${model}`, { method: 'POST', body: JSON.stringify(input) });
  console.log(`request ${job.request_id}`);

  let last = '', seen = 0;
  for (;;) {
    const status = await api(`${job.status_url}?logs=1`);
    const state = status.status === 'IN_QUEUE'
      ? `in queue (position ${status.queue_position})` : status.status.toLowerCase().replace('_', ' ');
    if (state !== last) console.log(last = state);
    const logs = status.logs || [];
    for (const log of logs.slice(seen)) console.log(`  ${log.message}`);
    seen = Math.max(seen, logs.length);
    if (status.status === 'COMPLETED') break;
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  const result = await api(job.response_url);
  const dir = path.join(outDir, job.request_id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'result.json'), JSON.stringify(result, null, 2));
  console.log(`wrote ${path.join(dir, 'result.json')}`);

  for (const url of new Set(fileUrls(result))) {
    const res = await fetch(url);
    if (!res.ok) fail(`GET ${url} -> ${res.status}`);
    const file = path.join(dir, path.basename(new URL(url).pathname));
    fs.writeFileSync(file, Buffer.from(await res.arrayBuffer()));
    console.log(`wrote ${file}`);
  }
})();

async function api(url, init = {}) {
  const res = await fetch(url, { ...init, headers: { Authorization: `Key ${key}`, 'Content-Type': 'application/json' } });
  const body = await res.text();
  if (!res.ok) fail(`${init.method || 'GET'} ${url} -> ${res.status} ${body}`);
  return JSON.parse(body);
}

function dataUri(file) {
  const type = MIME[path.extname(file).toLowerCase()] || 'application/octet-stream';
  return `data:${type};base64,${fs.readFileSync(file).toString('base64')}`;
}

// fal results describe files as { url, content_type, ... } anywhere in the JSON.
function* fileUrls(node) {
  if (Array.isArray(node)) for (const item of node) yield* fileUrls(item);
  else if (node && typeof node === 'object') {
    if (typeof node.url === 'string' && /^https?:/.test(node.url)) yield node.url;
    for (const item of Object.values(node)) yield* fileUrls(item);
  }
}

function fail(message) {
  console.error(message);
  process.exit(1);
}
