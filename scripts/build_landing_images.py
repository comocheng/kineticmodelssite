"""Write the images of the home page to database/static/database/images/landing/.

flame.svg is the hero flame: a fixed outline filled with Delaunay triangles. Each facet takes its
colour from its height and its distance from the axis, so the core is hot yellow and the edges are
deep orange. The seed is fixed, so a second run writes the same file.

The flame animates itself with CSS inside the SVG, so it moves when the page loads it as an <img>:
the body sways from its base, core facets brighten and edge facets darken on three unrelated
periods, and embers rise from the tips. flame-static.svg is the same flame without the motion, for
visitors who ask for reduced motion.

prometheus-logo-transparent.png (navbar) and prometheus-gift.png (the "Why the name" card) are the
site logo, a hand that holds fire, with its white background removed so that it sits on dark sections.

    python scripts/build_landing_images.py
"""
from pathlib import Path

import numpy as np
from matplotlib.path import Path as Outline
from PIL import Image
from scipy import ndimage
from scipy.spatial import Delaunay

IMAGES = Path(__file__).resolve().parent.parent / "database/static/database/images"
OUT = IMAGES / "landing/flame.svg"
OUT_STATIC = IMAGES / "landing/flame-static.svg"
LOGO_SIZES = {"prometheus-logo-transparent.png": 240, "prometheus-gift.png": 720}
SEED = 7
WIDTH, HEIGHT = 420, 600
HEADROOM = 90  # room above the tips for the embers to rise into
# Three periods (s) with no common beat, so the shimmer never moves in step
SHIMMER_PERIODS = (1.9, 2.6, 3.3)
EMBERS = 9

# Outline in flame units: x across (-1 to 1), y up from the base (0 to 1.5). Three tongues.
OUTLINE = [
    (0.00, 0.00), (0.28, 0.03), (0.52, 0.13), (0.70, 0.30), (0.78, 0.50), (0.74, 0.70),
    (0.80, 0.86), (0.86, 1.10), (0.66, 0.98), (0.50, 0.92), (0.40, 1.12), (0.12, 1.50),
    (0.04, 1.22), (-0.14, 1.06), (-0.28, 0.98), (-0.48, 1.24), (-0.54, 0.96), (-0.70, 0.80),
    (-0.78, 0.60), (-0.76, 0.40), (-0.66, 0.24), (-0.50, 0.11), (-0.27, 0.03),
]
# Heat 1 is the core, heat 0 the outer edge. The orange at 0.3 is the Figma accent #CE4801.
STOPS = [(0.0, "#6c2700"), (0.3, "#ce4801"), (0.55, "#f26a12"), (0.78, "#ff9a2e"), (1.0, "#ffd27a")]


def mix(heat):
    heat = min(max(heat, 0.0), 1.0)
    for (h0, c0), (h1, c1) in zip(STOPS, STOPS[1:]):
        if heat <= h1:
            t = (heat - h0) / (h1 - h0)
            a = [int(c0[i:i + 2], 16) for i in (1, 3, 5)]
            b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
            return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))
    return STOPS[-1][1]


ANIMATION_CSS = """
.body { transform-box: fill-box; transform-origin: 50% 100%; animation: sway 3.6s ease-in-out infinite; }
.glint { fill: #ffe7b0; opacity: 0; animation: glint 2.6s ease-in-out infinite; }
.shade { fill: #3a1400; opacity: 0; animation: shade 2.6s ease-in-out infinite; }
.ember { opacity: 0; transform-box: fill-box; transform-origin: center; animation: rise 3s ease-out infinite; }
@keyframes sway {
  0%, 100% { transform: scale(1, 1) skewX(0deg); }
  20% { transform: scale(1.01, 1.03) skewX(-1.5deg); }
  45% { transform: scale(0.995, 0.985) skewX(1deg); }
  70% { transform: scale(1.005, 1.025) skewX(-0.6deg); }
}
@keyframes glint { 0%, 100% { opacity: 0; } 50% { opacity: 0.6; } }
@keyframes shade { 0%, 100% { opacity: 0; } 50% { opacity: 0.35; } }
@keyframes rise {
  0% { opacity: 0; transform: translate(0, 0) rotate(0deg); }
  15% { opacity: 1; }
  100% { opacity: 0; transform: translate(var(--dx), var(--dy)) rotate(220deg); }
}
@media (prefers-reduced-motion: reduce) { .body, .glint, .shade, .ember { animation: none; } }
"""


def build_flame():
    rng = np.random.default_rng(SEED)
    outline = np.array(OUTLINE)
    shape = Outline(np.vstack([outline, outline[:1]]))
    inside = rng.uniform([-0.9, 0.0], [0.9, 1.5], size=(900, 2))
    inside = inside[shape.contains_points(inside, radius=-0.04)][:90]
    points = np.vstack([outline, inside])
    triangles = Delaunay(points).simplices
    centroids = points[triangles].mean(axis=1)
    triangles = triangles[shape.contains_points(centroids)]

    def to_svg(p):
        return (WIDTH / 2 + p[0] * WIDTH * 0.55, HEIGHT - 10 - p[1] * (HEIGHT - 20) / 1.5)

    # A second generator for the motion, so the geometry above stays the same as before
    motion = np.random.default_rng(SEED + 1)

    def timing(period):
        return f"animation-duration:{period:.2f}s;animation-delay:{-motion.uniform(0, period):.2f}s"

    facets, overlays = [], []
    for tri in triangles:
        cx, cy = points[tri].mean(axis=0)
        heat = 1.05 - 0.55 * (cy / 1.5) - 0.75 * abs(cx) / 0.80 + rng.normal(0, 0.06)
        corners = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(to_svg, points[tri]))
        facets.append(f'<polygon points="{corners}" fill="{mix(heat)}" stroke="{mix(heat)}" stroke-width="0.6"/>')
        kind = "glint" if heat > 0.55 else "shade" if heat < 0.3 else None
        if kind:
            period = SHIMMER_PERIODS[motion.integers(len(SHIMMER_PERIODS))]
            overlays.append(f'<polygon class="{kind}" points="{corners}" style="{timing(period)}"/>')

    embers = []
    for _ in range(EMBERS):
        x, y = to_svg((motion.uniform(-0.5, 0.8), motion.uniform(1.0, 1.35)))
        size = motion.uniform(3.5, 7)
        corners = f"{x:.1f},{y - size:.1f} {x + 0.87 * size:.1f},{y + 0.5 * size:.1f} {x - 0.87 * size:.1f},{y + 0.5 * size:.1f}"
        drift = f"--dx:{motion.uniform(-30, 30):.0f}px;--dy:{-motion.uniform(150, 210):.0f}px;"
        fill = mix(motion.uniform(0.75, 1.0))
        embers.append(f'<polygon class="ember" points="{corners}" fill="{fill}" '
                      f'style="{drift}{timing(motion.uniform(2.4, 4.2))}"/>')

    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {-HEADROOM} {WIDTH} {HEIGHT + HEADROOM}" '
            f'role="img" aria-label="Low-poly flame">\n')
    body = "\n".join(facets)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(head + f"<style>{ANIMATION_CSS}</style>\n<g class=\"body\">\n{body}\n"
                   + "\n".join(overlays) + "\n</g>\n<g>\n" + "\n".join(embers) + "\n</g>\n</svg>\n")
    OUT_STATIC.write_text(head + f"<g>\n{body}\n</g>\n</svg>\n")
    print(f"{OUT}: {len(facets)} facets, {len(overlays)} shimmer facets, {len(embers)} embers")
    print(f"{OUT_STATIC}: {len(facets)} facets")


def build_logos():
    # Only near-white pixels that touch the border are background; the light hand stays opaque.
    rgb = np.asarray(Image.open(IMAGES / "prometheus-logo.png").convert("RGB"))
    labels, _ = ndimage.label(rgb.min(axis=2) >= 238)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    alpha = np.where(np.isin(labels, list(border)), 0, 255).astype(float)
    alpha = ndimage.uniform_filter(alpha, 3).astype(np.uint8)
    logo = Image.fromarray(np.dstack([rgb, alpha]))
    logo = logo.crop(logo.getbbox())
    for name, size in LOGO_SIZES.items():
        out = logo.copy()
        out.thumbnail((size, size), Image.LANCZOS)
        out.save(IMAGES / "landing" / name, optimize=True)
        print(f"{IMAGES / 'landing' / name}: {out.size[0]}x{out.size[1]}")


if __name__ == "__main__":
    build_flame()
    build_logos()
