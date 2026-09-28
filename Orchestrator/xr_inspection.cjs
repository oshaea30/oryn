#!/usr/bin/env node
'use strict';

// Development-only observer: no device setup, input injection, or paid providers.
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const READ_TOOLS = Object.freeze(['openxr_get_session_info', 'openxr_get_instance_info',
  'unity_get_scene_root_objects', 'unity_get_children', 'unity_get_world_pose', 'openxr_capture_composited_image']);
const MAX_REPLY = 16 * 1024 * 1024;
class InspectionError extends Error {
  constructor(message, status = 'BLOCKED') { super(message); this.status = status; }
}
function check(condition, message) {
  if (!condition) throw new InspectionError(message, 'FAIL');
}

class McpClient {
  constructor(executable, { spawnProcess = spawn, timeoutMs = 15000 } = {}) {
    this.timeoutMs = timeoutMs; this.nextId = 1; this.pending = new Map(); this.closed = false; this.buffer = '';
    // Do not inherit provider API keys into the vendor process.
    const env = Object.fromEntries(['PATH', 'HOME', 'TMPDIR', 'LANG', 'SystemRoot']
      .filter(key => process.env[key] !== undefined).map(key => [key, process.env[key]]));
    this.process = spawnProcess(executable, [], { stdio: ['pipe', 'pipe', 'pipe'], env });
    this.process.stderr.resume(); // The vendor proxy manages its own diagnostics.
    this.process.on('error', () => this.stop('MCP proxy could not start. Check its installation.'));
    this.process.on('exit', () => this.stop('MCP proxy exited. No inspection result is implied.'));
    this.process.stdin.on('error', () => this.stop('MCP input stream closed.'));
    this.process.stdout.setEncoding('utf8');
    this.process.stdout.on('data', chunk => {
      this.buffer += chunk;
      if (Buffer.byteLength(this.buffer) > MAX_REPLY) { this.stop('MCP response exceeded the size limit.'); return; }
      let end;
      while ((end = this.buffer.indexOf('\n')) >= 0) {
        const line = this.buffer.slice(0, end); this.buffer = this.buffer.slice(end + 1);
        let reply;
        try { reply = JSON.parse(line); } catch { continue; } // Ignore startup banners.
        const waiting = this.pending.get(reply?.id);
        if (!waiting) continue;
        this.pending.delete(reply.id); clearTimeout(waiting.timer);
        if (reply.error || !Object.hasOwn(reply, 'result')) waiting.reject(new InspectionError('MCP request returned an error.'));
        else waiting.resolve(reply.result);
      }
    });
  }
  rpc(method, params) {
    if (this.closed) return Promise.reject(new InspectionError('MCP connection is closed.'));
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.stop('MCP request timed out; open ORYN and keep the Quest awake.'), this.timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.process.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
    });
  }
  async connect(capture) {
    await this.rpc('initialize', { protocolVersion: '2024-11-05', capabilities: {},
      clientInfo: { name: 'oryn-read-only-inspection', version: '1.0' } });
    this.process.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
    const list = await this.rpc('tools/list', {});
    if (list?._meta?.serverStatus !== 'online') throw new InspectionError('Operator backend is not online. Check ORYN and USB forwarding.');
    const names = new Set((list.tools || []).map(tool => tool.name));
    for (const name of READ_TOOLS.filter(name => capture || name !== 'openxr_capture_composited_image')) {
      if (!names.has(name)) throw new InspectionError('Required inspection tool unavailable: ' + name);
    }
  }
  call(name, args = {}) {
    if (!READ_TOOLS.includes(name)) return Promise.reject(new InspectionError('Write or unknown tool refused: ' + name));
    return this.rpc('tools/call', { name, arguments: args });
  }
  stop(message = 'Inspection connection closed.') {
    if (this.closed) return;
    this.closed = true;
    for (const { reject, timer } of this.pending.values()) { clearTimeout(timer); reject(new InspectionError(message)); }
    this.pending.clear(); this.buffer = '';
    this.process.stdin.end(); this.process.kill('SIGTERM');
    const timer = setTimeout(() => { if (this.process.exitCode === null) this.process.kill('SIGKILL'); }, 1000);
    timer.unref();
  }
}

function decode(result) {
  if (result?.isError) throw new InspectionError('Operator reported a tool error.');
  const content = result?.content;
  if (!Array.isArray(content) || content.length !== 1 || content[0].type !== 'text') throw new InspectionError('Unexpected Operator response format.');
  // v205 can return main-thread timeouts with isError:false. Require actual JSON.
  try { return JSON.parse(content[0].text); }
  catch { throw new InspectionError('Operator returned non-JSON text (possibly paused or waiting for permission).'); }
}
function focused(session) {
  if (session?.state?.name !== 'XR_SESSION_STATE_FOCUSED') throw new InspectionError('Quest is not focused on ORYN. Wear it, dismiss system dialogs, and open ORYN.');
  if (!session?.session?.handle) throw new InspectionError('No active XR session handle.');
  return session.session.handle;
}
function checkPose(reply, expectedPath) {
  check(reply?.matchCount === 1 && reply.matches?.length === 1, 'Missing or ambiguous transform: ' + expectedPath);
  const pose = reply.matches[0];
  check(pose.path === expectedPath, 'Transform path mismatch.');
  for (const field of ['position', 'rotation', 'scale']) {
    check(['x', 'y', 'z'].every(axis => typeof pose[field]?.[axis] === 'number' && Number.isFinite(pose[field][axis])), 'Invalid ' + field + ': ' + expectedPath);
  }
  check(['x', 'y', 'z'].every(axis => pose.scale[axis] > 0), 'Non-positive scale: ' + expectedPath);
  check(typeof pose.active === 'boolean', 'Invalid active state: ' + expectedPath);
  return pose;
}
function captureBytes(result) {
  if (result?.isError) throw new InspectionError('Screenshot capture failed.');
  const content = result?.content;
  if (!Array.isArray(content) || content.length !== 1 || content[0].type !== 'image') throw new InspectionError('Screenshot unavailable. Approve the capture dialog in the headset and rerun.');
  const item = content[0];
  check(item.mimeType === 'image/png' && typeof item.data === 'string' && item.data.length <= 12 * 1024 * 1024 &&
    item.data.length % 4 === 0 && !/[^A-Za-z0-9+/=]/.test(item.data), 'Invalid or oversized PNG capture.');
  const bytes = Buffer.from(item.data, 'base64');
  check(bytes.toString('base64') === item.data && bytes.length >= 24 &&
    bytes.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex')) && bytes.toString('ascii', 12, 16) === 'IHDR' &&
    bytes.readUInt32BE(16) > 0 && bytes.readUInt32BE(20) > 0, 'Capture lacks a valid PNG header and dimensions.');
  return bytes;
}

async function inspect(client, { capture = false, model = 'Oryn 39-part model 1', expectedParts = 39, saveCapture, activeTransformsOnly = false } = {}) {
  const report = { schema: 1, startedAt: new Date().toISOString(), status: 'BLOCKED', checks: [],
    capture: { status: capture ? 'NOT_RUN' : 'NOT_REQUESTED' },
    scope: 'Read-only structural observations, not interaction, semantics, reachability, or visual-quality validation.' };
  const pass = name => report.checks.push({ name, status: 'PASS' });
  const query = async (name, args) => decode(await client.call(name, args));
  try {
    await client.connect(capture); pass('MCP backend online and inspection tools available');
    const session = focused(await query('openxr_get_session_info'));
    report.session = session; pass('ORYN XR session focused');
    const app = await query('openxr_get_instance_info');
    check(app?.application?.name === 'Oryn Workspace' && app?.engine?.name === 'Unity', 'Connected app is not Oryn Workspace in Unity.');
    pass('Expected ORYN application');
    const roots = (await query('unity_get_scene_root_objects'))?.rootObjects;
    check(Array.isArray(roots), 'Missing scene hierarchy.');
    for (const name of ['Oryn Workspace', 'Workspace Panel', 'OVRCameraRig', 'Passthrough', model]) {
      const matches = roots.filter(root => root.name === name);
      check(matches.length === 1 && matches[0].active === true, 'Missing, inactive, or ambiguous scene root: ' + name);
    }
    pass('Workspace, UI, rig, passthrough, and model roots present');
    const children = (await query('unity_get_children', { path: model }))?.children;
    check(Array.isArray(children), 'Missing model children.');
    const parts = children.filter(child => /^Part island_\d{3}$/.test(child.name));
    const expected = new Set(Array.from({ length: expectedParts }, (_, i) => `${model}/Part island_${String(i + 1).padStart(3, '0')}`));
    check(parts.length === expectedParts && new Set(parts.map(p => p.path)).size === expectedParts &&
      parts.every(p => expected.has(p.path) && p.path === `${model}/${p.name}`), 'Unexpected, duplicate, or missing fixture part IDs.');
    report.partCount = parts.length; pass(`${expectedParts} unique expected fixture part IDs`);
    if (activeTransformsOnly) check(parts.every(p=>typeof p.active === 'boolean'), 'Missing part active flags.');
    report.partStates = parts.map(p=>({path:p.path,active:p.active}));
    report.unobservedTransforms = activeTransformsOnly ? parts.filter(p=>!p.active).map(p=>p.path) : [];
    report.poses = [];
    for (const target of [model, ...parts.filter(p=>!activeTransformsOnly || p.active).map(part => part.path)]) report.poses.push(checkPose(await query('unity_get_world_pose', { path: target }), target));
    check(report.poses[0].active, 'Model became inactive during inspection.');
    pass(activeTransformsOnly ? 'Root and active-part transforms valid; hidden transforms not observed' : 'Model and every part have finite transforms and positive scale');
    if (activeTransformsOnly) {
      const end = (await query('unity_get_children', {path:model}))?.children;
      const states = list => list.filter(p=>/^Part island_\d{3}$/.test(p.name)).map(p=>({path:p.path,active:p.active})).sort((a,b)=>a.path.localeCompare(b.path));
      if (!Array.isArray(end) || JSON.stringify(states(parts)) !== JSON.stringify(states(end)) || report.poses.slice(1).some(p=>!p.active))
        throw new InspectionError('Part active states changed during isolation sampling.');
      pass('Part active flags stable across isolation sampling');
    }
    if (capture) {
      const bytes = captureBytes(await client.call('openxr_capture_composited_image', { eye: 'left' }));
      if (typeof saveCapture !== 'function') throw new InspectionError('No local capture destination configured.');
      await saveCapture(bytes);
      report.capture = { status: 'PASS', file: 'capture.png', width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20),
        visualReview: 'NOT_AUTOMATED', note: 'Capture only; passthrough may appear black.' };
      pass('Consented screenshot returned');
    }
    const finalSession = focused(await query('openxr_get_session_info'));
    if (session !== finalSession) throw new InspectionError('XR session changed during inspection; rerun.');
    pass('Same focused XR session at completion'); report.status = 'PASS';
  } catch (error) {
    report.status = error instanceof InspectionError ? error.status : 'BLOCKED';
    report.message = error instanceof InspectionError ? error.message : 'Unexpected inspection failure; no pass recorded.';
  }
  report.finishedAt = new Date().toISOString(); return report;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log('node Orchestrator/xr_inspection.cjs [--capture] [--proxy /absolute/path]\nRequires an existing USB Operator connection and focused ORYN with its 39-part fixture.'); return;
  }
  let capture = false, proxy = path.join(os.homedir(), 'meta-xr-operator', 'meta-xr-operator-mcp-proxy');
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--capture') capture = true;
    else if (args[i] === '--proxy' && args[i + 1]) proxy = args[++i];
    else throw new InspectionError('Unknown or incomplete argument. Use --help.');
  }
  if (!path.isAbsolute(proxy) || !fs.existsSync(proxy)) throw new InspectionError('Install the bundled Operator proxy first, or provide --proxy.');
  const root = path.resolve(__dirname, '..', '.oryn-inspection');
  if (fs.existsSync(root) && (fs.lstatSync(root).isSymbolicLink() || !fs.lstatSync(root).isDirectory())) throw new InspectionError('Inspection output root must be a real local directory.');
  fs.mkdirSync(root, { recursive: true, mode: 0o700 });
  const folder = fs.mkdtempSync(path.join(root, 'run-'));
  const client = new McpClient(proxy);
  const deadline = setTimeout(() => client.stop('Inspection exceeded its two-minute run budget.'), 120000);
  let report;
  try { report = await inspect(client, { capture, saveCapture: bytes => fs.writeFileSync(path.join(folder, 'capture.png'), bytes, { flag: 'wx', mode: 0o600 }) }); }
  finally { clearTimeout(deadline); client.stop(); }
  fs.writeFileSync(path.join(folder, 'report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  console.log(JSON.stringify({ status: report.status, checksPassed: report.checks.length, partCount: report.partCount,
    capture: report.capture.status, message: report.message, report: path.join(folder, 'report.json') }, null, 2));
  process.exitCode = report.status === 'PASS' ? 0 : report.status === 'FAIL' ? 1 : 2;
}
if (require.main === module) main().catch(error => { console.error(error instanceof InspectionError ? error.message : 'Inspection failed.'); process.exitCode = 2; });
module.exports = { McpClient, InspectionError, READ_TOOLS, decode, focused, checkPose, captureBytes, inspect };
