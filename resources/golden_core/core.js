(() => {
 'use strict';
 const root=document.getElementById('jarvis-golden-preview');
 const canvas=root.querySelector('.g-canvas'),stage=root.querySelector('.g-stage');
 const loading=root.querySelector('.g-loading');
 if(!window.THREE){loading.textContent='The 3D engine is unavailable.';return;}
 const T=window.THREE;
 let renderer;
 try{renderer=new T.WebGLRenderer({canvas,alpha:false,antialias:false,powerPreference:'high-performance'});}
 catch(error){loading.textContent='Enable WebGL / hardware acceleration to view the core.';return;}
 const maxDpr=1.5;
 renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,maxDpr));
 renderer.setClearColor('#060609',1);
 renderer.outputColorSpace=T.LinearSRGBColorSpace;
 renderer.toneMapping=T.NoToneMapping;
 const scene=new T.Scene(),camera=new T.PerspectiveCamera(38,1,.1,30);
 camera.position.set(0,0,6.65);
 const hologram=new T.Group();scene.add(hologram);
 const sphereGroup=new T.Group();hologram.add(sphereGroup);
 const orbitGroup=new T.Group();hologram.add(orbitGroup);
 const resources=[];
 const track=o=>{resources.push(o);return o;};
 let randomSeed=9017;
 const random=()=>{randomSeed=(Math.imul(randomSeed,1664525)+1013904223)>>>0;return randomSeed/4294967296;};
 const amber=new T.Color('#ff8a24');
 const lineMaterial=track(new T.LineBasicMaterial({color:amber.clone().multiplyScalar(1.4),transparent:true,opacity:.72,depthWrite:false,blending:T.AdditiveBlending}));
 const fineMaterial=track(new T.LineBasicMaterial({color:amber,transparent:true,opacity:.34,depthWrite:false,blending:T.AdditiveBlending}));
 const beamMaterial=track(new T.MeshBasicMaterial({color:new T.Color(2.7,.43,.035),transparent:true,opacity:.9,depthWrite:false,blending:T.AdditiveBlending}));
 const mesh=(geo,mat,parent=hologram)=>{const m=new T.Mesh(track(geo),mat);parent.add(m);return m;};

 // Triangulated, genuinely three-dimensional lattice â€” no flattened image plane.
 const poly=track(new T.IcosahedronGeometry(1.13,2));
 const lattice=new T.LineSegments(track(new T.EdgesGeometry(poly,1)),lineMaterial);sphereGroup.add(lattice);
 const facetsMaterial=track(new T.ShaderMaterial({transparent:true,depthWrite:false,side:T.DoubleSide,blending:T.AdditiveBlending,
   uniforms:{energy:{value:.62}},
   vertexShader:'varying vec3 n;varying vec3 v;varying vec3 p;void main(){n=normalize(normalMatrix*normal);vec4 mv=modelViewMatrix*vec4(position,1.);v=normalize(-mv.xyz);p=position;gl_Position=projectionMatrix*mv;}',
   fragmentShader:'varying vec3 n;varying vec3 v;varying vec3 p;uniform float energy;void main(){float rim=pow(1.-abs(dot(normalize(n),normalize(v))),2.);float patch=step(.48,fract(sin(dot(floor(p*4.),vec3(12.98,78.23,37.17)))*43758.54));vec3 color=vec3(1.,.29,.015);gl_FragColor=vec4(color,(.012+rim*.045+patch*.018)*energy);}'
 }));
 const facets=mesh(poly,facetsMaterial,sphereGroup);
 const unique=new Map();const positions=poly.attributes.position;
 for(let i=0;i<positions.count;i++){const p=new T.Vector3().fromBufferAttribute(positions,i);unique.set(p.toArray().map(x=>x.toFixed(4)).join(','),p);}
 const nodes=Array.from(unique.values());
 // Sparse chords make the central lattice denser without obscuring its silhouette.
 const chordPositions=[];
 for(let i=0;i<36;i++){const a=nodes[Math.floor(random()*nodes.length)],b=nodes[Math.floor(random()*nodes.length)];if(a.distanceTo(b)<.5)continue;chordPositions.push(...a.toArray(),...b.toArray());}
 const chordGeometry=track(new T.BufferGeometry());chordGeometry.setAttribute('position',new T.Float32BufferAttribute(chordPositions,3));
 const chords=new T.LineSegments(chordGeometry,fineMaterial);sphereGroup.add(chords);

 // Point sprites: sharp pinpoints, a small luminous halo and depth attenuation.
 const particleVertex=`
 attribute float aSize;attribute float aPhase;varying vec3 vColor;
 uniform float uTime;uniform float uEnergy;uniform float uPixelRatio;
 void main(){vColor=color;vec4 mv=modelViewMatrix*vec4(position,1.);
 float scintillation=.72+.28*sin(aPhase+uTime*2.);
 gl_PointSize=clamp(aSize*uPixelRatio*scintillation*(5.8/-mv.z),1.,9.);
 gl_Position=projectionMatrix*mv;}`;
 const particleFragment=`
 varying vec3 vColor;uniform float uEnergy;
 void main(){float r=length(gl_PointCoord-.5)*2.;if(r>1.)discard;
 float sharp=exp(-r*r*8.);float halo=pow(1.-r,3.)*.24;
 gl_FragColor=vec4(vColor*(.5+uEnergy*1.7),(sharp+halo)*clamp(uEnergy*2.2,.05,1.));}`;
 function pointCloud(list,parent,opacity=1){
   const p=[],c=[],sz=[],ph=[];
   list.forEach(d=>{p.push(d.x,d.y,d.z);const color=new T.Color().setHSL(.07+random()*.06,.92,.43+random()*.23);c.push(color.r,color.g,color.b);sz.push(d.size||1.5+random()*2.5);ph.push(random()*Math.PI*2);});
   const geo=track(new T.BufferGeometry());geo.setAttribute('position',new T.Float32BufferAttribute(p,3));geo.setAttribute('color',new T.Float32BufferAttribute(c,3));geo.setAttribute('aSize',new T.Float32BufferAttribute(sz,1));geo.setAttribute('aPhase',new T.Float32BufferAttribute(ph,1));
   const mat=track(new T.ShaderMaterial({vertexShader:particleVertex,fragmentShader:particleFragment,transparent:true,depthWrite:false,vertexColors:true,blending:T.AdditiveBlending,
    uniforms:{uTime:{value:0},uEnergy:{value:opacity},uPixelRatio:{value:renderer.getPixelRatio()}}}));
   const cloud=new T.Points(geo,mat);parent.add(cloud);return cloud;
 }
 const nodeCloud=pointCloud(nodes.map(p=>({x:p.x,y:p.y,z:p.z,size:2.3})),sphereGroup,.55);

 const orbitBands=[];
 const bandSettings=[
   {radius:1.52,rotation:[.88,.26,.2],count:1100,seedCount:900,speed:.12,revolve:-.28,axis:[0,1,0]},
   {radius:1.7,rotation:[-.57,.54,-.4],count:1150,seedCount:950,speed:-.095,revolve:.24,axis:[1,.25,0]},
   {radius:1.85,rotation:[.28,-.81,.72],count:850,seedCount:700,speed:.078,revolve:-.2,axis:[.15,0,1]},
   {radius:1.49,rotation:[1.4,.3,-.6],count:600,seedCount:500,speed:-.15,revolve:.3,axis:[-.65,.7,.3]},
   {radius:1.96,rotation:[-.85,-.35,1.05],count:700,seedCount:0,speed:.085,revolve:-.22,axis:[.45,-.3,1]}
 ];
 bandSettings.forEach((setting,index)=>{
   const seedBeforeBand=randomSeed;
   const pivot=new T.Group();orbitGroup.add(pivot);
   const group=new T.Group();pivot.add(group);group.rotation.set(...setting.rotation);
   const axis=new T.Vector3(...setting.axis).normalize();
   const list=[];
   for(let i=0;i<setting.count;i++){
    const a=random()*Math.PI*2,cluster=.5+.5*Math.sin(a*3+index),r=setting.radius+(random()-.5)*(.03+cluster*.14);
    list.push({x:Math.cos(a)*r,y:Math.sin(a)*r,z:(random()-.5)*(.045+cluster*.14)+Math.sin(a*4+index)*.04,size:1.3+Math.pow(random(),2)*4.7});
   }
   const points=pointCloud(list,group,.66);
   const fineRing=mesh(new T.TorusGeometry(setting.radius,.0018,4,180),track(new T.MeshBasicMaterial({color:amber,transparent:true,opacity:.4,depthWrite:false,blending:T.AdditiveBlending})),group);
   orbitBands.push({pivot,group,points,fineRing,setting,axis,phase:0,revolution:0});
   randomSeed=seedBeforeBand;
   for(let i=0;i<setting.seedCount*7;i++)random();
 });

 // Segmented broad arcs, with fine luminous grooves and dense edge highlights.
 const arcMaterial=track(new T.ShaderMaterial({transparent:true,side:T.DoubleSide,depthWrite:false,blending:T.AdditiveBlending,
  uniforms:{uEnergy:{value:.6},uTime:{value:0}},
  vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
  fragmentShader:`varying vec2 vUv;uniform float uEnergy;uniform float uTime;
   void main(){float etch=step(.965,fract(vUv.x*104.))+step(.98,fract(vUv.y*108.));
   float grain=fract(sin(dot(vUv,vec2(12.9898,78.233)))*43758.5453);
   vec3 col=vec3(1.6,.255,.008)*(1.-etch*.34)+grain*.07;
   gl_FragColor=vec4(col*(.5+uEnergy*.8),.78*clamp(uEnergy*1.8,.05,1.));}`
 }));
 const arcSpecs=[
  {r:1.52,w:.085,start:3.25,span:2.7,rot:[.52,-.3,.14],speed:.09},
  {r:1.31,w:.055,start:3.5,span:2.6,rot:[-.25,.5,-.55],speed:-.12},
  {r:1.72,w:.06,start:.18,span:1.3,rot:[.88,.13,-.4],speed:.055}
 ];
 const arcs=[],arcEdgeMaterials=[];
 arcSpecs.forEach(spec=>{
   const group=new T.Group();hologram.add(group);group.rotation.set(...spec.rot);
   const face=mesh(new T.RingGeometry(spec.r-spec.w,spec.r,170,1,spec.start,spec.span),arcMaterial,group);
   const edgeMaterial=track(new T.MeshBasicMaterial({color:new T.Color(2.8,.65,.055),transparent:true,opacity:.8,depthWrite:false,blending:T.AdditiveBlending}));
   arcEdgeMaterials.push(edgeMaterial);
   for(const radius of [spec.r,spec.r-spec.w]){const edge=mesh(new T.TorusGeometry(radius,.003,5,130,spec.span),edgeMaterial,group);edge.rotation.z=spec.start;}
   const list=[];for(let i=0;i<230;i++){const a=spec.start+random()*spec.span,r=spec.r-random()*spec.w;list.push({x:Math.cos(a)*r,y:Math.sin(a)*r,z:.003,size:.65+random()*1.2});}
   const specks=pointCloud(list,group,.7);arcs.push({group,spec,face,specks,phase:0});
 });

 // Radial beams are slender 3D rods, not screen-space spokes.
 const rayGroup=new T.Group();hologram.add(rayGroup);
 const rays=[];
 for(let i=0;i<17;i++){
   const a=i/17*Math.PI*2+(random()-.5)*.2,z=(random()-.5)*.85;
   const dir=new T.Vector3(Math.cos(a),Math.sin(a),z).normalize();
   const length=1.43+random()*.59;
   const group=new T.Group();rayGroup.add(group);group.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),dir);
   const ray=mesh(new T.CylinderGeometry(.0045,.007,length,5,1,true),beamMaterial,group);ray.position.y=length/2;
   const tip=mesh(new T.SphereGeometry(.007,8,6),beamMaterial,group);tip.position.y=length;
   rays.push({group,length,phase:random()*6.28});
 }
 const nucleusMaterial=track(new T.MeshBasicMaterial({color:new T.Color(4.5,2.9,.65)}));
 const nucleus=mesh(new T.SphereGeometry(.12,40,24),nucleusMaterial);
 const innerHaloMaterial=track(new T.ShaderMaterial({transparent:true,depthWrite:false,blending:T.AdditiveBlending,
   uniforms:{energy:{value:.6}},
   vertexShader:'varying vec3 n;varying vec3 v;void main(){vec4 p=modelViewMatrix*vec4(position,1.);n=normalize(normalMatrix*normal);v=normalize(-p.xyz);gl_Position=projectionMatrix*p;}',
   fragmentShader:'varying vec3 n;varying vec3 v;uniform float energy;void main(){float f=pow(1.-abs(dot(normalize(n),normalize(v))),2.);gl_FragColor=vec4(1.,.36,.015,f*.12*energy);}'
 }));
 const innerHalo=mesh(new T.SphereGeometry(1.17,48,32),innerHaloMaterial);
 const innerDust=[];
 for(let i=0;i<210;i++){const dir=new T.Vector3(random()-.5,random()-.5,random()-.5).normalize().multiplyScalar(.25+random()*.78);innerDust.push({x:dir.x,y:dir.y,z:dir.z,size:.9+random()});}
 const dust=pointCloud(innerDust,sphereGroup,.3);
 const outerDust=[];
 for(let i=0;i<180;i++){const p=new T.Vector3(random()-.5,random()-.5,random()-.5).normalize().multiplyScalar(1.7+random()*.34);outerDust.push({x:p.x,y:p.y,z:p.z,size:.65+random()*1.1});}
 const dustOuter=pointCloud(outerDust,hologram,.25);

 // A scan shell breathes inward in listening mode; it remains invisible otherwise.
 const scanMaterial=track(new T.MeshBasicMaterial({color:amber,transparent:true,opacity:0,depthWrite:false,blending:T.AdditiveBlending}));
 const scan=mesh(new T.SphereGeometry(1.2,40,24),scanMaterial);scan.material.wireframe=true;

 // Lightweight real bloom: HDR scene -> threshold -> two separable blur scales -> composite.
 // No external postprocessing libraries or image assets are needed.
 const hdrType=renderer.capabilities.isWebGL2&&renderer.extensions.has('EXT_color_buffer_float')?T.HalfFloatType:T.UnsignedByteType;
 function renderTarget(){return track(new T.WebGLRenderTarget(1,1,{type:hdrType,minFilter:T.LinearFilter,magFilter:T.LinearFilter,depthBuffer:false}));}
 const sceneTarget=track(new T.WebGLRenderTarget(1,1,{type:hdrType,minFilter:T.LinearFilter,magFilter:T.LinearFilter,depthBuffer:true}));
 const brightTarget=renderTarget(),blurA=renderTarget(),blurB=renderTarget(),wideA=renderTarget(),wideB=renderTarget();
 const passScene=new T.Scene(),passCamera=new T.OrthographicCamera(-1,1,1,-1,0,1);
 const quad=new T.Mesh(track(new T.PlaneGeometry(2,2)),new T.MeshBasicMaterial());passScene.add(quad);track(quad.material);
 const passVertex='varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}';
 function shader(fragment,uniforms){return track(new T.ShaderMaterial({vertexShader:passVertex,fragmentShader:fragment,uniforms,depthTest:false,depthWrite:false}));}
 const threshold=shader(`varying vec2 vUv;uniform sampler2D source;void main(){vec3 c=texture2D(source,vUv).rgb;float l=max(c.r,max(c.g,c.b));gl_FragColor=vec4(c*smoothstep(.65,1.2,l),1.);}`,{source:{value:sceneTarget.texture}});
 const blurShader=shader(`varying vec2 vUv;uniform sampler2D source;uniform vec2 direction;
 void main(){vec3 c=texture2D(source,vUv).rgb*.227027;
 c+=(texture2D(source,vUv+direction*1.384615).rgb+texture2D(source,vUv-direction*1.384615).rgb)*.316216;
 c+=(texture2D(source,vUv+direction*3.230769).rgb+texture2D(source,vUv-direction*3.230769).rgb)*.070270;
 gl_FragColor=vec4(c,1.);}`,{source:{value:null},direction:{value:new T.Vector2()}});
 const composite=shader(`varying vec2 vUv;uniform sampler2D base;uniform sampler2D bloom;uniform sampler2D wideBloom;uniform float strength;
 vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
 void main(){vec3 c=texture2D(base,vUv).rgb;vec3 b=texture2D(bloom,vUv).rgb*.7+texture2D(wideBloom,vUv).rgb*.44;
 c=aces(c+b*strength);c=pow(c,vec3(1./2.2));gl_FragColor=vec4(c,1.);}`,{base:{value:sceneTarget.texture},bloom:{value:blurB.texture},wideBloom:{value:wideB.texture},strength:{value:.95}});
 function pass(material,target){quad.material=material;renderer.setRenderTarget(target);renderer.render(passScene,passCamera);}
 function blur(input,output,x,y){blurShader.uniforms.source.value=input.texture;blurShader.uniforms.direction.value.set(x,y);pass(blurShader,output);}
 function render(){
   renderer.setRenderTarget(sceneTarget);renderer.setClearColor('#060609',1);renderer.render(scene,camera);
   pass(threshold,brightTarget);
   blur(brightTarget,blurA,1/brightTarget.width,0);blur(blurA,blurB,0,1/brightTarget.height);
   blur(blurB,wideA,2/brightTarget.width,0);blur(wideA,wideB,0,2/brightTarget.height);
   pass(composite,null);
 }
 function resize(){
   const w=stage.clientWidth,h=stage.clientHeight,dpr=renderer.getPixelRatio();renderer.setSize(w,h,false);camera.aspect=w/h;
   const verticalHalfFov=T.MathUtils.degToRad(camera.fov/2);
   const limitingHalfFov=Math.atan(Math.tan(verticalHalfFov)*Math.min(1,camera.aspect));
   camera.position.z=2.65/Math.sin(limitingHalfFov);camera.updateProjectionMatrix();
   const width=Math.round(w*dpr),height=Math.round(h*dpr);sceneTarget.setSize(width,height);
   for(const target of [brightTarget,blurA,blurB,wideA,wideB])target.setSize(Math.max(1,Math.round(width/2)),Math.max(1,Math.round(height/2)));
 }
 const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(stage);resize();

 // State controller. Voice amplitude can be driven by real STT/TTS audio later.
 const states={
  idle:{speed:.22,energy:.64,spread:1,description:'Slow orbital drift. Steady central light.'},
  listening:{speed:.4,energy:.8,spread:.96,description:'Inward scan pulses. Focused particle motion.'},
  thinking:{speed:.48,energy:.9,spread:1.02,description:'Gentle increase in orbital pace. Focused lattice.'},
  speaking:{speed:.5,energy:.8,spread:1,description:'Voice-reactive nucleus, beams and particle glow.'},
  sleeping:{speed:0,energy:.09,spread:.91,description:'Dim nucleus. Settled orbits. Almost motionless.'}
 };
 let state='idle',current={...states.idle},audioLevel=null,level=0;
 let time=0,motionTime=0,last=performance.now(),disposed=false;
 let sequence=false,sequenceStart=0,animationId=0,visible=true;
 let viewX=.08,viewY=-.12,targetX=.08,targetY=-.12,dragging=false,lastX=0,lastY=0;
 const media=window.matchMedia('(prefers-reduced-motion: reduce)');
 const stateLabel=root.querySelector('.j-state-name'),detail=root.querySelector('.g-detail'),dot=root.querySelector('.g-dot');
 const buttons=Array.from(root.querySelectorAll('button[data-state]')),sequenceButton=root.querySelector('.j-sequence');
 const bars=Array.from({length:35},()=>{const e=document.createElement('span');root.querySelector('.j-wave').appendChild(e);return e;});
 function setState(next){
  if(!Object.prototype.hasOwnProperty.call(states,next))throw new RangeError('Unknown core state: '+next);
  state=next;stateLabel.textContent=next.charAt(0).toUpperCase()+next.slice(1);detail.textContent=states[next].description;
  buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.state===next)));
  dot.style.opacity=next==='sleeping'?'.35':'1';
 }
 function setAudioLevel(value){audioLevel=value===null?null:Math.min(1,Math.max(0,Number(value)||0));}
 function stopSequence(){sequence=false;sequenceButton.textContent='Play sequence';sequenceButton.setAttribute('aria-pressed','false');}
 const buttonHandlers=[];
 buttons.forEach(b=>{const fn=()=>{stopSequence();setState(b.dataset.state);};b.addEventListener('click',fn);buttonHandlers.push([b,fn]);});
 const onSequence=()=>{if(sequence){stopSequence();return;}sequence=true;sequenceStart=time;sequenceButton.textContent='Stop sequence';sequenceButton.setAttribute('aria-pressed','true');setState('idle');};sequenceButton.addEventListener('click',onSequence);
 const onDown=e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId);};
 const onMove=e=>{if(!dragging)return;targetY+=(e.clientX-lastX)*.006;targetX=Math.min(.8,Math.max(-.8,targetX+(e.clientY-lastY)*.005));lastX=e.clientX;lastY=e.clientY;};
 const onUp=()=>dragging=false;
 const resetView=()=>{targetX=.08;targetY=-.12;};
 canvas.addEventListener('pointerdown',onDown);canvas.addEventListener('pointermove',onMove);canvas.addEventListener('pointerup',onUp);canvas.addEventListener('pointercancel',onUp);canvas.addEventListener('dblclick',resetView);
 const allClouds=[nodeCloud,dust,dustOuter,...orbitBands.map(b=>b.points),...arcs.map(a=>a.specks)];
 function animate(now){
   if(disposed||!visible)return;
   const dt=Math.min((now-last)/1000,.05);last=now;time+=dt;
   if(sequence){const order=['idle','listening','thinking','speaking','sleeping'];const next=order[Math.floor((time-sequenceStart)/4)%order.length];if(next!==state)setState(next);}
   const smooth=1-Math.exp(-dt*4),target=states[state];
   for(const k of ['speed','energy','spread'])current[k]+=(target[k]-current[k])*smooth;
   const reduced=media.matches,movement=reduced?0:1;
   motionTime+=dt*current.speed*movement;
   const simulation=(.4+.6*Math.abs(Math.sin(time*3.2)))*(.24+.76*Math.abs(Math.sin(time*11.3)*Math.cos(time*4.1)));
   const requested=state==='speaking'?(audioLevel===null?simulation:audioLevel):state==='listening'?(audioLevel===null?.08+.14*Math.sin(time*3.6)**2:audioLevel):0;
   level+=(requested-level)*(1-Math.exp(-dt*16));
   const breath=reduced?0:Math.sin(time*1.3)*.018;
   const energy=current.energy+level*.64+breath;
   viewX+=(targetX-viewX)*smooth;viewY+=(targetY-viewY)*smooth;
   hologram.rotation.set(viewX,viewY,0);
   hologram.scale.setScalar(current.spread+level*.018*movement);
   sphereGroup.rotation.set(motionTime*.13,motionTime*.19,motionTime*.11);
   orbitBands.forEach((band,i)=>{
     band.phase+=dt*current.speed*band.setting.speed*movement;
     band.revolution=(band.revolution+dt*current.speed*band.setting.revolve*movement)%(Math.PI*2);
     band.pivot.quaternion.setFromAxisAngle(band.axis,band.revolution);
     band.group.rotation.z=band.setting.rotation[2]+band.phase;
     band.group.rotation.y=band.setting.rotation[1]+Math.sin(motionTime*.24+i)*.1*movement;
     band.fineRing.material.opacity=.12+energy*.22;
   });
   arcs.forEach(arc=>{arc.phase+=dt*current.speed*arc.spec.speed*movement;arc.group.rotation.z=arc.spec.rot[2]+arc.phase;});
   rayGroup.rotation.z=motionTime*.045;rayGroup.rotation.y=Math.sin(motionTime*.19)*.13;
   const speakingPulse=state==='speaking'&&!reduced?(.5+.5*Math.sin(time*17))*(.25+level*.75):0;
   rays.forEach(ray=>{ray.group.scale.y=1+level*.16*movement+speakingPulse*.025*movement+Math.sin(motionTime*.5+ray.phase)*.012*movement;});
   nucleus.scale.setScalar(.9+energy*.15+level*.28*movement+speakingPulse*.045*movement);
   nucleusMaterial.color.setRGB(3.5,2.15,.37).multiplyScalar((.03+Math.pow(Math.max(0,energy),1.7))*(1+speakingPulse*.08));
   lineMaterial.opacity=.1+energy*.57;fineMaterial.opacity=.06+energy*.25;
   beamMaterial.opacity=.055+energy*.6;
   arcEdgeMaterials.forEach(m=>m.opacity=Math.min(.9,energy*1.3));
   arcMaterial.uniforms.uEnergy.value=energy;arcMaterial.uniforms.uTime.value=motionTime;
   facetsMaterial.uniforms.energy.value=energy;innerHaloMaterial.uniforms.energy.value=energy;
   allClouds.forEach((cloud,i)=>{cloud.material.uniforms.uTime.value=reduced?0:state==='sleeping'?time*.12:time;cloud.material.uniforms.uEnergy.value=energy*(i===2?.32:.68);});
   const scanPhase=(time*.4)%1;
   scan.scale.setScalar(1.1-scanPhase*.3);scan.material.opacity=state==='listening'&&!reduced?Math.sin(scanPhase*Math.PI)*.027:0;
   composite.uniforms.strength.value=.72+energy*.28;
   bars.forEach((bar,i)=>{const shape=Math.sin((i+1)/36*Math.PI);const fluctuation=reduced?.5:.2+.8*Math.abs(Math.sin(time*9+i*.68));const amp=state==='speaking'?level*fluctuation:state==='listening'?level*fluctuation:state==='thinking'?.23*fluctuation:state==='idle'?.045:0;bar.style.height=(3+27*amp*shape)+'px';bar.style.opacity=state==='sleeping'?'.2':'.8';});
   render();animationId=requestAnimationFrame(animate);
 }
 function dispose(){
   if(disposed)return;disposed=true;cancelAnimationFrame(animationId);resizeObserver.disconnect();
   buttonHandlers.forEach(([b,fn])=>b.removeEventListener('click',fn));sequenceButton.removeEventListener('click',onSequence);
   canvas.removeEventListener('pointerdown',onDown);canvas.removeEventListener('pointermove',onMove);canvas.removeEventListener('pointerup',onUp);canvas.removeEventListener('pointercancel',onUp);canvas.removeEventListener('dblclick',resetView);
   document.removeEventListener('visibilitychange',onVisibility);window.removeEventListener('pagehide',dispose);
   [...new Set(resources)].forEach(r=>r.dispose());renderer.dispose();
 }
 function onVisibility(){visible=!document.hidden;if(visible&&!disposed){last=performance.now();animationId=requestAnimationFrame(animate);}else cancelAnimationFrame(animationId);}
 document.addEventListener('visibilitychange',onVisibility);window.addEventListener('pagehide',dispose,{once:true});
 window.jarvisCore={setState,setAudioLevel,getState:()=>state,resetView,dispose};
 loading.hidden=true;
 render();animationId=requestAnimationFrame(animate);
})();

