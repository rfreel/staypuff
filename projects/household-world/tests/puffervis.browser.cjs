// Run against a local household.api server with Playwright installed.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const viewport of [{width:1440,height:940},{width:390,height:844}]){
   const page=await browser.newPage({viewport});const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(process.env.PUFFERVIS_URL||'http://127.0.0.1:8765');
   await page.waitForFunction(()=>typeof worldViewer!=='undefined'&&worldViewer?.scene);
   await page.evaluate(()=>{window.drawCount=0;const draw=worldViewer.draw.bind(worldViewer);worldViewer.draw=()=>{window.drawCount++;draw()}});
   await page.waitForFunction(()=>window.drawCount>2);
   const scale=await page.evaluate(()=>worldViewer.scale);await page.locator('#cameraPlus').click();
   assert.ok(await page.evaluate(()=>worldViewer.scale)>scale);
   await page.locator('#cameraReset').click();assert.equal(await page.evaluate(()=>worldViewer.scale),1);
   await page.evaluate(()=>setView('overview'));
   const hidden=await page.evaluate(()=>window.drawCount);
   await page.waitForTimeout(200);assert.equal(await page.evaluate(()=>window.drawCount),hidden);
   await page.evaluate(()=>setView('world'));await page.waitForFunction(n=>window.drawCount>n,hidden);
   await page.evaluate(()=>{worldViewer.select('fridge')});assert.match(await page.locator('#worldInspector').innerText(),/Refrigerator/);
   // Pointer picking still works with the scene camera transform.
   const target=await page.evaluate(()=>{const p=worldViewer.picking.find(p=>p.entity.id==='person:adult_a')||worldViewer.picking.find(p=>p.entity.visual==='person');return {x:p.x,y:p.y}});
   const bounds=await page.locator('#worldCanvas').boundingBox();
   await page.mouse.click(bounds.x+target.x,bounds.y+target.y);
   assert.ok(await page.evaluate(()=>worldViewer.selected?.startsWith('person:')));
   let requests=0;
   await page.route('**/api/step',route=>{requests++;return route.fulfill({status:503,contentType:'application/json',body:'{"detail":"test failure"}'})});
   await page.locator('#worldPlay').click();await page.waitForFunction(()=>!worldPlaying);
   await page.waitForTimeout(1700);assert.equal(requests,1);assert.match(await page.locator('#worldPlay').innerText(),/PLAY SIMULATION/);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);
   // Exercise the unrelated fixture and a distant scene through the actual canvas.
   const fixture=require('../examples/puffervis_warehouse.json');
   await page.evaluate(scene=>{worldViewer.setScene(scene);worldViewer.draw()},fixture);
   await page.evaluate(()=>{const s=structuredClone(worldViewer.scene);s.camera={projection:'isometric',target:[100,7,-200],zoom:1.3};s.entities=[{id:'far',visual:'robot',position:[100,7,-200],label:'Far robot',facts:{},signal:''}];s.zones=[];s.connections=[];worldViewer.setScene(s);worldViewer.draw();const p=worldViewer.toIsoPoint(100,7,-200);if(Math.abs(p.x-worldViewer.width*.5)>1e-8||Math.abs(p.y-worldViewer.height*.48)>1e-8)throw Error('camera target off center')});
   await page.close();console.log(`PASS browser ${viewport.width}x${viewport.height}`);
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
