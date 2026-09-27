'use strict';
const el = id => document.getElementById(id);
let token = '', proposal = null, sentId = null, busy = false;
let costQuote = null;
const dollars = nanos => '$'+(nanos/1e9).toFixed(6);
el('paid').disabled = true;
el('quote').disabled = true;
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {cache:'no-store'} : {method:'POST', headers:{'Content-Type':'application/json','X-Oryn-Token':token}, body:JSON.stringify(data)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Request failed.');
  return value;
}
function invalidate() { proposal = null; el('apply').disabled = true; }
function clearQuote() { costQuote = null; el('paid').checked = false; el('paid').disabled = true; el('quoteDetails').textContent = 'Prepare a new quote before any paid request.'; }
function setBusy(value) { busy=value; ['ask','question','provider','profile','configure','clear'].forEach(id=>el(id).disabled=value); el('quote').disabled=value || el('provider').value!=='openai'; }
async function refreshBudget() {
  try {
    const b = await api('/api/budget');
    el('budget').textContent = `${b.halted ? 'HALTED — operator review required\n' : ''}${b.day} / UTC\nDaily ceiling: ${dollars(b.daily_limit_nanos)}\nCharged + reserved: ${dollars(b.charged_and_reserved_nanos)}\nRemaining: ${dollars(b.remaining_nanos)}`;
    el('usageHistory').textContent = b.recent.map(r=>`${r.request_id.slice(0,8)} · ${r.model} / ${r.effort}\n${r.status} · reserved ${dollars(r.reserved_nanos)}${r.calculated_cost_nanos===null ? '' : ' · calculated '+dollars(r.calculated_cost_nanos)}`).join('\n');
  } catch(error) { el('budget').textContent=error.message; }
}
async function refresh() {
  try {
    const value = await api('/api/state'), s = value.state, c = s.context;
    if (proposal && (proposal.session !== s.session || proposal.token !== s.contextToken)) invalidate();
    if (costQuote && (costQuote.session !== s.session || costQuote.token !== s.contextToken)) clearQuote();
    el('connection').textContent = c.ready ? 'Connected / ready' : 'Connected / open ORYN and release objects';
    const p = c.parts.find(x => x.partId === c.selectedPartId);
    el('context').textContent = `Assembly instance: ${c.owner || 'none'} · geometric parts: ${c.parts.length}\nMode: ${c.isolated ? 'isolated' : c.partsMode ? 'parts' : 'whole'}\nSelected: ${p ? 'Part '+p.number : 'whole assembly / none'}\nLabel: ${p ? (p.error || p.label || 'unidentified') : '—'}${p && p.label ? ' · user annotation · unverified · revision '+p.revision : ''}`;
    return s;
  } catch(error) { invalidate(); el('connection').textContent = error.message; throw error; }
}
el('refresh').onclick = () => refresh().catch(()=>{});
el('provider').onchange = () => {
  invalidate(); clearQuote(); setBusy(false);
  el('mode').textContent = el('provider').value === 'offline' ? 'No provider calls. Tests the real knowledge lookup and Quest action path.' : el('provider').value === 'gemini' ? 'BLOCKED — Gemini does not yet have a reviewed spending policy.' : 'Prepare a token-count quote, approve its exact maximum, then interpret. No automatic escalation.';
};
el('profile').onchange = () => { invalidate(); clearQuote(); };
document.querySelectorAll('[data-question]').forEach(button => button.onclick = () => { if(busy)return; el('question').value = button.dataset.question; invalidate(); clearQuote(); });
el('question').oninput = () => { invalidate(); clearQuote(); };
el('refreshBudget').onclick = refreshBudget;
el('quote').onclick = async () => {
  if(busy)return;
  clearQuote(); invalidate(); setBusy(true);
  try {
    const state=await refresh();
    const q=await api('/api/quote',{provider:el('provider').value,profile:el('profile').value,question:el('question').value,approveCount:true});
    costQuote={...q,session:state.session,token:state.contextToken};
    el('quoteDetails').textContent=`Model: ${q.model}\nEffort: ${q.effort}\nExact input: ${q.input_tokens} tokens\nMaximum output (including reasoning): ${q.max_output_tokens}\nWorst-case authorized cost: ${dollars(q.reserved_nanos)}\nProfile ceiling: ${dollars(q.ceiling_nanos)}\nDaily remaining: ${dollars(q.daily_remaining_nanos)}\nExpires: ${new Date(q.expires*1000).toLocaleTimeString()}\n${q.note}`;
    el('paid').disabled=false;
  } catch(error) { el('quoteDetails').textContent=error.message; }
  finally { setBusy(false); refreshBudget(); }
};
el('ask').onclick = async () => {
  if (busy) return;
  setBusy(true); invalidate(); el('receipt').textContent = '';
  el('requestStatus').textContent = 'Reading the current headset context…';
  try {
    const state = await refresh();
    const paid=el('provider').value!=='offline';
    if(paid && (!costQuote || !el('paid').checked)) throw new Error('Prepare and explicitly approve a cost quote first.');
    const data = {id:paid ? costQuote.request_id : crypto.randomUUID().replaceAll('-',''), question:el('question').value, provider:el('provider').value, profile:el('profile').value, approvePaid:el('paid').checked, approvedCostNanos:paid ? costQuote.reserved_nanos : 0};
    el('paid').checked = false;
    clearQuote();
    el('requestStatus').textContent = data.provider === 'offline' ? 'Running offline test…' : 'Waiting for provider. No automatic retry.';
    const result = await api('/api/ask', data);
    el('answer').textContent = result.answer;
    el('attribution').textContent = `Interpreter: ${result.provider}${result.model ? ' / '+result.model : ''}. Answer and action validation: ORYN.`;
    if (result.action) { proposal = {id:result.id, session:state.session, token:state.contextToken}; el('apply').disabled = false; el('apply').textContent = 'Confirm: '+result.action+' on Quest'; }
    el('requestStatus').textContent = result.action ? 'Proposal only — nothing has moved yet.' : 'Finished — no headset action.';
  } catch(error) { el('requestStatus').textContent = error.message; }
  finally { setBusy(false); refreshBudget(); }
};
async function receipt() {
  if (!sentId) return;
  try { const result = await api('/api/receipt/'+sentId); el('receipt').textContent = result.status.toUpperCase()+': '+result.message; }
  catch(error) { el('receipt').textContent = error.message; }
}
el('apply').onclick = async () => {
  if (!proposal) return;
  const id = proposal.id; invalidate(); sentId = id; el('checkReceipt').disabled = false;
  try { const result = await api('/api/apply', {id}); el('receipt').textContent = result.status.toUpperCase()+': '+result.message; setTimeout(receipt,1500); }
  catch(error) { el('receipt').textContent = error.message; }
};
el('checkReceipt').onclick = receipt;
el('configure').onclick = async () => {
  const data = {provider:el('provider').value, profile:el('profile').value, key:el('key').value}; el('key').value = ''; clearQuote();
  try { el('configStatus').textContent = (await api('/api/configure',data)).message; }
  catch(error) { el('configStatus').textContent = error.message; }
};
el('clear').onclick = async () => {
  clearQuote();
  try { el('configStatus').textContent = (await api('/api/configure',{provider:el('provider').value,clear:true})).message; }
  catch(error) { el('configStatus').textContent = error.message; }
};
api('/api/session').then(value => {token = value.token; refreshBudget(); return refresh();}).catch(error => {el('connection').textContent=error.message;});
