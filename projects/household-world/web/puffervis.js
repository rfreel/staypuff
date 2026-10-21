/* PufferVis / scene renderer v1.
 * Renderer-independent scene protocol. No simulator/domain imports; renders a
 * passive, immutable scene snapshot. Panning/selection never change RL state.
 * Authoring: procedural iso geometry, 2D Canvas; no third-party assets.
 */
(function(root) {
'use strict';
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const n=(v,defaultValue=0)=>Number.isFinite(Number(v))?Number(v):defaultValue;
const css={bg:'#141d1d',plinth:'#182625',slate:'#293d3c',olive:'#30413a',cream:'#3a4941',umber:'#364037',line:'#8ba59b',ink:'#eff0d9',muted:'#b6cabe',gold:'#efc381',green:'#92d2aa',coral:'#e78f76',blue:'#8ac6cd'};
const facePalettes={
  porcelain:['#e3e9dd','#a8baac','#81998e'],
  slate:['#465958','#324441','#243532'],
  dark:['#445454','#273638','#1c292a'],
  wood:['#d5af84','#907154','#705841'],
  ochre:['#e6b47d','#a5794e','#896046'],
  mint:['#aed6bb','#67917d','#4e7765'],
  rose:['#e6b49b','#a46a65','#854e4f'],
  blue:['#b8d8d6','#728e9b','#50717f'],
};
const glass='rgba(10,22,22,.75)';

class PufferVis {
  constructor(canvas, options={}) {
    if (!canvas || typeof canvas.getContext !== 'function') throw Error('Canvas required');
    this.canvas=canvas;this.ctx=canvas.getContext('2d');
    if(!this.ctx)throw Error('Canvas 2D context unavailable');
    this.options=options;this.scene=null;this.scale=1;this.panX=0;this.panY=0;
    this.layer='all';this.flow=true;this.picking=[];this.selected=null;
    this.hovered=null;this.pointer=null;this.dragged=false;this.width=1;this.height=1;
    this.active=options.active!==false;this.cameraTarget=[0,0,0];this.cameraZoom=1;this.cameraKey=null;
    this.disposed=false;this.time=0;this.phase=0;this.anim=0;
    this.reduced=typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.handlers={};this.bind();this.resize();this.frame=0;this.loop=this.loop.bind(this);
    if(this.active)this.frame=requestAnimationFrame(this.loop);
  }
  bind(){
    const pointer=(event)=>{const r=this.canvas.getBoundingClientRect();return {x:event.clientX-r.left,y:event.clientY-r.top}};
    this.handlers.down=(e)=>{if(e.button!==0&&e.pointerType!=='touch')return;this.pointer={...pointer(e),panX:this.panX,panY:this.panY};this.dragged=false;this.canvas.setPointerCapture?.(e.pointerId)};
    this.handlers.move=(e)=>{const p=pointer(e);if(this.pointer){let dx=p.x-this.pointer.x,dy=p.y-this.pointer.y;if(Math.hypot(dx,dy)>5)this.dragged=true;this.panX=this.pointer.panX+dx;this.panY=this.pointer.panY+dy;this.hovered=null}else{this.hovered=this.pick(p.x,p.y)}};
    this.handlers.up=(e)=>{const p=pointer(e);if(!this.dragged){let found=this.pick(p.x,p.y);this.select(found?.id||null)}this.pointer=null;this.dragged=false;try{this.canvas.releasePointerCapture(e.pointerId)}catch(_){}};
    this.handlers.wheel=e=>{e.preventDefault();const p=pointer(e);
      const prev=this.scale;this.scale=clamp(this.scale*(e.deltaY<0?1.11:.9),.6*this.cameraZoom,2.1*this.cameraZoom);
      this.panX+=(p.x-this.width*.5-this.panX)*(1-this.scale/prev);
      this.panY+=(p.y-this.height*.48-this.panY)*(1-this.scale/prev);
    };
    this.handlers.key=e=>{if(e.key==='Escape'){this.select(null)}else if(e.key==='+'||e.key==='='){this.zoom(1.12)}else if(e.key==='-'){this.zoom(.89)}};
    this.canvas.addEventListener('pointerdown',this.handlers.down);
    this.canvas.addEventListener('pointermove',this.handlers.move);
    this.canvas.addEventListener('pointerup',this.handlers.up);
    this.canvas.addEventListener('pointercancel',this.handlers.up);
    this.canvas.addEventListener('wheel',this.handlers.wheel,{passive:false});
    this.canvas.addEventListener('keydown',this.handlers.key);
    this.handlers.resize=()=>this.resize();window.addEventListener('resize',this.handlers.resize);
    if(typeof ResizeObserver!=='undefined'){this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(this.canvas)}
  }
  dispose(){this.disposed=true;cancelAnimationFrame(this.frame);this.observer?.disconnect();window.removeEventListener('resize',this.handlers.resize);for(const [type,key] of Object.entries({pointerdown:'down',pointermove:'move',pointerup:'up',pointercancel:'up',wheel:'wheel',keydown:'key'})){this.canvas.removeEventListener(type,this.handlers[key])}this.pointer=null;this.frame=0}
  resize(){const r=this.canvas.getBoundingClientRect();if(!r.width||!r.height)return;
    this.width=r.width;this.height=r.height;const dpr=Math.min(window.devicePixelRatio||1,2);
    let w=Math.max(1,Math.round(r.width*dpr)),h=Math.max(1,Math.round(r.height*dpr));
    if(this.canvas.width!==w)this.canvas.width=w;if(this.canvas.height!==h)this.canvas.height=h;
    this.ctx.setTransform(dpr,0,0,dpr,0,0);
  }
  setScene(scene){if(scene&&scene.schema!=='puffervis.scene.v1')throw Error('Unsupported PufferVis scene version');
    const camera=scene?.camera;
    const key=JSON.stringify([scene?.scene_id,camera]);
    this.scene=scene;this.time=0;this.phase=0;
    if(key!==this.cameraKey){
      this.cameraKey=key;this.cameraTarget=(camera?.target||[0,0,0]).map(v=>n(v));
      this.cameraZoom=n(camera?.zoom,1)>0?n(camera?.zoom,1):1;this.resetCamera();
    }
    if(this.selected&&!(scene?.entities||[]).some(x=>x.id===this.selected))this.select(null);
    this.onSelection();
  }
  setLayer(value){this.layer=value;}
  setFlow(value){this.flow=Boolean(value)}
  zoom(f){this.scale=clamp(this.scale*f,.6*this.cameraZoom,2.1*this.cameraZoom)}
  resetCamera(){this.scale=this.cameraZoom;this.panX=0;this.panY=0}
  select(id){this.selected=id;this.onSelection();}
  onSelection(){let e=this.scene?.entities.find(e=>e.id===this.selected)||null;
    if(typeof this.options.onSelect==='function')this.options.onSelect(e)}
  pick(x,y){for(let i=this.picking.length-1;i>=0;i--){let p=this.picking[i];if(Math.hypot((x-p.x)/p.rx,(y-p.y)/p.ry)<=1.15)return p.entity}return null}
  setActive(value){
    if(this.disposed)return;
    const active=Boolean(value);if(active===this.active)return;
    this.active=active;this.time=0;
    if(active){this.resize();this.frame=requestAnimationFrame(this.loop)}
    else{cancelAnimationFrame(this.frame);this.frame=0;this.pointer=null;}
  }
  loop(time){if(this.disposed||!this.active)return;const ms=this.time?Math.min(50,time-this.time):0;this.time=time;
    if(!this.reduced)this.phase+=ms/1000;this.draw();this.frame=requestAnimationFrame(this.loop)}
  tileW(){return Math.min(66,Math.max(17,this.width/18.7))*this.scale}
  toIsoPoint(x,y,z){x-=this.cameraTarget[0];y-=this.cameraTarget[1];z-=this.cameraTarget[2];const tw=this.tileW(),th=tw*.51;
    return {x:this.width*.5+this.panX+(x-z)*tw*.5,
            y:this.height*.48+this.panY+(x+z)*th*.5-y*tw*.8};
  }
  poly(points,fill,stroke=null,lw=1){const c=this.ctx;c.beginPath();points.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));c.closePath();if(fill){c.fillStyle=fill;c.fill()}if(stroke){c.strokeStyle=stroke;c.lineWidth=lw;c.stroke()}}
  line(a,b,color,width=1){const c=this.ctx;c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.strokeStyle=color;c.lineWidth=width;c.stroke()}
  point(x,z,h=0){return this.toIsoPoint(x,h,z)}
  prism(x,z,w,d,h,palette,base=0){const top=[this.point(x-w/2,z-d/2,h+base),this.point(x+w/2,z-d/2,h+base),this.point(x+w/2,z+d/2,h+base),this.point(x-w/2,z+d/2,h+base)];
    const low=[this.point(x-w/2,z-d/2,base),this.point(x+w/2,z-d/2,base),this.point(x+w/2,z+d/2,base),this.point(x-w/2,z+d/2,base)];
    this.poly([top[1],top[2],low[2],low[1]],palette[1]);this.poly([top[2],top[3],low[3],low[2]],palette[2]);this.poly(top,palette[0],null);
    return {top,low};}
  ellipse(x,y,rx,ry,color,rotation=0){const c=this.ctx;c.beginPath();c.ellipse(x,y,rx,ry,rotation,0,Math.PI*2);c.fillStyle=color;c.fill()}
  circle(x,y,r,color){const c=this.ctx;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fillStyle=color;c.fill()}
  text(value,x,y,font,color=css.ink,align='left',maxWidth=300){const c=this.ctx;c.font=font;c.textAlign=align;c.textBaseline='middle';c.fillStyle=color;c.fillText(String(value),x,y,maxWidth)}
  format(v){return v==null?'—':typeof v==='number'?(Number.isInteger(v)?String(v):v.toFixed(2)):String(v)}
  drawBackground(){const c=this.ctx, w=this.width,h=this.height;c.fillStyle=css.bg;c.fillRect(0,0,w,h);
    let g=c.createRadialGradient(w*.50,h*.40,30,w*.50,h*.50,w*.65);g.addColorStop(0,'#253b39');g.addColorStop(.55,'#1d2d2e');g.addColorStop(1,'#101a1a');c.fillStyle=g;c.fillRect(0,0,w,h);
    // Drafting instrument marks: drawn behind the world.
    c.fillStyle='rgba(143,194,177,.10)';for(let x=18;x<w;x+=33){for(let y=18;y<h;y+=33)c.fillRect(x,y,1,1)}

  }
  drawZone(z){let [x,d,w,h]=[z.x,z.z,z.width,z.depth];const zonePalette={slate:'#415451',olive:'#405947',cream:'#57645a',umber:'#4d534b'};
    const top=[this.point(x,d),this.point(x+w,d),this.point(x+w,d+h),this.point(x,d+h)];
    const drop=15*this.scale;this.poly([top[1],top[2],{x:top[2].x,y:top[2].y+drop},{x:top[1].x,y:top[1].y+drop}],'#1a2a26');
    this.poly([top[2],top[3],{x:top[3].x,y:top[3].y+drop},{x:top[2].x,y:top[2].y+drop}],'#14221e');
    this.poly(top,zonePalette[z.material]||'#3d5048','rgba(193,211,196,.32)');
    let c=this.ctx;c.save();c.globalAlpha=.20;for(let i=1;i<Math.ceil(w);i++)this.line(this.point(x+i,d),this.point(x+i,d+h),'#e5ebd9',.55);
    for(let i=1;i<Math.ceil(h);i++)this.line(this.point(x,d+i),this.point(x+w,d+i),'#e5ebd9',.55);
    c.restore();
    const label=this.point(x+w*.15,d+h*.14,.01);
    this.text(z.label,label.x,label.y-9*this.scale,`600 ${clamp(9*this.scale,7,12)}px monospace`,'rgba(239,243,218,.70)');
  }
  drawConnections(){if(!this.flow)return;const entities=new Map(this.scene.entities.map(x=>[x.id,x]));const c=this.ctx;
    for(const edge of this.scene.connections||[]){const a=entities.get(edge.from),b=entities.get(edge.to);if(!a||!b)continue;
      let p=this.point(a.position[0],a.position[2],.04),q=this.point(b.position[0],b.position[2],.04);
      c.save();c.strokeStyle='rgba(172,212,165,.4)';c.lineWidth=1.7;c.setLineDash([4,7]);this.line(p,q,c.strokeStyle,c.lineWidth);c.setLineDash([]);
      if(!this.reduced){let t=(this.phase*.2)%1;let px=p.x+(q.x-p.x)*t,py=p.y+(q.y-p.y)*t;this.circle(px,py,3.6,css.gold)}c.restore();
    }
  }
  drawShadow(entity){const [x,y,z]=entity.position,p=this.point(x,z,.03);this.ellipse(p.x,p.y+8*this.scale,15*this.scale,7*this.scale,'rgba(7,19,18,.27)')}
  drawEntity(e){if(this.layer==='kitchen'&&e.position[0]>9.4)return;if(this.layer==='market'&&e.position[0]<9.4)return;
    const [x,y,z]=e.position,center=this.point(x,z,y),k=this.scale,w=this.tileW();this.drawShadow(e);
    switch(e.visual){
    case 'fridge':{
      let b=this.prism(x,z,1.45,1.20,2.55,facePalettes.porcelain);let a=b.top[2],lo=b.low[2];
      this.line({x:a.x-3*k,y:a.y+7*k},{x:lo.x-3*k,y:lo.y-7*k},'#718d82',2*k);
      this.line({x:a.x-3*k,y:a.y+28*k},{x:lo.x-3*k,y:lo.y-25*k},'#dbe9dd',2.7*k);
      this.drawBillboard('COLD',center.x,center.y-125*k,'#afded4');break;}
    case 'sink':{
      this.prism(x,z,1.7,1.4,.85,facePalettes.porcelain);let p=this.point(x,z,.89),c=this.ctx;
      this.ellipse(p.x,p.y,19*k,9*k,'#546d70');this.ellipse(p.x,p.y,15*k,6*k,'#86abb1');
      this.line({x:p.x-4*k,y:p.y-7*k},{x:p.x-4*k,y:p.y-29*k},'#cddfd7',2.5*k);
      this.line({x:p.x-4*k,y:p.y-29*k},{x:p.x+8*k,y:p.y-29*k},'#cddfd7',2.5*k);break;}
    case 'stove':{
      this.prism(x,z,1.65,1.55,.9,facePalettes.dark);let p=this.point(x,z,.94);
      for(let dx of [-.37,.37]){let a=this.point(x+dx,z,.96);this.ellipse(a.x,a.y,11*k,6*k,'#1b2927');this.ellipse(a.x,a.y,7*k,3.9*k,e.signal==='active'?'#d96d42':'#526768')}
      if(e.signal==='active'){
        this.ellipse(p.x,p.y-4*k,18*k,8*k,'#293a38');this.ellipse(p.x,p.y-9*k,17*k,7*k,'#d0d4be');
        this.ellipse(p.x,p.y-9*k,12*k,4*k,'#a16a47');this.line({x:p.x+16*k,y:p.y-10*k},{x:p.x+30*k,y:p.y-15*k},'#b9c3b8',3*k);
        if(!this.reduced)for(let j=0;j<3;j++){let phase=(this.phase*.8+j*.33)%1;this.circle(p.x+Math.sin(j*4+this.phase)*7*k,p.y-(19+phase*31)*k, (2.8+phase*1.8)*k,`rgba(225,242,207,${(.22*(1-phase)).toFixed(3)})`)}
      }break;}
    case 'oven':{
      let b=this.prism(x,z,1.55,1.25,1.24,facePalettes.dark),p=b.low[2];
      this.poly([{x:p.x-18*k,y:p.y-21*k},{x:p.x+7*k,y:p.y-9*k},{x:p.x+7*k,y:p.y-40*k},{x:p.x-18*k,y:p.y-51*k}],'#192f2e','#839f91');
      let bulb=this.point(x+.22,z+.16,1.25);this.circle(bulb.x,bulb.y,2.5*k,'#eebc70');break;}
    case 'island':{
      this.prism(x,z,2.15,1.65,.89,facePalettes.wood);let p=this.point(x,z,.95);
      this.poly([{x:p.x-16*k,y:p.y-5*k},{x:p.x+8*k,y:p.y-15*k},{x:p.x+28*k,y:p.y-5*k},{x:p.x+4*k,y:p.y+5*k}],'#dfceaa','#f3ddbb');
      this.ellipse(p.x-4*k,p.y-7*k,7*k,3.5*k,'#78a45f');this.ellipse(p.x+9*k,p.y-7*k,5*k,3*k,'#dc8559');break;}
    case 'shelves':{
      this.prism(x,z,1.6,1.05,1.83,facePalettes.wood);
      for(let i=0;i<3;i++){let p=this.point(x+.35,z+.52,.3+i*.46);
        this.ellipse(p.x,p.y,6*k,4*k,i===0?'#e5c282':i===1?'#8dc192':'#cd9275');
        this.ellipse(p.x-11*k,p.y+5*k,4*k,3*k,'#d8b697')}
      break;}
    case 'dining_table':{
      this.prism(x,z,2.85,1.85,.63,facePalettes.wood);let p=this.point(x,z,.69);
      for(let dx of [-.75,0,.75]){let q=this.point(x+dx,z,.70);
        this.ellipse(q.x,q.y,12*k,6*k,'#e9ead5');this.ellipse(q.x,q.y,7*k,3.1*k,'#8ab38c')}
      break;}
    case 'market_stall':{
      const pal=e.variant==='corner'?facePalettes.ochre:e.variant==='fresh'?facePalettes.mint:facePalettes.blue;
      this.prism(x,z,2.03,1.35,1.40,pal);let roof=this.prism(x,z,2.4,1.65,.18,pal,1.51);
      this.drawBillboard(e.label.toUpperCase().replace(' GROCER',''),this.point(x,z,2.15).x,this.point(x,z,2.15).y,'#f6eee2');
      for(let i=0;i<4;i++){const p=this.point(x-.7+i*.45,z+.53,1.46);
        this.circle(p.x,p.y,5*k,[ '#e7ad67','#a9d99f','#ed9273','#e0cf83'][i])}break;}
    case 'checkout':{
      this.prism(x,z,1.9,1.2,.85,facePalettes.slate);const p=this.point(x,z,1.20);
      this.prism(x-.48,z-.17,.45,.43,.52,facePalettes.dark,.85);
      this.drawBillboard('PAY',p.x,p.y-4*k,'#ebd4a4');break;}
    case 'crate':{
      const urgent=e.variant==='urgent';this.prism(x,z,.75,.65,.32,urgent?facePalettes.rose:facePalettes.wood);
      let p=this.point(x,z,.35);this.ellipse(p.x,p.y,9*k,5*k,urgent?'#e29b75':'#8fbb81');
      this.ellipse(p.x-4*k,p.y-4*k,4*k,3*k,'#d2e5a7');break;}
    case 'meal':{
      let p=this.point(x,z,.79);this.ellipse(p.x,p.y,15*k,7*k,'#eff0db');
      this.ellipse(p.x,p.y-1*k,10*k,5*k,'#bb8555');this.ellipse(p.x+4*k,p.y-2*k,5*k,3*k,'#84b886');break;}
    case 'ledger':{
      this.prism(x,z,4.9,2.6,.30,facePalettes.dark);let count=n(e.facts.dinners_served);
      for(let i=0;i<5;i++){let bx=x-1.60+i*.65,factor=clamp(count/Math.max(1,n(this.scene.hud.day)),.12,1);
        this.prism(bx,z+.4,.4,.45,.25+factor*(i+2)*.08,facePalettes.mint,.31)}
      this.drawBillboard('WEEKLY RESERVE',this.point(x,z-.3,1.24).x,this.point(x,z-.3,1.24).y,'#e6e7cb');
      break;}
    case 'robot':{
      this.prism(x,z,.7,.75,.85,facePalettes.ochre);let p=this.point(x,z,.95);
      this.ellipse(p.x,p.y,9*k,5*k,'#263e39');this.circle(p.x,p.y,3.5*k,'#97dbbd');
      break;}
    case 'person':{
      let p=this.point(x,z,0);const tones={amber:'#e3b56d',rose:'#d6a098',mint:'#95c3a8',blue:'#9dbbd5'},body=tones[e.variant]||tones.amber;
      this.ellipse(p.x,p.y+2*k,13*k,5*k,'rgba(6,17,15,.32)');
      this.poly([{x:p.x-9*k,y:p.y-27*k},{x:p.x+9*k,y:p.y-27*k},{x:p.x+7*k,y:p.y-7*k},{x:p.x-7*k,y:p.y-7*k}],body);
      this.line({x:p.x-5*k,y:p.y-9*k},{x:p.x-5*k,y:p.y-1*k},'#334c48',3*k);
      this.line({x:p.x+5*k,y:p.y-9*k},{x:p.x+5*k,y:p.y-1*k},'#334c48',3*k);
      this.circle(p.x,p.y-36*k,9*k,'#e9c4a4');this.ellipse(p.x,p.y-42*k,8*k,4*k,'#3c3b36');
      break;}
    default:{this.prism(x,z,1,1,1,facePalettes.slate)}
    }
    const p=this.point(x,z,.3);this.picking.push({x:p.x,y:p.y-15*k,rx:32*k,ry:33*k,entity:e});
    if(e.id===this.selected||e.id===this.hovered?.id){this.drawMarker(e)}
    if(e.signal==='urgent'&&this.layer!=='market'){this.drawBillboard('!',p.x,p.y-42*k,css.coral)}
  }
  drawBillboard(label,x,y,color){const c=this.ctx;c.save();c.textAlign='center';c.textBaseline='middle';c.font=`700 ${Math.max(8,9*this.scale)}px monospace`;
    const width=Math.min(125,c.measureText(label).width+15*this.scale);c.fillStyle='rgba(20,32,29,.88)';c.fillRect(x-width/2,y-9*this.scale,width,19*this.scale);
    c.fillStyle=color;c.fillText(label,x,y,width-5);c.restore()}
  drawMarker(e){const [x,_,z]=e.position,p=this.point(x,z,2.1),k=this.scale;let c=this.ctx;c.save();c.strokeStyle=css.gold;c.lineWidth=1.4;
    c.beginPath();c.moveTo(p.x,p.y);c.lineTo(p.x,p.y-11*k);c.stroke();this.circle(p.x,p.y-13*k,4*k,css.gold);
    c.restore();this.drawBillboard(e.label.toUpperCase(),p.x,p.y-29*k,css.gold);
  }
  drawLedger(){if(!this.scene)return;const hud=this.scene.hud||{};
    this.prism(13.2,10,4.9,2.6,.30,facePalettes.dark);
    for(let i=0;i<5;i++){
      let bx=11.6+i*.58,p=this.point(bx,10.4,.38),factor=clamp((hud.dinners_served||0)/Math.max(1,hud.day||1),.12,1);
      const h=(.25+factor*(i+2)*.08);this.prism(bx,10.4,.4,.45,h,facePalettes.mint,.31);
    }
    this.drawBillboard('WEEKLY RESERVE',this.point(13.2,9.7,1.3).x,this.point(13.2,9.7,1.3).y,'#e6e7cb');
  }
  drawHud(){const c=this.ctx,w=this.width,h=this.height,s=this.scene||{},hud=s.hud||{};
    let stripY=h-98; c.fillStyle='rgba(12,23,22,.82)';c.fillRect(0,stripY,w,58);c.strokeStyle='rgba(179,205,189,.2)';c.strokeRect(0,stripY,w,.5);
    const parts=[['DAY',`${String(hud.day||0).padStart(2,'0')} / ${String(hud.horizon||0).padStart(2,'0')}`],
      ['DINNERS',`${hud.dinners_served||0}`],['RESERVE',`$${(n(hud.budget_remaining_cents)/100).toFixed(2)}`],
      ['SCORE',n(hud.score).toFixed(1)],['BEADS',`${hud.task_count||0}`]];
    const step=Math.min(164,(w-28)/parts.length);let start=(w-step*parts.length)/2;
    for(let i=0;i<parts.length;i++){
      let xx=start+i*step;this.text(parts[i][0],xx+8,stripY+15,'700 9px monospace','#96ada2');
      this.text(parts[i][1],xx+8,stripY+36,'500 16px Georgia,serif',css.ink);
      if(i) this.line({x:xx,y:stripY+9},{x:xx,y:stripY+49},'rgba(199,219,199,.13)');
    }
    const label=`STATE · ${s.provenance==='synthetic_simulation'?'SYNTHETIC':'UNKNOWN'} / VISUAL LAYOUT · ILLUSTRATIVE`;
    this.text(label,16,h-109,'600 9px monospace','#a9c6bb');
    if(this.layer!=='all')this.text('FILTER: '+this.layer.toUpperCase(),w-16,h-109,'600 9px monospace',css.gold,'right');
    if(this.hovered&&!this.selected){let e=this.hovered;this.drawBillboard(e.label.toUpperCase(),this.width/2,52,css.gold)}
  }
  draw(){if(!this.width||!this.height)return;this.drawBackground();this.picking=[];if(!this.scene)return;
    // Static geometry under dynamic agents. Render order follows iso diagonal.
    const zones=this.scene.zones||[];for(const zone of zones)this.drawZone(zone);
    this.drawConnections();
    let entities=(this.scene.entities||[]).slice().sort((a,b)=>(a.position[0]+a.position[2])-(b.position[0]+b.position[2]));
    for(let e of entities)this.drawEntity(e);
    this.drawHud();
  }
}
root.PufferVis={Renderer:PufferVis,SCHEMA:'puffervis.scene.v1'};
if(typeof module!=='undefined'&&module.exports)module.exports=root.PufferVis;
})(typeof window!=='undefined'?window:globalThis);
