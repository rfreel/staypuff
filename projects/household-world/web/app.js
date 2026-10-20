/* Household World dashboard. Live routes are loopback FastAPI; offline build is labeled replay only. */
'use strict';
const $ = (selector)=>document.querySelector(selector);
const $$ = (selector)=>Array.from(document.querySelectorAll(selector));
const htmlEscape = (value)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = c => '$'+(Number(c||0)/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const dec = (v,d=1) => Number(v||0).toFixed(d);
const pct = v => (100*Number(v||0)).toFixed(0)+'%';
const replay = window.__REPLAY__ || null;
let sim = null;
let busy = false;
let replayIndex=0;
let replayPolicy=0;
let comparisonCache=null;
let lastGraphNode=null;

function toast(message){const e=$('#toast');e.textContent=message;e.classList.add('visible');window.clearTimeout(toast.timer);toast.timer=window.setTimeout(()=>e.classList.remove('visible'),5000)}
async function request(path,options={}){
  if(replay) throw Error('This is an offline, recorded replay. Run the server for interactive simulation.');
  const res=await fetch('/api/'+path,{headers:{'Content-Type':'application/json'},...options});
  let payload=await res.json();
  if(!res.ok)throw Error(payload.detail||res.statusText);
  return payload;
}
function replayTimeline(){return replay.scenarios[replayPolicy]?.timeline||[]}
function setAction(value){const selected=Math.max(0,Math.min(7,parseInt(value,10)||0));$('#action').value=String(selected);if(replay&&selected!==replayPolicy){replayPolicy=selected;replayIndex=0;comparisonCache=null;sim=replayTimeline()[0];render()}}
async function advance(n){
 if(busy)return;
 if(replay){const seq=replayTimeline();replayIndex=Math.min(seq.length-1,replayIndex+n);sim=seq[replayIndex];render();return}
 busy=true;updateButtons();
 try{const action=Number($('#action').value);const payload=n===1?await request('step',{method:'POST',body:JSON.stringify({action})}):await request('run',{method:'POST',body:JSON.stringify({action,days:n})});sim=payload.state;comparisonCache=null;render()}
 catch(err){toast(err.message)}finally{busy=false;updateButtons()}
}
async function resetWorld(){if(busy)return;
 if(replay){replayIndex=0;sim=replayTimeline()[0];comparisonCache=null;render();return}
 try{sim=await request('reset',{method:'POST',body:'{}'});comparisonCache=null;render()}catch(e){toast(e.message)}
}
function updateButtons(){const ended=sim&&sim.day>=sim.horizon;$('#step').disabled=busy||ended;$('#seven').disabled=busy||ended;$('#step').innerHTML=(replay?'NEXT REPLAY DAY':'ADVANCE ONE DAY')+' <b>→</b>';$('#engineMode').textContent=replay?'SYNTHETIC / REPLAY':'SYNTHETIC / LIVE'}
function setView(name){$$('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.view===name));$$('.view').forEach(v=>v.classList.toggle('active',v.id==='view-'+name));history.replaceState(null,'','#'+name);if(name==='counterfactual'&&!comparisonCache&&sim?.day<sim?.horizon&&!replay) compare();}
function render(){if(!sim)return;
 $('#nowIndicator').textContent=`DAY ${String(sim.day).padStart(2,'0')} / ${String(sim.horizon).padStart(2,'0')}`;
 $('#seedIndicator').textContent='SEED '+String(sim.seed).padStart(4,'0');
 const m=sim.metrics||{}, b=sim.budget||{};
 const spend=money(b.spent_total_cents).split('.');$('#mSpend').innerHTML=htmlEscape(spend[0])+'<span>.'+htmlEscape(spend[1])+'</span>';
 $('#mSpendSub').textContent=`${money(b.remaining_cents)} available this week`;
 $('#mServed').innerHTML=`${m.dinner_served||0}<span>/${sim.horizon}</span>`;
 $('#mServedSub').textContent=(sim.day?dec((m.dinner_served||0)/sim.day*100,0):'0')+'% of simulated dinners served';
 $('#mWaste').innerHTML=`${(m.household_waste_g||0)>1000?dec(m.household_waste_g/1000,2):dec(m.household_waste_g,0)}<span>${m.household_waste_g>1000?'kg':'g'}</span>`;
 $('#mScore').innerHTML=dec(sim.score,1)+'<span>/100</span>';
 drawPeople();drawMeal();drawInventory();drawMarketMini();drawMarket();drawKitchen();drawBeads();drawComparison();updateButtons();
}
function drawPeople(){
 const m=sim.metrics||{},n=(m.dinner_served||0),people=sim.people||[];
 $('#peopleCards').innerHTML=people.map((p,index)=>{
   const target=(p.dinner_reference_kcal||0)*n;
   const consumed=(m.consumed_kcal||{})[p.id]||0;
   const served=(m.served_kcal||{})[p.id]||0;
   const ratio=target?consumed/target:0;
   const name=p.id==='husband'?'HUSBAND':p.id==='wife'?'WIFE':p.id==='child'?'CHILD':p.id.toUpperCase();
   return `<div class="person"><div class="person-head"><strong>${htmlEscape(name)}</strong><span class="p-type">${htmlEscape(p.role.toUpperCase())} · ${dec(p.age_years,0)} YEARS</span></div>
   <div class="person-bar"><div class="person-fill" style="width:${Math.min(100,ratio*100)}%"></div><div class="person-target" style="left:${Math.min(98,Math.max(5,target?target/(Math.max(target,served)*1.1)*100:80))}%"></div></div>
   <div class="person-foot"><span>CONSUMED ${Math.round(consumed).toLocaleString()} KCAL</span><span>REFERENCE ${Math.round(target).toLocaleString()} KCAL</span></div></div>`
 }).join('')+`<div class="sublead">For the ${n} modeled dinners, not a full-day dietary assessment.</div>`;
}
function drawMeal(){const meal=sim.latest_meal;
 $('#lastRecipeTag').textContent=meal?'DAY '+String(sim.day-1).padStart(2,'0'):'AWAITING STEP';
 if(!meal){$('#mealPanel').innerHTML='<div class="empty-state">No meal has been served on the most recent day.</div>';return}
 const b=sim.latest_basket||{total_cents:0},p=sim.latest_physics||{};
 $('#mealPanel').innerHTML=`<div class="meal-name">${htmlEscape(meal.title)}</div>
 <div class="meal-facts"><div class="meal-fact"><strong>${money(b.total_cents)}</strong><span>DAILY BASKET</span></div><div class="meal-fact"><strong>${dec(meal.scheduled_minutes,0)}m</strong><span>SCHEDULED</span></div><div class="meal-fact"><strong>${pct(meal.actual_acceptance)}</strong><span>ACCEPTANCE</span></div></div>
 <div class="fact-strip"><span>PREPARED FOOD REUSED</span><strong>${meal.reused_prepared_food?'YES':'NO'}</strong></div><div class="fact-strip"><span>ENERGY DELIVERED</span><strong>${dec(meal.nutrition_total.kcal,0)} KCAL SERVED</strong></div><div class="fact-strip"><span>THERMAL CORE PROXY</span><strong>${dec(p.core_c)} °C</strong></div>`;
}
function drawInventory(){let lots=sim.inventory||[];$('#lotCount').textContent=lots.length+' LOTS';
 $('#inventoryMini').innerHTML=lots.length?lots.slice(0,6).map(l=>`<div class="inventory-row"><div><div class="inventory-name">${htmlEscape(l.name)}</div><div class="inventory-meta">${dec(l.grams,0)} G · ${htmlEscape(l.storage.toUpperCase())}</div><div class="lot-bar"><span style="width:${Math.min(100,l.grams/10)}%"></span></div></div><div class="inventory-time ${l.days_remaining<=2?'warn':''}">${l.days_remaining<0?'EXPIRED':l.days_remaining+'D LEFT'}</div></div>`).join(''):'<div class="unavailable">No stored ingredients. Purchase groceries to replenish.</div>';
}
function drawMarketMini(){const ms=sim.market||[];let rows=['chicken','rice','broccoli','beans','tofu'].map(id=>{
 const os=ms.filter(o=>o.product===id&&o.stock>0).sort((a,b)=>a.price_cents/a.package_g-b.price_cents/b.package_g);
 if(!os.length)return `<div class="market-line"><span>${htmlEscape(id)}</span><i>STOCKOUT</i></div>`;
 const o=os[0];return `<div class="market-line"><span>${htmlEscape(id)}</span><div><strong>${money(o.price_cents)}</strong><i>${htmlEscape(o.store)}</i></div></div>`
 });$('#marketMini').innerHTML=rows.join('')+'<div class="sublead">Invented prices and stock levels; not connected to retailers.</div>';
}
function drawMarket(){
 const ms=sim.market||[];
 const stores=[{id:'corner',name:'Corner',fee:2,travel:12},{id:'value',name:'Value',fee:5,travel:28},{id:'fresh',name:'Fresh',fee:3.2,travel:21}];
 $('#marketSummary').innerHTML=stores.map((s,i)=>`<div class="store-card"><div class="num">0${i+1} / MERCHANT</div><h3>${s.name}</h3><p>${money(s.fee*100)} TRIP · ${s.travel} MIN</p></div>`).join('');
 const ids=[...new Set(ms.map(o=>o.product))].sort();
 $('#marketTable tbody').innerHTML=ids.map(id=>{
 const os=stores.map(s=>ms.find(o=>o.product===id&&o.store===s.id));
 return `<tr><td>${htmlEscape(id)}</td>${os.map(o=>o?(o.stock?`<td>${money(o.price_cents)} ${o.promotion!=='none'?'<span class="promo">'+htmlEscape(o.promotion)+'</span>':''}</td>`:'<td><span class="stockout">OUT</span></td>'):'<td>—</td>').join('')}<td>${os[0]?.package_g||0} g</td></tr>`
 }).join('');
 const basket=sim.latest_basket;
 if(!basket){$('#basketLines').innerHTML='<div class="unavailable">No purchase has occurred in the current replay position.</div>'}
 else{$('#basketLines').innerHTML=(basket.lines||[]).map(l=>`<div class="basket-line"><div>${htmlEscape(l.product)} <em> × ${l.packages} / ${htmlEscape(l.store)}</em></div><strong>${money(l.paid_cents)}</strong></div>`).join('')+`<div class="basket-line"><div>Trip costs <em>/${basket.stores.length} stores</em></div><strong>${money(basket.trip_cents)}</strong></div><div class="basket-total"><span>Settled cost</span><strong>${money(basket.total_cents)}</strong></div>`}
 const b=sim.budget||{},weekly=b.weekly_cents||1,counts=b.spent_by_week||{};
 $('#budgetChart').innerHTML=Array.from({length:Math.ceil(sim.horizon/7)},(_,i)=>{
 const spent=Number(counts[i]||counts[String(i)]||0),ratio=Math.min(1,spent/weekly);
 return `<div class="budget-week"><span>WK ${String(i+1).padStart(2,'0')}</span><div class="budget-track"><div class="budget-fill ${spent>weekly?'over':''}" style="width:${ratio*100}%"></div></div><span class="budget-value">${money(spent)}</span></div>`
 }).join('')+`<div class="sublead">Hard cap ${money(weekly)} per seven-day budget window. Only simulated dinner purchases are charged.</div>`;
}
function drawKitchen(){const schedule=sim.latest_schedule;
 if(!schedule){$('#gantt').innerHTML='<div class="unavailable">Advance to create a resource-constrained cooking schedule.</div>';$('#thermal').innerHTML='<div class="unavailable">No heating operation yet.</div>';$('#physicalNotes').innerHTML='';return}
 $('#scheduleSpan').textContent=dec(schedule.makespan_min,0)+' MIN · '+schedule.tasks.length+' OPERATIONS';
 const max=Math.max(1,schedule.makespan_min);
 $('#gantt').innerHTML=schedule.tasks.map(task=>`<div class="gantt-row"><div class="gantt-label">${htmlEscape(task.id.replaceAll('_',' '))}</div><div class="gantt-track"><div class="gantt-block ${htmlEscape(task.resource)}" title="${htmlEscape(task.resource)} · ${task.start_min}-${task.end_min}m" style="left:${task.start_min/max*100}%;width:${Math.max(1,(task.end_min-task.start_min)/max*100)}%"></div></div></div>`).join('')+`<div class="gantt-axis"><span>00:00</span><span>${Math.round(max/2)}m</span><span>${Math.round(max)}m</span></div>`;
 const p=sim.latest_physics||{},c=Math.min(100,(p.core_c||0)/110*100);
 $('#thermal').innerHTML=`<div class="thermal-read"><strong>${dec(p.core_c,1)}°</strong><small>SIMULATED CORE C</small></div><div class="thermal-meter"><span style="width:${c}%"></span></div><div class="thermal-label"><span>SURFACE ${dec(p.surface_c)} °C</span><span>PAN ${dec(p.pan_c)} °C</span></div><div class="fact-strip"><span>EVAPORATION PROXY</span><strong>${dec(p.evaporated_g)} G</strong></div><div class="fact-strip"><span>HEAT INPUT</span><strong>${dec(p.electricity_kwh,2)} KWH</strong></div><p class="sublead warn">Not a validated food-safety determination. Use real thermometers and official guidelines in real kitchens.</p>`;
 const m=sim.metrics||{};
 $('#physicalNotes').innerHTML=[['01','PRECEDENCE','All dependencies must finish before their successors begin.'],['02','CAPACITY','Each shared kitchen resource has finite capacity.'],['03','MASS',`${dec(m.edible_meal_g||0)} g edible-equivalent ingredient allocation tracked.`],['04','VERIFICATION','Physical transitions and budget invariants checked separately.']].map(v=>`<div class="physical-note"><strong>${v[0]}</strong><div><b>${v[1]}</b><br>${v[2]}</div></div>`).join('');
}
function classifyBead(n){const id=n.id||'';
 if(id.endsWith('.goal'))return '1 / GOAL';
 if(['people','pantry','prices','budget'].some(x=>id.endsWith('.'+x))||id.includes('.profile_')||id.includes('.quote_'))return '2 / OBSERVE';
 if(['recipe','safety','need','basket','checkout'].some(x=>id.endsWith('.'+x))||id.includes('.need_'))return '3 / DECIDE';
 if(['travel','store','reserve'].some(x=>id.endsWith('.'+x)))return '4 / ACQUIRE';
 if(id.includes('.op_'))return '5 / OPERATE';
 return '6 / VERIFY & LEARN';
}
function drawBeads(){const g=sim.beads||{summary:{total:0,counts:{}},nodes:[]};
 const counts=g.summary?.counts||{};
 $('#beadMetrics').innerHTML=[['ACTIVE BEADS',g.summary?.total||0],['PASSED',counts.passed||0],['BLOCKED / FAILED',(counts.blocked||0)+(counts.failed||0)]].map(x=>`<div class="bead-kpi"><strong>${x[1]}</strong><span>${x[0]}</span></div>`).join('');
 const filter=$('#beadFilter');const selected=filter.value;const types=[...new Set((g.nodes||[]).map(n=>n.kind))].sort();
 filter.innerHTML='<option value="">ALL TYPES</option>'+types.map(t=>`<option value="${htmlEscape(t)}">${htmlEscape(t.toUpperCase())}</option>`).join('');filter.value=types.includes(selected)?selected:'';
 const nodes=(g.nodes||[]).filter(n=>!filter.value||n.kind===filter.value);
 const grouped={};nodes.forEach(n=>(grouped[classifyBead(n)]??=[]).push(n));
 $('#beadGraph').innerHTML=nodes.length?'<div class="dag-groups">'+Object.entries(grouped).sort(([a],[b])=>a.localeCompare(b)).map(([stage,list])=>`<div class="dag-group"><div class="dag-group-label">${stage} / ${list.length}</div>${list.map(n=>`<button class="bead-node ${n.status}" data-bead="${htmlEscape(n.id)}"><small>${htmlEscape(n.kind.toUpperCase())} · ${htmlEscape(n.status.toUpperCase())} · ${(n.depends_on||[]).length} DEPS</small><span>${htmlEscape(n.label)}</span></button>`).join('')}</div>`).join('')+'</div>':'<div class="unavailable">No compiled Beads yet. Advance the world to create an execution graph.</div>';
 $$('[data-bead]').forEach(e=>e.addEventListener('click',()=>{lastGraphNode=g.nodes.find(n=>n.id===e.dataset.bead);$$('.bead-node').forEach(x=>x.classList.toggle('selected',x===e));
 $('#beadInfo').textContent=`${lastGraphNode.id} | ${lastGraphNode.kind} | ${lastGraphNode.status} | PREREQUISITES: ${lastGraphNode.depends_on.join(', ')||'none'} | RESOURCES: ${JSON.stringify(lastGraphNode.resources)} | DETAILS: ${JSON.stringify(lastGraphNode.details)} | PROVENANCE: ${lastGraphNode.provenance}`;}));
}
function drawComparison(){if(!comparisonCache){$('#comparison').innerHTML='<div class="unavailable">Fork the current state to compare alternative actions.</div>';return}
 const alts=comparisonCache.alternatives||[];const best=alts.length?Math.max(...alts.map(a=>a.reward)):0;
 $('#compareDay').textContent='BRANCHED AT DAY '+String(comparisonCache.day||0).padStart(2,'0');
 $('#comparison').innerHTML=alts.map((a,i)=>`<div class="comparison-card ${a.reward===best?'best':''}"><div class="marker">${a.reward===best?'BEST ONE-STEP REWARD':'INTERVENTION '+String(i).padStart(2,'0')}</div><h3>${htmlEscape(a.action.replaceAll('_',' ').toLowerCase())}</h3><div class="comparison-r">${Number(a.reward)>=0?'+':''}${dec(a.reward,3)}</div><div class="comparison-row"><span>DINNER SERVED</span><strong>${a.info.served?'YES':'NO'}</strong></div><div class="comparison-row"><span>SPENDING</span><strong>${money(a.info.spend_cents)}</strong></div><div class="comparison-row"><span>MENU</span><strong>${htmlEscape(a.info.recipe||'NONE')}</strong></div><div class="comparison-row"><span>SCORE AFTER STEP</span><strong>${dec(a.info.score,1)}</strong></div></div>`).join('');
}
async function compare(){if(replay){const preview=replay.scenarios[replayPolicy]?.alternatives||[];comparisonCache={day:0,alternatives:preview};drawComparison();return}
 try{const data=await request('counterfactual');comparisonCache=data;drawComparison();if(!data.alternatives?.length)toast('The scenario is complete. Reset before branching.')}
 catch(e){toast(e.message)}
}
async function exportData(){if(replay){const blob=new Blob([JSON.stringify({mode:'offline_recorded_replay',snapshot:sim},null,2)],{type:'application/json'});downloadBlob(blob,'household-replay.json');return}
 try{const data=await request('export');downloadBlob(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),'household-evidence.json')}catch(e){toast(e.message)}}
function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}

function openConfiguration(){
 if(replay){toast('The offline preview is a recorded replay. Run the local server to configure a new household.');return}
 if(!sim)return;
 const budget=sim.budget||{};
 $('#budgetInput').value=((budget.weekly_cents||0)/100).toFixed(0);
 $('#burnersInput').value='2';
 $('#horizonInput').value=sim.horizon;
 $('#personInputs').innerHTML=(sim.people||[]).map((person,index)=>`<fieldset class="config-person" data-person="${index}"><legend>${htmlEscape(person.id.toUpperCase())} <span>/ ${htmlEscape(person.role.toUpperCase())}</span></legend>
   <div class="config-person-grid"><label>Age (years)<input class="input-age" type="number" min="0" max="125" step="1" value="${person.age_years}" required></label>
   <label>Dinner reference (kcal)<input class="input-energy" type="number" min="1" max="5000" step="1" value="${person.dinner_reference_kcal}" required></label>
   <label>Protein reference (g)<input class="input-protein" type="number" min="0" max="300" step="1" value="${person.dinner_protein_reference_g||0}" required></label>
   <label>Fiber reference (g)<input class="input-fiber" type="number" min="0" max="150" step="1" value="${person.dinner_fiber_reference_g||0}" required></label></div>
   <label>Allergens, comma separated<input class="input-allergens" type="text" value="${htmlEscape((person.allergens||[]).join(', '))}" placeholder="e.g. milk, egg"></label>
 </fieldset>`).join('');
 $('#configDialog').showModal();
}
async function saveConfiguration(e){
 e.preventDefault();
 const people=(sim.people||[]).map((person,i)=>{const f=$$('.config-person')[i];const num=(c)=>Number(f.querySelector(c).value);
  return {id:person.id,role:person.role,age_years:num('.input-age'),
   dinner_energy_reference_kcal:num('.input-energy'),
   dinner_protein_reference_g:num('.input-protein'),dinner_fiber_reference_g:num('.input-fiber'),
   preferences:person.preferences||{}, texture_restrictions:person.texture_restrictions||[],
   allergens:f.querySelector('.input-allergens').value.split(',').map(a=>a.trim().toLowerCase()).filter(Boolean)};
 });
 const budget=Math.round(Number($('#budgetInput').value)*100),horizon=Number($('#horizonInput').value),burners=Number($('#burnersInput').value);
 try{sim=await request('configure',{method:'POST',body:JSON.stringify({seed:sim.seed,horizon,weekly_budget_cents:budget,burners,people})});
  comparisonCache=null;$('#configDialog').close();render();toast('Household simulation reset using updated synthetic parameters.');}
 catch(err){toast(err.message)}
}

async function init(){
 $$('.nav-item').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
 $('#action').addEventListener('change',e=>setAction(e.target.value));
 $('#step').addEventListener('click',()=>advance(1));$('#seven').addEventListener('click',()=>advance(7));
 $('#configure').addEventListener('click',openConfiguration);
 $('#configForm').addEventListener('submit',saveConfiguration);
 $('#closeConfig').addEventListener('click',()=>$('#configDialog').close());
 $('#cancelConfig').addEventListener('click',()=>$('#configDialog').close());
 $('#reset').addEventListener('click',resetWorld);$('#compare').addEventListener('click',compare);
 $('#export').addEventListener('click',exportData);
 $('#beadFilter').addEventListener('change',drawBeads);
 if(replay){sim=replayTimeline()[0];$('#engineMode').textContent='SYNTHETIC / REPLAY';toast('Offline replay: fixed trajectories. For live choices, run the local server.');}
 else{try{sim=await request('state');}catch(e){toast('Cannot connect to the local simulation API. Start python -m household.cli serve.');return}}
 render();let requested=location.hash.replace('#','');if(['overview','market','kitchen','beads','counterfactual','evidence'].includes(requested))setView(requested);
}
document.addEventListener('DOMContentLoaded',init);
