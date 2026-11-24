"""Procedural spiral galaxy texture (no images used): galaxy(size, seed) -> float32 RGB array 0..1."""
import numpy as np
from PIL import Image, ImageFilter


def _noise(rng, n, blur):
    im = Image.fromarray((rng.random((n, n)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(np.float32) / 255
    return (a - a.min()) / (a.max() - a.min() + 1e-6)


def galaxy(n=1500, seed=75):
    rng = np.random.default_rng(seed)
    y, x = (np.mgrid[0:n, 0:n].astype(np.float32) - n / 2) / (n / 2)
    r = np.sqrt(x * x + y * y) + 1e-4
    th = np.arctan2(y, x)
    fine = _noise(rng, n, 2.5)
    dust = _noise(rng, n, 7) * 0.5 + _noise(rng, n, 20) * 0.3 + fine * 0.2
    clump = np.clip(dust * 1.6 - 0.35, 0, None) ** 1.5
    arms = np.zeros_like(r)
    for k, (m, wind, w, p) in enumerate([(2, 2.4, 1.0, 8), (2, 2.4, 0.5, 3), (4, 2.6, 0.22, 10)]):
        phase = m * (th - wind * np.log(r) + k * 0.45) + 0.6 * (_noise(rng, n, 30) - 0.5)
        arms += w * (0.5 + 0.5 * np.cos(phase)) ** p
    arms *= np.exp(-r / 0.42) * (0.25 + 1.3 * clump)
    lanes = 1 - 0.55 * np.clip(np.cos(2 * (th - 2.4 * np.log(r)) - 0.5), 0, 1) ** 12 * np.exp(-r / 0.5)
    halo = np.exp(-r / 0.7) * 0.22 * (0.5 + 0.5 * dust)
    core = np.exp(-(r / 0.06) ** 2) * 1.6 + np.exp(-r / 0.11) * 0.7
    # colours: gold core, violet and teal arms, rose outer haze
    gold = np.array([1.0, 0.78, 0.45]); violet = np.array([0.62, 0.42, 1.0])
    teal = np.array([0.30, 0.85, 0.75]); rose = np.array([1.0, 0.45, 0.70])
    mix = np.clip((r - 0.1) / 0.6, 0, 1)[..., None]
    arm_col = violet * (1 - mix) + teal * mix * (0.5 + 0.5 * dust[..., None]) + rose * mix * 0.3
    img = (core[..., None] * gold + arms[..., None] * arm_col * 1.5 + halo[..., None] * (rose * 0.5 + violet * 0.5)) * lanes[..., None]
    # stars: sparse points, a few with soft glow
    st = np.zeros((n, n), np.float32)
    k = int(n * n * 0.0016)
    sy, sx = rng.integers(0, n, k), rng.integers(0, n, k)
    st[sy, sx] = rng.random(k) ** 3 * 1.6
    glow = np.asarray(Image.fromarray((np.clip(st, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6))).astype(np.float32) / 255
    img += (st * 0.7 + glow * 2.5)[..., None] * np.array([0.9, 0.92, 1.0])
    img *= (1 - np.clip((r - 0.82) / 0.16, 0, 1) ** 2)[..., None]  # dark rim so the texture edge never shows
    img = 1 - np.exp(-img * 1.4)  # soft tone map, no hard clipping
    return np.clip(img, 0, 1).astype(np.float32)


if __name__ == "__main__":
    Image.fromarray((galaxy(900) * 255).astype(np.uint8)).save("galaxy-test.png")
