const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const web=path.join(__dirname,'../web');
function harness(){
  const frames=new Map();let id=0;
  const canvas=new EventTarget();
  canvas.getContext=()=>({setTransform(){}});
  canvas.getBoundingClientRect=()=>({width:1000,height:700,left:0,top:0});
  const window=new EventTarget();window.devicePixelRatio=1;
  let disconnected=false;
  const context=vm.createContext({window,console,
    requestAnimationFrame:f=>{frames.set(++id,f);return id},
    cancelAnimationFrame:i=>frames.delete(i),
    ResizeObserver:class{observe(){}disconnect(){disconnected=true}}
  });
  vm.runInContext(fs.readFileSync(path.join(web,'puffervis.js'),'utf8'),context);
  return {canvas,window,frames,context,disconnected:()=>disconnected,Renderer:window.PufferVis.Renderer};
}
const scene=(target=[8,0,5.8],zoom=1,id='a')=>({schema:'puffervis.scene.v1',scene_id:id,camera:{target,zoom},entities:[]});
test('dispose removes every canvas/window handler and allows clean remount',()=>{
  const h=harness(), r=new h.Renderer(h.canvas);let calls=0;
  for(const method of ['select','pick','zoom','resize'])r[method]=()=>{calls++};
  r.dispose();r.dispose();
  for(const type of ['pointerdown','pointermove','pointerup','pointercancel','wheel','keydown']){
    const event=new Event(type);Object.assign(event,{button:0,clientX:1,clientY:1,key:'+',deltaY:-1});h.canvas.dispatchEvent(event);
  }
  h.window.dispatchEvent(new Event('resize'));
  assert.equal(calls,0);assert.equal(r.pointer,null);assert.equal(h.frames.size,0);assert.ok(h.disconnected());
  const next=new h.Renderer(h.canvas);const e=new Event('keydown');e.key='+';h.canvas.dispatchEvent(e);
  assert.equal(next.scale,1.12);assert.equal(r.scale,1);next.dispose();
});
test('camera targets distant coordinates, applies zoom, preserves user view until camera changes',()=>{
  const h=harness(),r=new h.Renderer(h.canvas);
  r.setScene(scene([100,7,-200],3));
  const p=r.toIsoPoint(100,7,-200);assert.equal(p.x,500);assert.equal(p.y,336);
  const offset=r.toIsoPoint(101,7,-200).x-p.x;
  r.zoom(1.2);r.panX=20;r.panY=30;
  r.setScene({...scene([100,7,-200],3),revision:2});assert.equal(r.panX,20);assert.ok(Math.abs(r.scale-3.6)<1e-12);
  r.resetCamera();assert.equal(r.scale,3);assert.equal(r.panX,0);
  r.setScene(scene([100,7,-200],1));assert.ok(Math.abs((r.toIsoPoint(101,7,-200).x-500)*3-offset)<1e-9);
  r.setScene(scene([-400,2,80],.2,'warehouse'));assert.equal(r.scale,.2);assert.equal(r.toIsoPoint(-400,2,80).x,500);
  r.dispose();
});
test('inactive renderer neither draws nor schedules, and resumes a single loop',()=>{
  const h=harness(),r=new h.Renderer(h.canvas);let draws=0;r.draw=()=>draws++;
  r.setActive(false);r.loop(100);assert.equal(draws,0);assert.equal(h.frames.size,0);
  r.setScene(scene());r.setActive(true);r.setActive(true);assert.equal(h.frames.size,1);
  const [id,frame]=[...h.frames][0];h.frames.delete(id);frame(200);assert.equal(draws,1);assert.equal(h.frames.size,1);
  r.dispose();r.setActive(true);assert.equal(h.frames.size,0);
});
function appHarness(fetch){
  const elements=new Map(),timers=[];
  const get=s=>{if(!elements.has(s))elements.set(s,{value:'0',classList:{toggle(){},add(){},remove(){}},textContent:''});return elements.get(s)};
  const context=vm.createContext({window:{},document:{querySelector:get,querySelectorAll:()=>[],addEventListener(){},body:{classList:{toggle(){}}}},history:{replaceState(){}},fetch,setTimeout:(f,ms)=>{timers.push({f,ms});return timers.length},clearTimeout(){}});
  vm.runInContext(fs.readFileSync(path.join(web,'app.js'),'utf8'),context);
  vm.runInContext('sim={day:0,horizon:30};render=()=>{};toast=()=>{};',context);
  return {context,timers,get,run:s=>vm.runInContext(s,context)};
}
for(const [name,fetch] of Object.entries({network:async()=>{throw Error('offline')},http:async()=>({ok:false,json:async()=>({detail:'rejected'})}),json:async()=>({ok:true,json:async()=>{throw Error('bad JSON')}})})){
  test(`autoplay stops after ${name} failure`,async()=>{
    let requests=0;const h=appHarness((...a)=>{requests++;return fetch(...a)});
    await h.run('playWorld()');assert.equal(requests,1);assert.equal(h.run('worldPlaying'),false);assert.equal(h.run('busy'),false);assert.equal(h.timers.length,0);assert.match(h.get('#worldPlay').textContent,/PLAY SIMULATION/);
  });
}
test('successful playback schedules the next step and inactive view stops renderer',async()=>{
  const h=appHarness(async()=>({ok:true,json:async()=>({state:{day:1,horizon:30}})}));
  await h.run('playWorld()');assert.equal(h.timers.length,1);assert.equal(h.timers[0].ms,1500);
  h.run("worldViewer={setActive(value){this.active=value}};setView('overview')");
  assert.equal(h.run('worldPlaying'),false);assert.equal(h.run('worldViewer.active'),false);
  h.run("setView('world')");assert.equal(h.run('worldViewer.active'),true);
});
test('recorded replay reports successful advancement',async()=>{
  const h=appHarness();h.run('replayTimeline=()=>[{day:0},{day:1}]');
  // Replay is immutable at load, so use a fresh context with its recorded payload.
  h.context.window.__REPLAY__={scenarios:[{timeline:[{day:0},{day:1}]}]};
  const c=vm.createContext({...h.context,window:h.context.window});
  vm.runInContext(fs.readFileSync(path.join(web,'app.js'),'utf8'),c);
  vm.runInContext('render=()=>{}',c);assert.equal(await vm.runInContext('advance(1)',c),true);
});
