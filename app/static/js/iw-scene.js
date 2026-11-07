// Latar 3D partikel untuk Informatika World.
// <canvas id="iw-scene" data-variant="globe|stream" data-anchor="right|center">
//   globe  : bola titik-titik dengan paket data yang berjalan di antara simpul (guru & login)
//   stream : aliran partikel melengkung seperti kabel data (siswa)
// Kalau WebGL tidak tersedia, halaman tetap jalan dengan latar CSS biasa.
import * as THREE from "three";

const canvas = document.getElementById("iw-scene");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const PALETTE = {
  teal: new THREE.Color("#2fe0c5"),
  mint: new THREE.Color("#b9fff1"),
  white: new THREE.Color("#f2faf8"),
  amber: new THREE.Color("#f6c56b"),
  coral: new THREE.Color("#ff8a66"),
  deep: new THREE.Color("#0f8f80"),
};

const pointShader = {
  vertexShader: /* glsl */ `
    attribute float aSize;
    attribute vec3 aColor;
    uniform float uPixelRatio;
    uniform float uNear;
    uniform float uFar;
    varying vec3 vColor;
    varying float vFade;
    void main() {
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      gl_Position = projectionMatrix * mv;
      gl_PointSize = aSize * uPixelRatio * (8.0 / -mv.z);
      vColor = aColor;
      vFade = 1.0 - smoothstep(uNear, uFar, -mv.z);
    }
  `,
  fragmentShader: /* glsl */ `
    uniform float uOpacity;
    varying vec3 vColor;
    varying float vFade;
    void main() {
      float d = length(gl_PointCoord - 0.5);
      float a = smoothstep(0.5, 0.05, d);
      gl_FragColor = vec4(vColor, a * uOpacity * (0.25 + 0.75 * vFade));
    }
  `,
};

function pointsMaterial(opacity, near, far, pixelRatio) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uPixelRatio: { value: pixelRatio },
      uOpacity: { value: opacity },
      uNear: { value: near },
      uFar: { value: far },
    },
    vertexShader: pointShader.vertexShader,
    fragmentShader: pointShader.fragmentShader,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
}

function pick(weights) {
  let r = Math.random();
  for (const [color, w] of weights) {
    if ((r -= w) <= 0) return color;
  }
  return weights[0][0];
}

// ---------- Varian 1: globe jaringan ----------
function buildGlobe(pixelRatio) {
  const group = new THREE.Group();
  const radius = 1.6;
  const count = 2400;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const nodes = [];
  const golden = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    const jitter = radius * (1 + (Math.random() - 0.5) * 0.04);
    const v = new THREE.Vector3(Math.cos(theta) * r, y, Math.sin(theta) * r).multiplyScalar(jitter);
    v.toArray(positions, i * 3);
    const c = pick([[PALETTE.teal, 0.55], [PALETTE.mint, 0.25], [PALETTE.white, 0.12], [PALETTE.amber, 0.08]]);
    c.toArray(colors, i * 3);
    sizes[i] = 1.6 + Math.random() * 2.8;
    if (i % 97 === 0) nodes.push(v);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
  geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
  group.add(new THREE.Points(geo, pointsMaterial(0.85, 4.5, 8.5, pixelRatio)));

  // Busur antar simpul + paket data yang berjalan di atasnya
  const arcs = [];
  const lineMat = new THREE.LineBasicMaterial({ color: PALETTE.teal, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false });
  for (let i = 0; i < 16; i++) {
    const a = nodes[Math.floor(Math.random() * nodes.length)];
    const b = nodes[Math.floor(Math.random() * nodes.length)];
    if (a === b || a.distanceTo(b) < 0.9) continue;
    const mid = a.clone().add(b).multiplyScalar(0.5).normalize().multiplyScalar(radius * (1.25 + a.distanceTo(b) * 0.12));
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)), lineMat));
    arcs.push({ curve, t: Math.random(), speed: 0.08 + Math.random() * 0.12 });
  }

  const packetPos = new Float32Array(arcs.length * 3);
  const packetCol = new Float32Array(arcs.length * 3);
  const packetSize = new Float32Array(arcs.length).fill(9);
  arcs.forEach((_, i) => (i % 3 === 0 ? PALETTE.amber : PALETTE.white).toArray(packetCol, i * 3));
  const packetGeo = new THREE.BufferGeometry();
  packetGeo.setAttribute("position", new THREE.BufferAttribute(packetPos, 3));
  packetGeo.setAttribute("aColor", new THREE.BufferAttribute(packetCol, 3));
  packetGeo.setAttribute("aSize", new THREE.BufferAttribute(packetSize, 1));
  group.add(new THREE.Points(packetGeo, pointsMaterial(1, 4.5, 8.5, pixelRatio)));

  const tmp = new THREE.Vector3();
  return {
    group,
    baseSize: radius * 2.6,
    update(dt, time) {
      group.rotation.y = time * 0.06;
      group.rotation.x = Math.sin(time * 0.15) * 0.08 + 0.25;
      arcs.forEach((arc, i) => {
        arc.t = (arc.t + dt * arc.speed) % 1;
        arc.curve.getPoint(arc.t, tmp).toArray(packetPos, i * 3);
      });
      packetGeo.attributes.position.needsUpdate = true;
    },
  };
}

// ---------- Varian 2: aliran data ----------
function buildStream(pixelRatio) {
  const group = new THREE.Group();
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-3.4, -1.6, -0.6),
    new THREE.Vector3(-1.6, -0.9, 0.3),
    new THREE.Vector3(-0.2, 0.1, 0.0),
    new THREE.Vector3(0.9, 1.1, -0.4),
    new THREE.Vector3(1.6, 2.6, 0.2),
  ]);
  const count = 3200;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const seeds = [];

  for (let i = 0; i < count; i++) {
    seeds.push({
      t: Math.random(),
      angle: Math.random() * Math.PI * 2,
      radius: 0.18 + Math.pow(Math.random(), 0.6) * 0.32,
      speed: 0.018 + Math.random() * 0.02,
      spin: (Math.random() - 0.5) * 0.6,
    });
    const c = pick([[PALETTE.teal, 0.4], [PALETTE.mint, 0.18], [PALETTE.amber, 0.24], [PALETTE.coral, 0.1], [PALETTE.white, 0.08]]);
    c.toArray(colors, i * 3);
    sizes[i] = 2 + Math.random() * 3.6;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
  geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
  group.add(new THREE.Points(geo, pointsMaterial(0.8, 3.5, 9, pixelRatio)));

  const p = new THREE.Vector3();
  const tangent = new THREE.Vector3();
  const normal = new THREE.Vector3();
  const binormal = new THREE.Vector3();
  const up = new THREE.Vector3(0, 0, 1);

  function place(dt) {
    for (let i = 0; i < count; i++) {
      const s = seeds[i];
      s.t = (s.t + dt * s.speed) % 1;
      s.angle += dt * s.spin;
      curve.getPointAt(s.t, p);
      curve.getTangentAt(s.t, tangent);
      normal.crossVectors(tangent, up).normalize();
      binormal.crossVectors(tangent, normal).normalize();
      // tabung sedikit membesar di tengah supaya terasa bervolume
      const swell = 1 + Math.sin(s.t * Math.PI) * 0.5;
      const r = s.radius * swell;
      positions[i * 3] = p.x + (normal.x * Math.cos(s.angle) + binormal.x * Math.sin(s.angle)) * r;
      positions[i * 3 + 1] = p.y + (normal.y * Math.cos(s.angle) + binormal.y * Math.sin(s.angle)) * r;
      positions[i * 3 + 2] = p.z + (normal.z * Math.cos(s.angle) + binormal.z * Math.sin(s.angle)) * r;
    }
    geo.attributes.position.needsUpdate = true;
  }
  place(0);

  return {
    group,
    baseSize: 5.2,
    update(dt, time) {
      place(dt);
      group.rotation.y = Math.sin(time * 0.12) * 0.25;
      group.rotation.x = Math.sin(time * 0.09) * 0.08;
    },
  };
}

function start() {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "low-power" });
  } catch (err) {
    return; // tanpa WebGL: latar CSS sudah cukup
  }
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.75);
  renderer.setPixelRatio(pixelRatio);
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 50);
  camera.position.set(0, 0, 7);

  const variant = canvas.dataset.variant === "stream" ? buildStream(pixelRatio) : buildGlobe(pixelRatio);
  const holder = new THREE.Group();
  holder.add(variant.group);
  scene.add(holder);

  const anchor = canvas.dataset.anchor || "right";
  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };

  function layout() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    const viewH = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.z;
    const viewW = viewH * camera.aspect;
    const mobile = w < 860;
    let scale;
    if (mobile) {
      // HP: objek di bagian atas, di atas judul
      scale = Math.min(viewW * 0.9, viewH * 0.36) / variant.baseSize;
      holder.position.set(viewW * 0.12, viewH * 0.32, 0);
    } else if (anchor === "center") {
      scale = Math.min(viewW, viewH) * 0.62 / variant.baseSize;
      holder.position.set(0, 0, 0);
    } else {
      scale = Math.min(viewW * 0.42, viewH * 0.72) / variant.baseSize;
      holder.position.set(viewW * 0.27, viewH * 0.12, 0);
    }
    holder.scale.setScalar(scale);
  }
  layout();
  window.addEventListener("resize", layout);

  window.addEventListener("pointermove", (e) => {
    pointer.tx = (e.clientX / window.innerWidth - 0.5) * 2;
    pointer.ty = (e.clientY / window.innerHeight - 0.5) * 2;
  }, { passive: true });

  const clock = new THREE.Clock();
  let running = !reduceMotion;
  let frame = 0;

  function render() {
    const dt = Math.min(clock.getDelta(), 0.05);
    const time = clock.elapsedTime;
    variant.update(dt, time);
    pointer.x += (pointer.tx - pointer.x) * 0.04;
    pointer.y += (pointer.ty - pointer.y) * 0.04;
    holder.rotation.y = pointer.x * 0.18;
    holder.rotation.x = pointer.y * 0.1;
    renderer.render(scene, camera);
    if (frame++ === 1) canvas.classList.add("is-ready");
  }

  function loop() {
    if (!running) return;
    render();
    requestAnimationFrame(loop);
  }

  if (reduceMotion) {
    // gerak dikurangi: tampilkan satu bingkai diam saja
    variant.update(0, 4);
    render();
    render();
    canvas.classList.add("is-ready");
  } else {
    loop();
  }

  document.addEventListener("visibilitychange", () => {
    if (reduceMotion) return;
    const visible = document.visibilityState === "visible";
    if (visible && !running) {
      running = true;
      clock.getDelta();
      loop();
    } else if (!visible) {
      running = false;
    }
  });
}

if (canvas) start();
