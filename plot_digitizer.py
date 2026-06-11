"""Extract (x, y) data series from images of simple plots.

The user supplies axis calibration (two clicked points per axis with their
real values) and one sampled color per data series. Pixels matching each
color are masked and collapsed into points:

- line mode: one point per pixel column (median row), then downsampled
- scatter mode: connected blobs -> centroids
"""
import numpy as np
from PIL import Image
from scipy import ndimage


def _color_mask(arr, color, tolerance):
    diff = arr.astype(np.float32) - np.asarray(color, dtype=np.float32)
    return np.sqrt((diff ** 2).sum(axis=2)) <= tolerance


def _axis_map(p1, p2, log=False):
    """Pixel -> data mapping from two calibration points.

    Log axes are linear in log10(value), so we interpolate there and
    exponentiate back.
    """
    if log:
        if p1["value"] <= 0 or p2["value"] <= 0:
            raise ValueError("Log-scale calibration values must be positive.")
        v1, v2 = np.log10(p1["value"]), np.log10(p2["value"])
    else:
        v1, v2 = p1["value"], p2["value"]
    scale = (v2 - v1) / (p2["pixel"] - p1["pixel"])

    def to_data(px):
        lin = v1 + (np.asarray(px, dtype=np.float64) - p1["pixel"]) * scale
        return 10 ** lin if log else lin

    return to_data


def _round_sig(values, sig=4):
    out = []
    for v in values:
        out.append(0.0 if v == 0 else round(v, -int(np.floor(np.log10(abs(v)))) + sig - 1))
    return out


def digitize(image, calibration, series_colors, mode="line",
             tolerance=40, max_points=60, x_log=False, y_log=False):
    """
    calibration: {"x1": {"pixel": px, "value": v}, "x2": ...,   (pixel = column)
                  "y1": {"pixel": py, "value": v}, "y2": ...}   (pixel = row)
    series_colors: list of [r, g, b]
    Returns [{"color", "points" (data coords), "pixels" (for overlay)}].
    """
    arr = np.asarray(image.convert("RGB"))
    h, w = arr.shape[:2]

    cal = calibration
    if cal["x1"]["pixel"] == cal["x2"]["pixel"] or cal["y1"]["pixel"] == cal["y2"]["pixel"]:
        raise ValueError("Calibration points on the same axis must not coincide.")
    to_x = _axis_map(cal["x1"], cal["x2"], log=x_log)
    to_y = _axis_map(cal["y1"], cal["y2"], log=y_log)

    # Search only inside the region spanned by the calibration points,
    # padded slightly so curves touching the axes aren't clipped.
    pad = 5
    c0 = max(0, min(cal["x1"]["pixel"], cal["x2"]["pixel"]) - pad)
    c1 = min(w, max(cal["x1"]["pixel"], cal["x2"]["pixel"]) + pad)
    r0 = max(0, min(cal["y1"]["pixel"], cal["y2"]["pixel"]) - pad)
    r1 = min(h, max(cal["y1"]["pixel"], cal["y2"]["pixel"]) + pad)

    results = []
    for color in series_colors:
        mask = np.zeros((h, w), dtype=bool)
        mask[r0:r1, c0:c1] = _color_mask(arr[r0:r1, c0:c1], color, tolerance)

        if mode == "scatter":
            labels, n = ndimage.label(mask)
            pixels = []
            for blob in range(1, n + 1):
                rows, cols = np.nonzero(labels == blob)
                if rows.size < 4:  # ignore speckle
                    continue
                pixels.append((cols.mean(), rows.mean()))
            pixels.sort()
        else:  # line: median row per column
            pixels = []
            for col in range(c0, c1):
                rows = np.nonzero(mask[:, col])[0]
                if rows.size:
                    pixels.append((col, float(np.median(rows))))
            if len(pixels) > max_points:
                idx = np.linspace(0, len(pixels) - 1, max_points).astype(int)
                pixels = [pixels[i] for i in idx]

        xs = _round_sig(to_x([p[0] for p in pixels]))
        ys = _round_sig(to_y([p[1] for p in pixels]))
        results.append({
            "color": list(color),
            "points": list(zip(xs, ys)),
            "pixels": [[round(c, 1), round(r, 1)] for c, r in pixels],
        })
    return results
