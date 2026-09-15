"""regions.vote: colour-region borders smoothed on the palette-index map, with no colour created and no
facet merged away."""
from __future__ import annotations

import unittest

from ._fixtures import SKILL_DIR  # noqa: F401  (puts the skill on sys.path)
from scripts import regions

TRANSPARENT = regions.TRANSPARENT


def box_blur(mask: bytes, width: int, height: int, radius: float) -> bytes:
    """A stdlib stand-in for the Gaussian prep passes in: a (2r+1)^2 box mean, edges clamped."""
    r = max(1, round(radius))
    out = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            total = count = 0
            for yy in range(max(0, y - r), min(height, y + r + 1)):
                for xx in range(max(0, x - r), min(width, x + r + 1)):
                    total += mask[yy * width + xx]
                    count += 1
            out[y * width + x] = total // count
    return bytes(out)


def grid(rows: list[str]) -> tuple[list[int], int, int]:
    """'.' transparent, digits are palette labels."""
    return [TRANSPARENT if ch == "." else int(ch) for row in rows for ch in row], len(rows[0]), len(rows)


def turns(labels: list[int], width: int, height: int, a: int, b: int) -> int:
    """How often the a|b border's column position changes from one row to the next."""
    edges = []
    for y in range(height):
        row = labels[y * width:(y + 1) * width]
        edges.append(next((x for x in range(1, width) if row[x - 1] == a and row[x] == b), None))
    return sum(1 for p, q in zip(edges, edges[1:]) if p is not None and q is not None and p != q)


class Vote(unittest.TestCase):
    def test_zero_radius_is_the_identity(self):
        labels, w, h = grid(["0011", "0.11", "2211"])
        self.assertEqual(regions.vote(labels, w, h, 0, box_blur), labels)

    def test_no_colour_is_created(self):
        labels, w, h = grid(["001122", "010122", "001212", "331122"])
        out = regions.vote(labels, w, h, 1, box_blur)
        self.assertLessEqual(set(out) - {TRANSPARENT}, set(labels) - {TRANSPARENT})

    def test_silhouette_is_untouched(self):
        labels, w, h = grid(["..0011..", ".001011.", "00101011", ".001011.", "..0011.."])
        out = regions.vote(labels, w, h, 1, box_blur)
        self.assertEqual([v == TRANSPARENT for v in out], [v == TRANSPARENT for v in labels])

    def test_a_ragged_border_straightens(self):
        # Noise knocked single pixels across a straight border. (A strict 1 px alternation has its true
        # border between pixel centres, so no per-pixel labelling can straighten it; that is not tested.)
        rows = ["0000111111", "0001111111", "0000111111", "0000011111", "0000111111", "0001111111", "0000111111"]
        labels, w, h = grid(rows)
        out = regions.vote(labels, w, h, 1, box_blur)
        self.assertLess(turns(out, w, h, 0, 1), turns(labels, w, h, 0, 1))

    def test_a_tie_goes_to_the_more_frequent_label_not_the_lower_index(self):
        def flat(mask, width, height, radius):  # every label supports every pixel equally
            return bytes([100] * (width * height)) if any(mask) else bytes(width * height)
        labels, w, h = grid(["0111", "1111"])
        self.assertEqual(regions.vote(labels, w, h, 1, flat), [1] * 8)

    def test_a_facet_larger_than_the_radius_survives(self):
        rows = ["1111111111"] * 3 + ["1112222111"] * 4 + ["1111111111"] * 3
        labels, w, h = grid(rows)
        out = regions.vote(labels, w, h, 1, box_blur)
        self.assertGreaterEqual(out.count(2), labels.count(2) // 2)


if __name__ == "__main__":
    unittest.main()
