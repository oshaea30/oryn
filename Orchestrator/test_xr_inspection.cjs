'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { PassThrough } = require('node:stream');
const { McpClient, READ_TOOLS, decode, focused, checkPose, captureBytes, inspect } = require('./xr_inspection.cjs');

const MODEL = 'Oryn 39-part model 1';
const wrapped = value => ({ content: [{ type: 'text', text: JSON.stringify(value) }] });
const session = handle => ({ session: { handle }, state: { name: 'XR_SESSION_STATE_FOCUSED' } });
const pose = target => ({ matchCount: 1, matches: [{ path: target, active: true,
  position: { x: 0, y: 1, z: 0 }, rotation: { x: 0, y: 0, z: 0 }, scale: { x: .35, y: .35, z: .35 } }] });
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBykAAAAASUVORK5CYII=', 'base64');
const image = () => ({ content: [{ type: 'image', mimeType: 'image/png', data: png.toString('base64') }] });
function fixture(modify = (name, data) => data) {
  const calls = [];
  return { calls, async connect() {}, async call(name, args = {}) {
    calls.push({ name, args });
    let data;
    switch (name) {
      case 'openxr_get_session_info': data = session('82'); break;
      case 'openxr_get_instance_info': data = { application: { name: 'Oryn Workspace' }, engine: { name: 'Unity' } }; break;
      case 'unity_get_scene_root_objects': data = { rootObjects: ['Oryn Workspace', 'Workspace Panel', 'OVRCameraRig', 'Passthrough', MODEL].map(name => ({ name, active: true })) }; break;
      case 'unity_get_children': data = { children: Array.from({ length: 39 }, (_, i) => { const name = 'Part island_' + String(i + 1).padStart(3, '0'); return { name, path: MODEL + '/' + name }; }) }; break;
      case 'unity_get_world_pose': data = pose(args.path); break;
      case 'openxr_capture_composited_image': return modify(name, image());
      default: throw Error('Unexpected call');
    }
    return wrapped(modify(name, data));
  } };
}

test('valid fixture inspects model and all 39 parts without requesting an image', async () => {
  const client = fixture(); const result = await inspect(client);
  assert.equal(result.status, 'PASS'); assert.equal(result.partCount, 39); assert.equal(result.poses.length, 40);
  assert.equal(result.capture.status, 'NOT_REQUESTED');
  assert.ok(client.calls.every(c => READ_TOOLS.includes(c.name)));
  assert.equal(client.calls.filter(c => c.name === 'openxr_capture_composited_image').length, 0);
});
test('capture is opt-in, saved once, and not a visual quality assertion', async () => {
  let saved = 0;
  const result = await inspect(fixture(), { capture: true, saveCapture: bytes => { assert.deepEqual(bytes, png); saved++; } });
  assert.equal(result.status, 'PASS'); assert.equal(saved, 1); assert.equal(result.capture.visualReview, 'NOT_AUTOMATED');
});
test('sleeping headset is blocked before reading scene', async () => {
  const client = fixture((name, data) => name === 'openxr_get_session_info' ? { state: { name: 'XR_SESSION_STATE_IDLE' } } : data);
  assert.equal((await inspect(client)).status, 'BLOCKED'); assert.equal(client.calls.length, 1);
});
test('session changes and loss of focus at completion block the result', async () => {
  for (const end of [session('83'), { state: { name: 'XR_SESSION_STATE_VISIBLE' } }]) {
    let count = 0;
    const client = fixture((name, data) => name === 'openxr_get_session_info' && ++count === 2 ? end : data);
    assert.equal((await inspect(client)).status, 'BLOCKED');
  }
});
test('wrong application and missing or duplicate workspace roots fail', async () => {
  for (const modify of [
    (n, d) => n === 'openxr_get_instance_info' ? { application: { name: 'Other' } } : d,
    (n, d) => { if (n === 'unity_get_scene_root_objects') d.rootObjects.pop(); return d; },
    (n, d) => { if (n === 'unity_get_scene_root_objects') d.rootObjects.push(d.rootObjects[0]); return d; },
  ]) assert.equal((await inspect(fixture(modify))).status, 'FAIL');
});
test('missing, duplicate and forged part paths fail', async () => {
  for (const change of [parts => parts.pop(), parts => { parts[1] = parts[0]; }, parts => { parts[0].path = 'another object'; }]) {
    assert.equal((await inspect(fixture((n, d) => { if (n === 'unity_get_children') change(d.children); return d; }))).status, 'FAIL');
  }
});
test('nonfinite transforms, strings, zero scales and ambiguous paths fail validation', () => {
  for (const change of [p => { p.position.x = NaN; }, p => { p.rotation.y = Infinity; }, p => { p.scale.z = 0; }, p => { p.scale.x = -.1; }, p => { p.position.x = '1'; }]) {
    const reply = pose(MODEL); change(reply.matches[0]); assert.throws(() => checkPose(reply, MODEL));
  }
  assert.throws(() => checkPose({ matchCount: 2, matches: [pose(MODEL).matches[0], pose(MODEL).matches[0]] }, MODEL));
  assert.throws(() => checkPose(pose('wrong'), MODEL));
});
test('inactive individual parts are recorded, not misreported as missing geometry', async () => {
  const result = await inspect(fixture((n, d) => { if (n === 'unity_get_world_pose' && d.matches[0].path !== MODEL) d.matches[0].active = false; return d; }));
  assert.equal(result.status, 'PASS'); assert.equal(result.poses[1].active, false);
});
test('SDK isError:false timeout text cannot masquerade as JSON success', () => {
  assert.throws(() => decode({ isError: false, content: [{ type: 'text', text: 'Error: External tool callback timed out waiting for main thread' }] }));
  assert.throws(() => decode({ isError: true, content: [] }));
  assert.throws(() => focused({ state: { name: 'XR_SESSION_STATE_FOCUSED' } }));
});
test('pending capture consent blocks without saving or retrying', async () => {
  let saved = 0;
  const client = fixture((n, d) => n === 'openxr_capture_composited_image' ? { content: [{ type: 'text', text: 'Permission pending' }] } : d);
  const report = await inspect(client, { capture: true, saveCapture: () => saved++ });
  assert.equal(report.status, 'BLOCKED'); assert.equal(saved, 0);
  assert.equal(client.calls.filter(c => c.name === 'openxr_capture_composited_image').length, 1);
});
test('bad image encoding, wrong MIME, and invalid PNG dimensions fail', () => {
  for (const change of [i => { i.data = '!!!!'; }, i => { i.mimeType = 'text/html'; }, i => { i.data = Buffer.alloc(30).toString('base64'); }]) {
    const result = image(); change(result.content[0]); assert.throws(() => captureBytes(result));
  }
  const result = image(); const bytes = Buffer.from(png); bytes.writeUInt32BE(0, 16); result.content[0].data = bytes.toString('base64');
  assert.throws(() => captureBytes(result));
});

function fakeProcess(handler) {
  const proc = new EventEmitter(); proc.stdin = new PassThrough(); proc.stdout = new PassThrough(); proc.stderr = new PassThrough(); proc.exitCode = null;
  proc.kill = () => { proc.exitCode = 0; proc.emit('exit', 0); };
  let buffer = '';
  proc.stdin.on('data', bytes => { buffer += bytes; let end; while ((end = buffer.indexOf('\n')) >= 0) {
    const request = JSON.parse(buffer.slice(0, end)); buffer = buffer.slice(end + 1);
    handler(request, reply => proc.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: request.id, ...reply }) + '\n'));
  } });
  return proc;
}
test('client refuses writes before sending any tool call', async () => {
  const sent = []; const proc = fakeProcess(request => sent.push(request));
  const client = new McpClient('/fake', { spawnProcess: () => proc });
  try { await assert.rejects(client.call('openxr_set_controller_input', { value: 1 }), /refused/); assert.equal(sent.length, 0); }
  finally { client.stop(); }
});
test('connection requires an online backend and its expected tools', async () => {
  for (const list of [{ _meta: { serverStatus: 'offline' }, tools: READ_TOOLS.map(name => ({ name })) }, { _meta: { serverStatus: 'online' }, tools: [] }]) {
    const proc = fakeProcess((r, send) => { if (r.id) send({ result: r.method === 'tools/list' ? list : {} }); });
    const client = new McpClient('/fake', { spawnProcess: () => proc });
    try { await assert.rejects(client.connect(false)); } finally { client.stop(); }
  }
});
test('timeout closes proxy and rejects pending work without retries', async () => {
  let sent = 0; const proc = fakeProcess(() => sent++);
  const client = new McpClient('/fake', { spawnProcess: () => proc, timeoutMs: 10 });
  await assert.rejects(client.call('openxr_get_session_info'), /timed out/);
  assert.equal(client.closed, true); assert.equal(sent, 1); assert.equal(proc.exitCode, 0);
});
test('proxy startup errors and JSON-RPC errors are blocked', async () => {
  for (const mode of ['startup', 'rpc']) {
    const proc = fakeProcess((r, send) => { if (mode === 'rpc') send({ error: { code: -32000 } }); });
    const client = new McpClient('/fake', { spawnProcess: () => proc });
    const promise = assert.rejects(client.call('openxr_get_session_info'));
    if (mode === 'startup') proc.emit('error', Error('spawn failed'));
    await promise; client.stop();
  }
});

test('transport handles fragmented replies, startup banners, and notifications', async () => {
  const proc = fakeProcess(request => {
    const wire = JSON.stringify({ jsonrpc: '2.0', id: request.id, result: wrapped(session('82')) }) + '\n';
    proc.stdout.write('Vendor startup banner\n{"jsonrpc":"2.0","method":"notifications/tools/list_changed"}\n');
    proc.stdout.write(wire.slice(0, 19)); proc.stdout.write(wire.slice(19));
  });
  const client = new McpClient('/fake', { spawnProcess: () => proc });
  try { assert.equal(focused(decode(await client.call('openxr_get_session_info'))), '82'); }
  finally { client.stop(); }
});
test('vendor process receives only explicitly permitted environment names', () => {
  const proc = fakeProcess(() => {});
  const client = new McpClient('/fake', { spawnProcess: (exe, args, options) => {
    assert.equal(exe, '/fake'); assert.deepEqual(args, []);
    assert.ok(Object.keys(options.env).every(key => ['PATH', 'HOME', 'TMPDIR', 'LANG', 'SystemRoot'].includes(key)));
    return proc;
  } });
  client.stop();
});
