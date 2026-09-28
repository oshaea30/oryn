#!/usr/bin/env node
'use strict';

// Development-only action test. Operator remains read-only; Unity's existing
// command bridge owns action validation. No controller injection or paid APIs.
const { execFile } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { McpClient, InspectionError, inspect } = require('./xr_inspection.cjs');
const MODEL = 'Oryn 39-part model 1';
const LIMITS = Object.freeze({ position: .003, rotationDegrees: .2, scaleAbsolute: .00001, scaleRelative: .0001 });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const blocked = message => { throw new InspectionError(message); };
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

function quaternion(euler) {
  const multiply = (a, b) => [a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],
    a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],
    a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],
    a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];
  const [x,y,z] = ['x','y','z'].map(axis => euler[axis]*Math.PI/360);
  // Unity Euler angles use Z then X then Y, including wraparound/gimbal aliases.
  return multiply(multiply([0,Math.sin(y),0,Math.cos(y)], [Math.sin(x),0,0,Math.cos(x)]), [0,0,Math.sin(z),Math.cos(z)]);
}
function angle(a, b) {
  const qa = quaternion(a), qb = quaternion(b);
  return 2*Math.acos(Math.min(1, Math.abs(qa.reduce((n,v,i) => n+v*qb[i], 0))))*180/Math.PI;
}
function scaleMatches(a, b) {
  return ['x','y','z'].every(axis => Math.abs(a[axis]-b[axis]) <= LIMITS.scaleAbsolute+LIMITS.scaleRelative*Math.abs(a[axis]));
}
function samePose(a, b) {
  return a.active === b.active && distance(a.position,b.position) <= LIMITS.position &&
    angle(a.rotation,b.rotation) <= LIMITS.rotationDegrees && scaleMatches(a.scale,b.scale);
}
function compare(baseline, observed, factor) {
  const before = baseline.poses, after = new Map(observed.poses.map(p => [p.path,p]));
  if (!after.has(before[0].path) || !samePose(before[0], after.get(before[0].path))) blocked('Assembly root moved during the test; results are not attributable to the command alone.');
  const failures = [];
  let maxPositionError = 0, maxRotationError = 0, moved = 0;
  for (const home of before.slice(1)) {
    const actual = after.get(home.path), expected = { ...home, position: {} };
    for (const axis of ['x','y','z']) expected.position[axis] = before[0].position[axis] + factor*(home.position[axis]-before[0].position[axis]);
    const positionError = distance(expected.position,actual.position), rotationError = angle(home.rotation,actual.rotation);
    maxPositionError = Math.max(maxPositionError,positionError); maxRotationError = Math.max(maxRotationError,rotationError);
    if (distance(home.position,actual.position) > LIMITS.position) moved++;
    if (!samePose(expected,actual)) failures.push(home.path);
  }
  return { status: failures.length || (factor > 1 && !moved) ? 'FAIL' : 'PASS', factor,
    partsChecked: before.length-1, activeParts: observed.poses.slice(1).filter(p=>p.active).map(p=>p.path),
    movedParts: moved, maxPositionError, maxRotationErrorDegrees: maxRotationError, failures };
}

class UsbBridge {
  constructor(python) { this.python = python; }
  request(request) {
    return new Promise((resolve,reject) => {
      const env = Object.fromEntries(['PATH','HOME','TMPDIR','LANG','SystemRoot'].filter(k => process.env[k] !== undefined).map(k => [k,process.env[k]]));
      env.PYTHONDONTWRITEBYTECODE = '1';
      const child = execFile(this.python, [path.join(__dirname,'xr_command_bridge.py')],
        { timeout: 25000, maxBuffer: 128*1024, env }, (error,stdout) => {
          if (error) return reject(new InspectionError('USB adapter timed out or failed. Any dispatched command has an unknown outcome; do not resend.'));
          try {
            const value = JSON.parse(stdout);
            if (value.error) return reject(new InspectionError(value.error));
            resolve(value);
          } catch { reject(new InspectionError('Invalid USB adapter reply; do not resend an action.')); }
        });
      child.stdin.on('error', () => {}); child.stdin.end(JSON.stringify(request));
    });
  }
}

function compareIsolation(baseline, observed, targetPath) {
  const active = observed.partStates.filter(p=>p.active).map(p=>p.path);
  const target = observed.poses.find(p=>p.path===targetPath);
  const subset = {...baseline,poses:baseline.poses.filter(p=>p.path===baseline.poses[0].path || (target && p.path===targetPath))};
  const geometry = compare(subset,observed,1);
  const correct = active.length===1 && active[0]===targetPath && !!target;
  return {...geometry,status:correct && geometry.status==='PASS'?'PASS':'FAIL',activeParts:active,
    activeFlagsChecked:observed.partStates.length,hiddenTransforms:'NOT_OBSERVED',
    targetTransform:target?'CHECKED':'UNAVAILABLE',
    failures:[...geometry.failures,...(correct?[]:['Expected only '+targetPath+' active'])]};
}

function validateState(value, initial, mode, now = Date.now(), selected = '', isolated = false, owner = 1) {
  const s = value?.state, c = s?.context;
  if (c?.ready === false) blocked('ORYN reports busy: release all objects/gestures and keep the app focused. No further action sent.');
  if (c?.partsMode === !mode || c?.isolated !== isolated || c?.selectedPartId !== selected)
    blocked('Unexpected parts mode, isolation or selection for this test phase. No automatic reset performed.');
  const hex = (v,n) => typeof v === 'string' && new RegExp(`^[a-f0-9]{${n}}$`).test(v);
  if (typeof value?.serial !== 'string' || !/^[A-Za-z0-9._:-]{1,100}$/.test(value.serial) || s?.schema !== 1 ||
      !hex(s?.session,32) || !hex(s?.contextToken,32) || !Number.isInteger(s?.utc) || now/1000-s.utc > 10 || now/1000-s.utc < -3 ||
      c?.ready !== true || c.owner !== owner || !hex(c.assetSha256,64) || c.partsMode !== mode || c.isolated !== isolated || c.selectedPartId !== selected ||
      !Array.isArray(c.parts) || c.parts.length !== 39 || new Set(c.parts.map(p=>p.partId)).size !== 39 ||
      c.parts.some(p=>!hex(p.partId,64)) || new Set(c.parts.map(p=>p.number)).size !== 39 ||
      c.parts.some(p=>!Number.isInteger(p.number) || p.number<1 || p.number>39)) {
    blocked('Requires a fresh, ready, whole-selected 39-part drone (owner '+owner+'), in the expected assembled/exploded mode. Release hands and close Meta menus.');
  }
  if (initial) {
    const base = initial.state;
    if (value.serial !== initial.serial || s.session !== base.session || c.assetSha256 !== base.context.assetSha256 ||
        JSON.stringify(c.parts) !== JSON.stringify(base.context.parts)) blocked('Device, session, asset, or part records changed; stopping.');
  }
  return value;
}

async function runAssemblyTest({ client, bridge, execute = false, test = 'spread', targetNumber = 1, owner = 1, expectedAssetHash = null, wait = sleep, now = Date.now, progress = () => {}, save = () => {} }) {
  const model = 'Oryn 39-part model '+owner;
  const report = { schema: 1, status: 'BLOCKED', startedAt: new Date(now()).toISOString(),
    test, owner, expectedAssetHash, scope: 'Command-level assembly regression; active flags are not rendered visibility. Not gestures, visuals, collisions, or semantic identity.',
    limits: LIMITS, actions: [], snapshots: {}, checks: [], recovery: 'No action dispatched.' };
  const started = now();
  const budget = () => { if (now()-started > 150000) blocked('Test exceeded its 150-second budget. No further commands will be sent.'); };
  const usb = async request => { budget(); return bridge.request(request); };
  let initial, xrSession;
  const observe = async (phase, mode, selected = '', isolated = false) => {
    await progress('Inspecting '+phase);
    const before = validateState(await usb({ operation:'snapshot' }),initial,mode,now(),selected,isolated,owner);
    if (expectedAssetHash && before.state.context.assetSha256 !== expectedAssetHash) blocked('Selected asset does not match the manifest-bound test target. No action sent.');
    const snapshot = await inspect({ connect:async()=>{}, call:(...args)=>{budget();return client.call(...args);} },{activeTransformsOnly:isolated,model});
    report.snapshots[phase] = snapshot;
    if (snapshot.status !== 'PASS') throw new InspectionError(snapshot.message, snapshot.status);
    if (xrSession && snapshot.session !== xrSession) blocked('Operator session changed across test phases.');
    xrSession = snapshot.session;
    if (phase === 'baseline' && snapshot.poses.some(p=>!p.active)) blocked('All fixture parts must initially be active.');
    const after = validateState(await usb({ operation:'snapshot' }),initial,mode,now(),selected,isolated,owner);
    if (before.state.contextToken !== after.state.contextToken || before.state.session !== after.state.session || JSON.stringify(before.state.context)!==JSON.stringify(after.state.context))
      blocked('Workspace changed during position sampling; stopping.');
    if (!initial) initial = after;
    return after;
  };
  const apply = async (action, expected, partId = '') => {
    await progress('Sending '+action+' once');
    const entry = { action, partId, id:randomUUID().replaceAll('-',''), status:'dispatching' };
    report.actions.push(entry); report.recovery = 'Action may be pending. Do not resend; inspect receipt and current headset state.';
    await save(report); // Durable command ID before any transport mutation.
    const response = await usb({ operation:'apply', action, partId, id:entry.id, serial:expected.serial, expected:expected.state });
    entry.status = response.status;
    await save(report);
    if (entry.status !== 'waiting') blocked('Command transfer outcome is uncertain. No automatic retry or cleanup command.');
    for (let poll=0; poll<12; poll++) {
      const receipt = await usb({ operation:'receipt', serial:expected.serial, id:entry.id });
      entry.status = receipt.status;
      if (entry.status === 'executed') { await wait(600); return; }
      if (entry.status !== 'waiting') blocked('Quest rejected the command or could not confirm execution. No retry.');
      await wait(500);
    }
    blocked('No execution receipt within the poll limit. Command may still execute before expiry; do not resend.');
  };
  try {
    if (!execute) blocked('Pass --execute to authorize one test cycle. No device commands sent.');
    if (!Number.isInteger(owner) || owner < 1 || owner > 100000 || (expectedAssetHash !== null && !/^[a-f0-9]{64}$/.test(expectedAssetHash))) blocked('Invalid explicit assembly identity.');
    if (!['spread','isolation'].includes(test) || !Number.isInteger(targetNumber) || targetNumber < 1 || targetNumber > 39)
      blocked('Unsupported test or fixture part number.');
    await client.connect(false);
    const baselineState = await observe('baseline',false);
    report.checks.push({ name:'Assembled fixture and focused stable context', status:'PASS' });
    let restoreState;
    if (test === 'spread') {
      await apply('explode',baselineState);
      report.recovery = 'Explosion executed; reassembly not yet verified.';
      restoreState = await observe('exploded',true);
      report.checks.push({ name:'All parts match 2.1x radial spread; root unchanged', ...compare(report.snapshots.baseline,report.snapshots.exploded,2.1) });
    } else {
      const target = await usb({operation:'resolve',serial:baselineState.serial,expected:baselineState.state,number:targetNumber});
      const part = baselineState.state.context.parts.find(p=>p.number === targetNumber);
      if (target.partId !== part?.partId || target.number !== targetNumber || !/^island_\d{3}$/.test(target.geometryName))
        blocked('Missing or mismatched geometry binding; no selection sent.');
      const targetPath = model+'/Part '+target.geometryName;
      if (!report.snapshots.baseline.poses.some(p=>p.path === targetPath)) blocked('Bound target not found in scene; no selection sent.');
      report.target = {...target,path:targetPath};
      await apply('select',baselineState,target.partId);
      report.recovery = 'Part selection executed; whole-assembly restoration not yet verified.';
      const selectedState = await observe('selected',true,target.partId);
      report.checks.push({name:'Requested part selected; all parts remain active and unmoved',...compare(report.snapshots.baseline,report.snapshots.selected,1)});
      if (report.checks.at(-1).status === 'PASS') {
        await apply('isolate',selectedState,target.partId);
        report.recovery = 'Isolation executed; other parts may remain hidden until reassembly.';
        restoreState = await observe('isolated',true,target.partId,true);
        report.checks.push({name:'Only the bound target is active; root and target transforms unchanged',...compareIsolation(report.snapshots.baseline,report.snapshots.isolated,targetPath)});
      } else restoreState = selectedState;
    }
    // Even a geometric mismatch is followed by the planned guarded reassembly.
    // Transport, focus, identity or context uncertainty aborts without blind cleanup.
    await apply('reassemble',restoreState);
    await observe('reassembled',false);
    report.checks.push({ name:'All parts return to baseline position, rotation, scale and active state', ...compare(report.snapshots.baseline,report.snapshots.reassembled,1) });
    report.status = report.checks.every(c=>c.status === 'PASS') ? 'PASS' : 'FAIL';
    report.recovery = report.checks.at(-1).status === 'PASS' ? 'Reassembly verified against baseline.' : 'Reassembly executed but differs from baseline; inspect the scene.';
  } catch(error) {
    report.status = error instanceof InspectionError ? error.status : 'BLOCKED';
    report.message = error instanceof InspectionError ? error.message : 'Unexpected test failure; no automatic retry.';
  }
  report.finishedAt = new Date(now()).toISOString();
  await save(report); return report;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) { console.log('node Orchestrator/xr_assembly_test.cjs --execute [--test spread|isolation] [--part 1..39] [--python /absolute/python3] [--proxy /absolute/proxy]\nRequires the assembled 39-part drone, selected as a whole, ORYN focused, hands released. Spread: explode/reassemble. Isolation: select/isolate/reassemble. No paid calls.'); return; }
  let execute = false, test = 'spread', targetNumber = 1, owner = 1, expectedAssetHash = null, python = '/opt/homebrew/bin/python3', proxy = path.join(os.homedir(),'meta-xr-operator','meta-xr-operator-mcp-proxy');
  for (let i=0;i<args.length;i++) {
    if (args[i] === '--execute') execute = true;
    else if (args[i] === '--test' && args[i+1]) test=args[++i];
    else if (args[i] === '--part' && args[i+1]) targetNumber=Number(args[++i]);
    else if (args[i] === '--owner' && args[i+1]) owner=Number(args[++i]);
    else if (args[i] === '--asset-sha256' && args[i+1]) expectedAssetHash=args[++i];
    else if (args[i] === '--python' && args[i+1]) python=args[++i];
    else if (args[i] === '--proxy' && args[i+1]) proxy=args[++i];
    else blocked('Unknown or incomplete argument; use --help.');
  }
  if (!execute) blocked('No action authorized. Use --execute for the explicit test cycle.');
  for (const executable of [python,proxy]) if (!path.isAbsolute(executable) || !fs.existsSync(executable)) blocked('Provide installed absolute Python/proxy paths.');
  const root = path.resolve(__dirname,'..','.oryn-inspection');
  if (fs.existsSync(root) && (fs.lstatSync(root).isSymbolicLink() || !fs.lstatSync(root).isDirectory())) blocked('Inspection output root must be a real directory.');
  fs.mkdirSync(root,{ recursive:true,mode:0o700 });
  const folder = fs.mkdtempSync(path.join(root,'assembly-')), filename = path.join(folder,'report.json');
  const save = report => {
    const temporary = path.join(folder,'report.partial');
    fs.writeFileSync(temporary,JSON.stringify(report,null,2)+'\n',{mode:0o600}); fs.renameSync(temporary,filename);
  };
  const client = new McpClient(proxy);
  let report;
  try { report = await runAssemblyTest({client,bridge:new UsbBridge(python),execute,test,targetNumber,owner,expectedAssetHash,save,progress:message=>console.log(message)}); }
  finally {client.stop();}
  console.log(JSON.stringify({status:report.status,checks:report.checks,actions:report.actions,message:report.message,recovery:report.recovery,report:filename},null,2));
  process.exitCode = report.status === 'PASS' ? 0 : report.status === 'FAIL' ? 1 : 2;
}
if (require.main === module) main().catch(error=>{console.error(error instanceof InspectionError?error.message:'Assembly test unavailable.');process.exitCode=2;});
module.exports = { runAssemblyTest, compare, angle, validateState, UsbBridge, MODEL, LIMITS };
