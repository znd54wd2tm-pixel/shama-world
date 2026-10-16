/* Lazy-loaded, local Three.js scene. No CDN dependency at runtime. */
import * as THREE from './vendor/three.module.js';

export function createCaseScene(host, data, { preview = false } = {}) {
  let renderer, frame = 0, disposed = false, complete = null;
  const textures = new Set(), geometries = new Set(), materials = new Set();
  const fallback = () => {
    host.dataset.renderer = 'fallback';
    host.querySelector('canvas')?.remove();
    if (complete) { complete(); complete = null; }
  };
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
  } catch (_) {
    fallback();
    return { play: () => Promise.resolve(), dispose() {} };
  }
  host.dataset.renderer = 'three';
  host.appendChild(renderer.domElement);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.5;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, 1, .1, 80);
  camera.position.set(4.1, 3, 6.5);
  camera.lookAt(0, .6, 0);
  scene.add(new THREE.HemisphereLight(0xfff4df, 0x333941, 3));
  [[0xffe3a0, 60, -3, 5, 3], [0xffffff, 90, 4, 4, -2], [0xb8c5cf, 35, -4, 2, -3]].forEach(([color, intensity, x, y, z]) => {
    const light = new THREE.PointLight(color, intensity, 25); light.position.set(x, y, z); scene.add(light);
  });
  // A small generated environment gives the metal broad studio reflections.
  const envCanvas = document.createElement('canvas'); envCanvas.width = 256; envCanvas.height = 128;
  const ctx = envCanvas.getContext('2d'); ctx.fillStyle = '#252a2e'; ctx.fillRect(0, 0, 256, 128);
  ctx.fillStyle = '#e3d4b0'; ctx.fillRect(30, 5, 20, 100); ctx.fillStyle = '#b2b9bc'; ctx.fillRect(150, 15, 45, 80);
  const env = new THREE.CanvasTexture(envCanvas); env.mapping = THREE.EquirectangularReflectionMapping; textures.add(env); scene.environment = env;
  const seed = [...data.name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  const style = data.style || 'carbon';
  const goldColor = { bronze: 0xaf7843, platinum: 0xb9c3c9, gold: 0xd9ae51, imperial: 0xf0cf7d, carbon: 0xc2a36a }[style] || 0xd9ae51;
  const material = (params) => { const mat = new THREE.MeshStandardMaterial(params); materials.add(mat); return mat; };
  const black = material({ color: 0x111418, metalness: .65, roughness: .28 });
  const gold = material({ color: goldColor, metalness: .94, roughness: .2 });
  const dark = material({ color: 0x050607, metalness: .3, roughness: .6 });
  const lightMat = material({ color: 0xffd887, emissive: 0xffbb48, emissiveIntensity: 3 });
  const body = new THREE.Group(); scene.add(body);
  const box = (w, h, d, mat, parent, x = 0, y = 0, z = 0) => {
    const geo = new THREE.BoxGeometry(w, h, d); geometries.add(geo);
    const mesh = new THREE.Mesh(geo, mat); mesh.position.set(x, y, z); parent.add(mesh); return mesh;
  };
  const width = 2.5 + (seed % 3) * .13, depth = 1.6 + (seed % 2) * .15;
  box(width, 1.05, depth, black, body, 0, .65);
  box(width - .08, .06, depth - .08, gold, body, 0, 1.2);
  const lid = new THREE.Group(); lid.position.set(0, 1.22, -depth / 2); body.add(lid);
  box(width + .04, .28, depth + .04, black, lid, 0, .14, depth / 2);
  box(width + .08, .035, depth + .08, gold, lid, 0, 0, depth / 2);
  const bands = style === 'imperial' ? [-.9, -.5, .5, .9] : [-.85, .85];
  bands.forEach((x) => {
    box(.10, 1.06, depth + .035, gold, body, x, .65);
    box(.11, .32, depth + .07, gold, lid, x, .14, depth / 2);
  });
  for (const x of [-width/2, width/2]) for (const z of [-depth/2, depth/2]) box(.17, 1.14, .17, gold, body, x, .66, z);
  [-.55, .55].forEach((x) => { box(.21, .3, .10, gold, body, x, 1.05, depth/2+.07); box(.075, .1, .025, dark, body, x, 1.05, depth/2+.13); });
  box(.62, .09, .10, gold, lid, 0, .48, depth/2); box(.09, .20, .10, gold, lid, -.27, .37, depth/2); box(.09, .20, .10, gold, lid, .27, .37, depth/2);
  const label = document.createElement('canvas'); label.width = 512; label.height = 256;
  const lc = label.getContext('2d'); lc.fillStyle = '#101214'; lc.fillRect(0,0,512,256); lc.strokeStyle = '#b5985c'; lc.lineWidth = 3; lc.strokeRect(8,8,496,240);
  lc.fillStyle = '#e0c38a'; lc.textAlign = 'center'; lc.font = '24px Arial'; lc.fillText('SHAMA WORLD',256,70); lc.font = 'bold 27px Arial';
  data.name.split(' ').length > 2 ? (lc.fillText(data.name.split(' ').slice(0,-1).join(' '),256,132),lc.fillText('CASE',256,172)) : lc.fillText(data.name,256,145);
  lc.font = '15px Arial'; lc.fillText(`VAULT / ${String(data.id).padStart(3,'0')}`,256,214);
  const tex = new THREE.CanvasTexture(label); tex.colorSpace = THREE.SRGBColorSpace; textures.add(tex);
  box(1.05, .51, .016, material({ map:tex, metalness:.35, roughness:.45 }), body, 0,.61,depth/2+.035);
  if (style === 'imperial') {
    for (let i = -2; i <= 2; i++) box(.10,.25 + (2-Math.abs(i))*.09,.13,gold,lid,i*.16,.4,depth*.65);
  }
  const inside = new THREE.PointLight(0xffd780,0,8); inside.position.set(0,1.3,0); body.add(inside);
  const shadowCanvas=document.createElement('canvas'); shadowCanvas.width=128;shadowCanvas.height=128;
  const sc=shadowCanvas.getContext('2d'),gradient=sc.createRadialGradient(64,64,2,64,64,64);
  gradient.addColorStop(0,'rgba(0,0,0,.9)');gradient.addColorStop(1,'rgba(0,0,0,0)');sc.fillStyle=gradient;sc.fillRect(0,0,128,128);
  const shadowTexture=new THREE.CanvasTexture(shadowCanvas);textures.add(shadowTexture);
  const shadowMaterial=new THREE.MeshBasicMaterial({map:shadowTexture,transparent:true,depthWrite:false});materials.add(shadowMaterial);
  const shadowGeometry=new THREE.PlaneGeometry(4.7,3.6);geometries.add(shadowGeometry);
  const floor=new THREE.Mesh(shadowGeometry,shadowMaterial);floor.rotation.x=-Math.PI/2;floor.position.y=.02;scene.add(floor);
  const resize = () => { if (disposed) return; const rect = host.getBoundingClientRect(); const w = Math.max(1,rect.width),h = Math.max(1,rect.height); renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix(); };
  const observer = new ResizeObserver(resize); observer.observe(host); resize();
  let started = 0, playing = false;
  const draw = (now) => {
    if (disposed) return;
    if (playing) {
      const t = (now-started)/1000;
      const drop = Math.min(1,t/.72);
      body.position.y = drop < 1 ? 3.8*(1-drop*drop) : Math.max(0,.18*Math.sin((t-.72)*16)*Math.exp(-(t-.72)*7));
      const open = Math.max(0,Math.min(1,(t-.9)/.8));
      lid.rotation.x = -1.95*(1-Math.pow(1-open,3));
      inside.intensity = open*30;
      camera.position.z = 6.5-Math.min(1,t/1.8)*1.3;
      if (t>=2) { playing=false; complete?.(); complete=null; }
    } else if (preview && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) body.rotation.y = Math.sin(now/2000)*.10;
    camera.lookAt(0,.65,0); renderer.render(scene,camera);
    frame=requestAnimationFrame(draw);
  };
  const lost = (event) => { event.preventDefault(); cancelAnimationFrame(frame); fallback(); };
  renderer.domElement.addEventListener('webglcontextlost',lost);
  frame=requestAnimationFrame(draw);
  return {
    play: () => new Promise((resolve) => { complete=resolve; started=performance.now(); playing=true; }),
    dispose() {
      if (disposed) return; disposed=true; complete?.(); complete=null; cancelAnimationFrame(frame); observer.disconnect();
      renderer.domElement.removeEventListener('webglcontextlost',lost);
      geometries.forEach((g)=>g.dispose()); materials.forEach((m)=>m.dispose()); textures.forEach((t)=>t.dispose());
      scene.clear(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
    }
  };
}
