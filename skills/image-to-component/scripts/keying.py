"""Find and remove a raster's background.

Stdlib only; operates on straight-alpha RGBA byte buffers so the gated suite can test it with no
toolchain. `prep.py` decodes the image and hands the buffer here.

Background colour is a Chebyshev distance on RGB from the median border colour. A border that is
already mostly transparent has no background to key: its "median colour" is whatever RGB the
transparent pixels happen to carry, usually black, which would key a dark subject away.
"""
from __future__ import annotations

import statistics
from collections import deque

ALPHA_VISIBLE = 128


def _border(width: int, height: int):
    for x in range(width):
        yield x, 0
        if height > 1:
            yield x, height - 1
    for y in range(1, height - 1):
        yield 0, y
        if width > 1:
            yield width - 1, y


def border_background(buf: bytes, width: int, height: int) -> tuple[int, int, int] | None:
    """Median RGB of the opaque border, or None when most of the border is already transparent."""
    samples = [buf[(y * width + x) * 4:(y * width + x) * 4 + 4] for x, y in _border(width, height)]
    opaque = [s for s in samples if s[3] >= ALPHA_VISIBLE]
    if len(opaque) * 2 <= len(samples):
        return None
    return tuple(int(statistics.median(s[i] for s in opaque)) for i in range(3))


def _near(buf: bytes, offset: int, bg: tuple[int, int, int], tolerance: int) -> bool:
    return (abs(buf[offset] - bg[0]) <= tolerance and abs(buf[offset + 1] - bg[1]) <= tolerance
            and abs(buf[offset + 2] - bg[2]) <= tolerance)


def key_flood(buf: bytes, width: int, height: int, bg: tuple[int, int, int], tolerance: int) -> bytes:
    """A copy whose edge-connected pixels near `bg` are transparent; enclosed ones survive."""
    out = bytearray(buf)
    seen = bytearray(width * height)
    queue = deque()
    for x, y in _border(width, height):
        i = y * width + x
        if not seen[i] and _near(buf, i * 4, bg, tolerance):
            seen[i] = 1
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        out[(y * width + x) * 4 + 3] = 0
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            i = ny * width + nx
            if 0 <= nx < width and 0 <= ny < height and not seen[i]:
                seen[i] = 1
                if _near(buf, i * 4, bg, tolerance):
                    queue.append((nx, ny))
    return bytes(out)


def _distance(buf: bytes, offset: int, bg: tuple[int, int, int]) -> int:
    return max(abs(buf[offset] - bg[0]), abs(buf[offset + 1] - bg[1]), abs(buf[offset + 2] - bg[2]))


def soft_matte(original: bytes, keyed: bytes, width: int, height: int, bg: tuple[int, int, int],
               tolerance: int, radius: int = 3, key: str = "flood") -> bytes:
    """Replace the hard key's 0/255 step with alpha proportional to colour distance.

    A hard key puts the edge wherever the colour first leaves `tolerance`, so a blurred, JPEG-soft
    or anti-aliased edge comes out fat and stepped. Within `radius` px of the boundary, alpha is
    `(d - floor) / (local - floor)`: `d` the pixel's distance from `bg`, `floor` the keyed ground's
    median distance (its noise), `local` the largest subject distance within `radius`. The edge then
    sits where the colour is halfway between ground and subject. A ground-coloured pixel the key
    left opaque (an enclosed detail under flood keying) stays opaque.

    Under `key="global"` every ground-like pixel is background by definition, so there is no
    enclosed detail to protect and no band: alpha is coverage everywhere, `(d - floor) /
    (peak - floor)`, `peak` the 95th percentile subject distance. A single-colour glyph blurred
    below its stroke width keeps its holes this way — the band cannot reach a hole's centre.
    """
    size = width * height
    dist = [_distance(original, i * 4, bg) for i in range(size)]
    ground = [keyed[i * 4 + 3] == 0 for i in range(size)]
    ground_d = sorted(d for d, g in zip(dist, ground) if g)
    if not ground_d or len(ground_d) == size:
        return keyed
    floor = ground_d[len(ground_d) // 2]
    subject = [not g and d > tolerance for d, g in zip(dist, ground)]
    out = bytearray(keyed)
    if key == "global":
        subject_d = sorted(d for d, s in zip(dist, subject) if s)
        peak = subject_d[int(len(subject_d) * 0.95)] if subject_d else floor
        for i, d in enumerate(dist):
            share = (d - floor) / (peak - floor) if peak > floor else 0.0
            out[i * 4 + 3] = round(255 * min(1.0, max(0.0, share)))
        return bytes(out)

    def within(mask, x, y):
        return any(mask[ny * width + nx]
                   for ny in range(max(0, y - radius), min(height, y + radius + 1))
                   for nx in range(max(0, x - radius), min(width, x + radius + 1)))

    for y in range(height):
        for x in range(width):
            i = y * width + x
            if not (ground[i] or subject[i]):
                continue
            if not within(subject if ground[i] else ground, x, y):
                continue
            local = max(dist[ny * width + nx]
                        for ny in range(max(0, y - radius), min(height, y + radius + 1))
                        for nx in range(max(0, x - radius), min(width, x + radius + 1))
                        if subject[ny * width + nx])
            share = (dist[i] - floor) / (local - floor) if local > floor else 0.0
            out[i * 4 + 3] = round(255 * min(1.0, max(0.0, share)))
    return bytes(out)


def key_global(buf: bytes, width: int, height: int, bg: tuple[int, int, int], tolerance: int) -> bytes:
    """A copy whose every pixel near `bg` is transparent, connected or not."""
    out = bytearray(buf)
    for offset in range(0, width * height * 4, 4):
        if _near(buf, offset, bg, tolerance):
            out[offset + 3] = 0
    return bytes(out)
