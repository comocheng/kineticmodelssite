// The 3D flame of the home page hero (database/templates/database/home.html).
//
// Three nested low-poly shells glow additively, so the core turns yellow-white where they overlap
// and the edges stay deep orange, as in a real flame. The shells rotate at different speeds, noise
// that rises through their vertices makes the tongues lick upward, and species from the database
// rise from the tips under the names that most models give them.
// The SVG flame stays in the page and shows when WebGL does not start or the visitor asks for
// reduced motion. Three.js is vendored: database/static/database/vendor/three-0.160.0/.

const HEIGHT = 1.7;      // flame height in scene units
const RADIUS = 0.58;     // widest radius, a third of the way up
const RINGS = 11;        // rings of vertices from base to tip
const SIDES = 10;        // vertices around each ring
const LABELS_IN_AIR = 7;  // species names rising at one time
const LABEL_LIFE = 4.2;   // seconds from release to fade-out
const LABEL_HEIGHT = 0.16;  // scene units; larger on small canvases so the names stay legible

// [scale, heat offset, brightness, noise seed, spin in rad/s]; the inner shells sit lower and hotter
const SHELLS = [
    [1.0, -0.22, 0.42, 1.0, 0.45],
    [0.74, 0.05, 0.4, 2.0, 0.6],
    [0.48, 0.4, 0.42, 3.0, 0.8],
];

// 3D simplex noise, Ian McEwan and Stefan Gustavson (Ashima Arts), MIT license
const NOISE = `
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 10.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
float snoise(vec3 v) {
    const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0))
        + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.5 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
    m = m * m;
    return 105.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}
`;

const VERTEX = `
uniform float uTime;
uniform float uSeed;
uniform float uHeat;
attribute float aT;
attribute vec3 aCenter;
varying vec3 vView;
varying float vHeat;
${NOISE}
void main() {
    vec3 p = position;
    float angle = atan(p.z, p.x);
    // Noise that moves up the flame: the radius breathes and the upper rings lick upward
    float n = snoise(vec3(cos(angle) * 0.9 + uSeed, sin(angle) * 0.9, aT * 2.2 - uTime * 1.4));
    float lift = aT * aT;
    p.xz *= 1.0 + 0.16 * n * aT;
    p.y += 0.26 * lift * n + 0.26 * lift * aT * sin(uTime * 2.3 + angle * 3.0 + uSeed);
    p.x += 0.05 * lift * sin(uTime * 1.7 + uSeed);
    // One heat per facet (aCenter is the same at its three corners): hot low and inside, cool at the tips
    float h = snoise(aCenter * 2.5 + vec3(uSeed, -uTime * 1.2, 0.0));
    vHeat = clamp(1.0 - 0.75 * (aCenter.y / ${HEIGHT.toFixed(1)}) + 0.25 * h + uHeat, 0.0, 1.0);
    vec4 view = modelViewMatrix * vec4(p, 1.0);
    vView = view.xyz;
    gl_Position = projectionMatrix * view;
}
`;

// The colour stops of the SVG flame; 0.3 is the Figma accent #CE4801
const FRAGMENT = `
uniform float uBrightness;
varying vec3 vView;
varying float vHeat;
vec3 ramp(float h) {
    vec3 c0 = vec3(0.424, 0.153, 0.0);
    vec3 c1 = vec3(0.808, 0.282, 0.004);
    vec3 c2 = vec3(0.949, 0.416, 0.071);
    vec3 c3 = vec3(1.0, 0.604, 0.180);
    vec3 c4 = vec3(1.0, 0.824, 0.478);
    if (h < 0.3) return mix(c0, c1, h / 0.3);
    if (h < 0.55) return mix(c1, c2, (h - 0.3) / 0.25);
    if (h < 0.78) return mix(c2, c3, (h - 0.55) / 0.23);
    return mix(c3, c4, (h - 0.78) / 0.22);
}
void main() {
    // Flat facets: the normal comes from the screen-space slope of the triangle
    vec3 n = normalize(cross(dFdx(vView), dFdy(vView)));
    float key = abs(dot(n, normalize(vec3(-0.5, 0.6, 0.65))));
    float rim = pow(1.0 - abs(dot(n, normalize(-vView))), 2.0);
    vec3 colour = ramp(vHeat) * (0.35 + 0.85 * key) + rim * vec3(1.0, 0.45, 0.1) * 0.35;
    gl_FragColor = vec4(colour * uBrightness, 1.0);
}
`;

function random(seed) {
    // mulberry32: a small seeded generator, so each shell keeps its shape between visits
    return () => {
        seed = (seed + 0x6d2b79f5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

function flameGeometry(THREE, seed) {
    // A teardrop lathe with jittered vertices and three static tongues, as unindexed facets
    const rand = random(seed * 9973);
    const base = [0, 0, 0, 0];
    const tip = [0.04 * (rand() - 0.5), HEIGHT * 1.08, 0.04 * (rand() - 0.5), 1];
    const rings = [];
    for (let j = 1; j < RINGS; j++) {
        const t = j / RINGS;
        const radius = (RADIUS / 0.423) * t ** 0.45 * (1 - t) ** 0.9;
        const ring = [];
        for (let i = 0; i < SIDES; i++) {
            const angle = (2 * Math.PI * (i + 0.5 * (j % 2))) / SIDES + (rand() - 0.5) * 0.25;
            const r = radius * (1 + (rand() - 0.5) * 0.18);
            const tongue = 0.6 * t ** 3 * Math.max(0, Math.sin(3 * angle + 0.7)) ** 2;
            ring.push([r * Math.cos(angle), t * HEIGHT + (rand() - 0.5) * 0.04 + tongue, r * Math.sin(angle), t]);
        }
        rings.push(ring);
    }
    const faces = [];
    const first = rings[0];
    const last = rings[rings.length - 1];
    for (let i = 0; i < SIDES; i++) {
        const k = (i + 1) % SIDES;
        faces.push([base, first[k], first[i]], [last[i], last[k], tip]);
        for (let j = 0; j < rings.length - 1; j++) {
            const [a, b, c, d] = [rings[j][i], rings[j][k], rings[j + 1][i], rings[j + 1][k]];
            faces.push([a, b, c], [b, d, c]);
        }
    }
    const position = new Float32Array(faces.length * 9);
    const center = new Float32Array(faces.length * 9);
    const height = new Float32Array(faces.length * 3);
    faces.forEach((face, f) => {
        const c = [0, 1, 2].map((axis) => (face[0][axis] + face[1][axis] + face[2][axis]) / 3);
        face.forEach((v, corner) => {
            position.set(v.slice(0, 3), f * 9 + corner * 3);
            center.set(c, f * 9 + corner * 3);
            height[f * 3 + corner] = v[3];
        });
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
    geometry.setAttribute("aCenter", new THREE.BufferAttribute(center, 3));
    geometry.setAttribute("aT", new THREE.BufferAttribute(height, 1));
    return geometry;
}

function labelTexture(THREE, name) {
    // A glowing species name on a transparent canvas. A digit after a letter, ")" or another
    // subscript digit is a subscript, so CH3OH reads as CH₃OH and a leading digit stays full size.
    const px = 64;
    const font = (size) => `600 ${size}px "Instrument Sans", Inter, "Helvetica Neue", Arial, sans-serif`;
    const runs = [];
    for (const ch of name) {
        const previous = runs[runs.length - 1];
        const sub = /\d/.test(ch) && previous && (/[A-Za-z)\]]$/.test(previous.text) || previous.sub);
        if (previous && previous.sub === Boolean(sub)) previous.text += ch;
        else runs.push({ text: ch, sub: Boolean(sub) });
    }
    const ctx = document.createElement("canvas").getContext("2d");
    const pad = 24;
    let width = 0;
    runs.forEach((run) => {
        ctx.font = font(run.sub ? px * 0.62 : px);
        run.width = ctx.measureText(run.text).width;
        width += run.width;
    });
    ctx.canvas.width = Math.ceil(width + 2 * pad);
    ctx.canvas.height = Math.ceil(px * 1.4 + 2 * pad);
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = "#ffe2bd";
    ctx.shadowColor = "rgba(255, 122, 51, 0.95)";
    for (const blur of [18, 6]) {
        ctx.shadowBlur = blur;
        let x = pad;
        runs.forEach((run) => {
            ctx.font = font(run.sub ? px * 0.62 : px);
            ctx.fillText(run.text, x, pad + px * 1.05 + (run.sub ? px * 0.22 : 0));
            x += run.width;
        });
    }
    const texture = new THREE.CanvasTexture(ctx.canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return { texture, aspect: ctx.canvas.width / ctx.canvas.height };
}

function speciesParticles(THREE, names) {
    // Each particle is one species record of the database (see database/services/landing.py),
    // released from the tips in turn and fading as it rises
    const rand = random(42);
    const labels = names.map((name) => labelTexture(THREE, name));
    const group = new THREE.Group();
    group.userData.scale = 1;
    let next = 0;
    const slots = Array.from({ length: Math.min(LABELS_IN_AIR, labels.length) }, () => {
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
            transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        }));
        group.add(sprite);
        return { sprite };
    });
    // One name leaves every LABEL_LIFE / slots seconds, alternating sides, so names rarely overlap
    const release = (p, age) => {
        const side = next % 2 ? 1 : -1;
        p.label = labels[next++ % labels.length];
        p.sprite.material.map = p.label.texture;
        Object.assign(p, {
            x: side * (0.1 + rand() * 0.35), y: 1.55 + rand() * 0.25, z: (rand() - 0.5) * 0.3,
            vx: side * (0.02 + rand() * 0.06), vy: 0.22 + rand() * 0.08, life: LABEL_LIFE, age,
        });
    };
    slots.forEach((p, i) => release(p, LABEL_LIFE * (1 - (i + 1) / slots.length)));
    group.userData.update = (dt) => {
        slots.forEach((p) => {
            p.age += dt;
            if (p.age > p.life) release(p, 0);
            p.x += p.vx * dt;
            p.y += p.vy * dt;
            const k = p.age / p.life;
            const height = LABEL_HEIGHT * group.userData.scale * (0.9 + 0.2 * k);
            p.sprite.position.set(p.x, p.y, p.z);
            p.sprite.scale.set(height * p.label.aspect, height, 1);
            p.sprite.material.opacity = Math.sin(Math.PI * k) ** 0.8;
        });
    };
    return group;
}

async function start(mount) {
    const THREE = await import(mount.dataset.three);
    const list = document.getElementById("lp-flame-species");
    const names = list ? JSON.parse(list.textContent).map((species) => species.name) : [];
    await document.fonts.load('600 64px "Instrument Sans"').catch(() => {});
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.className = "lp-flame__canvas";
    renderer.domElement.setAttribute("aria-hidden", "true");

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 20);
    camera.position.set(0, 1.1, 5.4);
    camera.lookAt(0, 1.1, 0);

    const flame = new THREE.Group();
    const shells = SHELLS.map(([scale, heat, brightness, seed, spin]) => {
        const material = new THREE.ShaderMaterial({
            vertexShader: VERTEX,
            fragmentShader: FRAGMENT,
            uniforms: {
                uTime: { value: 0 }, uSeed: { value: seed }, uHeat: { value: heat },
                uBrightness: { value: brightness },
            },
            extensions: { derivatives: true },
            transparent: true, depthWrite: false, side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending,
        });
        const mesh = new THREE.Mesh(flameGeometry(THREE, seed), material);
        mesh.scale.setScalar(scale);
        mesh.position.y = (1 - scale) * 0.08;
        mesh.userData.spin = spin;
        flame.add(mesh);
        return mesh;
    });
    scene.add(flame);
    const species = speciesParticles(THREE, names);
    scene.add(species);

    const resize = () => {
        const { width, height } = mount.getBoundingClientRect();
        if (!width || !height) return;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        species.userData.scale = height < 400 ? 1.8 : 1;
    };
    new ResizeObserver(resize).observe(mount);
    resize();

    let time = 0;
    let last = 0;
    let running = false;
    let visible = true;
    const draw = (dt) => {
        time += dt;
        shells.forEach((mesh) => {
            mesh.material.uniforms.uTime.value = time;
            mesh.rotation.y = time * mesh.userData.spin;
        });
        flame.position.y = 0.02 * Math.sin(time * 1.3);
        species.userData.update(dt);
        renderer.render(scene, camera);
    };
    const frame = (now) => {
        if (!running) return;
        // At most 60 frames per second: a 120 Hz display gains nothing visible for twice the work
        if (now - last >= 1000 / 61) {
            draw(Math.min((now - last) / 1000, 0.05));
            last = now;
        }
        requestAnimationFrame(frame);
    };
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
        const on = visible && document.visibilityState === "visible" && !motion.matches;
        mount.classList.toggle("is-3d", !motion.matches);
        if (on && !running) {
            running = true;
            last = performance.now();
            requestAnimationFrame(frame);
        }
        running = on;
    };

    draw(0);
    mount.append(renderer.domElement);
    new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        update();
    }).observe(mount);
    document.addEventListener("visibilitychange", update);
    motion.addEventListener("change", update);
    renderer.domElement.addEventListener("webglcontextlost", () => {
        running = false;
        mount.classList.remove("is-3d");
    });
    update();
}

const mount = document.getElementById("lp-flame");
if (mount && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    start(mount).catch(() => mount.classList.remove("is-3d"));
}
