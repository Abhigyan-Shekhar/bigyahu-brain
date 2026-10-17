'use strict';
const token = location.hash.slice(1);
history.replaceState(null, '', '/');
const status = document.querySelector('#status');
const details = document.querySelector('#details');
const svg = document.querySelector('#graph');
const ns = 'http://www.w3.org/2000/svg';
async function api(path) {
  const response = await fetch(path, {headers: {Authorization: 'Bearer '+token}});
  const result = await response.json();
  if (!response.ok) throw new Error((result.warnings || ['Access unavailable; reopen the launch URL or refresh the projection.']).join(', '));
  return result;
}
function element(name, attrs, text) {
  const e = document.createElementNS(ns,name);
  for (const [key,value] of Object.entries(attrs)) e.setAttribute(key,value);
  if (text !== undefined) e.textContent = text;
  return e;
}
function show(node, graph) {
  details.replaceChildren();
  const heading = document.createElement('h2');
  heading.textContent = node.name || node.record_uid || node.kind;
  details.append(heading);
  const body = document.createElement('pre');
  if (node.kind === 'Person') {
    const ids = new Set(graph.edges.filter(e => e.source===node.uid && e.relation==='AUTHORED').map(e => e.target));
    const memories = graph.nodes.filter(n=>ids.has(n.uid));
    body.textContent = memories.map(n=>n.brain+'\n'+n.text).join('\n\n') || 'No authored memory in these authorized scopes.';
  } else body.textContent = JSON.stringify(node,null,2);
  details.append(body);
}
function render(graph) {
  svg.replaceChildren(); details.replaceChildren();
  const brains = [...new Set(graph.nodes.map(n=>n.brain))].sort();
  const order = ['Brain','Team','Person','Memory','Entity','Source','CompanyDocument','CompanyConceptMention','CompanySymbol','CompanyFile','CompanySource','Version'];
  const positions = new Map();
  for (const [col,brain] of brains.entries()) {
    const x = 35 + col*1060/Math.max(1,brains.length);
    svg.append(element('text',{x,y:26},brain));
    const nodes = graph.nodes.filter(n=>n.brain===brain).sort((a,b)=>order.indexOf(a.kind)-order.indexOf(b.kind)||a.uid.localeCompare(b.uid));
    nodes.forEach((n,row)=>positions.set(n.uid, [x+8, 65+row*590/Math.max(1,nodes.length)]));
  }
  for (const edge of graph.edges) {
    const a=positions.get(edge.source),b=positions.get(edge.target);
    if (!a || !b) continue;
    const line=element('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1]});
    line.append(element('title',{},edge.relation));svg.append(line);
  }
  for (const node of graph.nodes) {
    const [x,y]=positions.get(node.uid);
    const group=element('g',{tabindex:0,role:'button','aria-label':node.kind+': '+(node.name || node.record_uid || node.path || node.kind)});
    group.append(element('circle',{cx:x,cy:y,r:8,fill:node.kind==='Person'?'#9a753b':node.kind==='Memory'?'#397c60':'#365866'}));
    group.append(element('text',{x:x+12,y:y+4},(node.kind+': '+(node.name || node.record_uid || node.path || node.kind)).slice(0,36)));
    group.append(element('title',{},node.kind+' · '+node.brain));
    group.addEventListener('click',()=>show(node,graph));
    group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show(node,graph);}});
    svg.append(group);
  }
  status.textContent = graph.nodes.length+' visible nodes · '+graph.edges.length+' relationships · Evidence requires judgment';
}
document.querySelector('#scopes').addEventListener('submit',async event=>{
  event.preventDefault();svg.replaceChildren();details.replaceChildren();status.textContent='Checking current permissions…';
  const params=new URLSearchParams();
  for(const box of document.querySelectorAll('input[name=brain]:checked')) params.append('brain',box.value);
  if(document.querySelector('#company').checked) params.set('company','true');
  try{render(await api('/api/graph?'+params));}catch(error){status.textContent=error.message;}
});
(async()=>{try{
  const context=await api('/api/brains');
  document.querySelector('#identity').textContent='Viewing as '+context.principal;
  for(const brain of context.brains){
    const label=document.createElement('label'),box=document.createElement('input');
    box.type='checkbox';box.name='brain';box.value=brain;box.checked=brain.startsWith('private:');
    label.append(box,document.createTextNode(' '+brain));document.querySelector('#brains').append(label);
  }
  status.textContent='Select scopes to explore.';
}catch(error){status.textContent=error.message;}})();
