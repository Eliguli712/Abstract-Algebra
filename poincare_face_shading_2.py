"""Paired Poincare-disk / upper-half-plane visualization.

The two panels share
  1. exactly the same locally adapted geodesic-edge colors: orthogonal-circle
     radius R supplies the base hue, then the two neighbouring cells supply the
     local hue and contrast correction,
  2. exactly the same *cell* lightfield: every closed region cut out by the
     geodesics is filled from a base color determined by
        (a) its recursion depth  d = how many drawn geodesics separate it
            from the center of the disk, and
        (b) its capped, normalized hyperbolic radial position t = rho/rho_cap,
        (c) its polar angle theta and a tiny deterministic cell phase, so cells
            in one recursion layer do not receive identical colours;
     the base is then blended with the mean color of the cell's incident
     geodesics and shaded from a deeper edge to a soft luminous core, before
     being pulled through one Cayley--Mobius map.

The default palette is an adaptive HSV rainbow.  Named bounded palettes remain
available, and the model boundary automatically follows the active palette.

Running this file writes ``poincare_inversion_correspondence.png`` next to it.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Tuple

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, Normalize

try:  # optional, only used for fast connected components
    from scipy import ndimage as _ndi

    _HAVE_SCIPY = True
except Exception:  # pragma: no cover
    _ndi = None
    _HAVE_SCIPY = False


class HyperbolicTilingArcVisualizer:
    """Generate ideal extensions of selected {p,q} Poincare tiling edges."""

    @staticmethod
    def geodesic_ab_from_uv(u, v, eps=1e-12):
        u = np.asarray(u, dtype=float)
        v = np.asarray(v, dtype=float)
        u1, u2 = u
        v1, v2 = v
        det = u1 * v2 - u2 * v1

        if abs(det) < eps:
            w = u if np.linalg.norm(u) > np.linalg.norm(v) else v
            nw = np.linalg.norm(w)
            d = np.array([1.0, 0.0]) if nw < eps else w / nw
            return "diameter", {"dir": d}

        nu2 = u1 * u1 + u2 * u2
        nv2 = v1 * v1 + v2 * v2
        a = (u2 * (nv2 + 1.0) - v2 * (nu2 + 1.0)) / det
        b = (v1 * (nu2 + 1.0) - u1 * (nv2 + 1.0)) / det
        center = np.array([-a / 2.0, -b / 2.0], dtype=float)
        radius2 = (a * a + b * b) / 4.0 - 1.0
        return "circle", {
            "a": a,
            "b": b,
            "center": center,
            "radius": np.sqrt(max(radius2, 0.0)),
        }

    @classmethod
    def sample_geodesic_arc(cls, u, v, n=600):
        kind, data = cls.geodesic_ab_from_uv(u, v)
        u = np.asarray(u, dtype=float)
        v = np.asarray(v, dtype=float)
        if kind == "diameter":
            t = np.linspace(0.0, 1.0, n)[:, None]
            return (1.0 - t) * u + t * v

        c = data["center"]
        radius = data["radius"]
        a1 = np.arctan2(u[1] - c[1], u[0] - c[0])
        a2 = np.arctan2(v[1] - c[1], v[0] - c[0])
        da = (a2 - a1) % (2.0 * np.pi)
        if da > np.pi:
            da -= 2.0 * np.pi
        theta = a1 + np.linspace(0.0, da, n)
        pts = np.column_stack(
            [c[0] + radius * np.cos(theta), c[1] + radius * np.sin(theta)]
        )
        return pts[np.hypot(pts[:, 0], pts[:, 1]) <= 1.0 + 1e-10]

    @staticmethod
    def geodesic_circle_reflect(z1, z2, eps=1e-12):
        det = z1.real * z2.imag - z1.imag * z2.real
        if abs(det) < eps:
            v = z1 if abs(z1) > abs(z2) else z2
            return True, None, None, np.arctan2(v.imag, v.real)

        matrix = np.array([[z1.real, z1.imag], [z2.real, z2.imag]], dtype=float)
        rhs = np.array([(abs(z1) ** 2 + 1.0) / 2.0, (abs(z2) ** 2 + 1.0) / 2.0])
        cx, cy = np.linalg.solve(matrix, rhs)
        center = cx + 1j * cy
        radius = np.sqrt(max(abs(center) ** 2 - 1.0, 0.0))
        return False, center, radius, None

    @classmethod
    def reflect_in_geodesic(cls, z, z1, z2):
        is_diameter, center, radius, theta = cls.geodesic_circle_reflect(z1, z2)
        if is_diameter:
            return np.exp(2j * theta) * np.conj(z)
        return center + radius * radius / np.conj(z - center)

    @staticmethod
    def hyperbolic_circumradius(p, q):
        return np.arccosh(np.cos(np.pi / p) / np.sin(np.pi / q))

    @staticmethod
    def poincare_radius_from_hyperbolic(radius):
        return np.tanh(radius / 2.0)

    @classmethod
    def seed_regular_polygon(cls, p=4, q=5, rot=0.0):
        radius = cls.hyperbolic_circumradius(p, q)
        rho = cls.poincare_radius_from_hyperbolic(radius)
        angles = rot + 2.0 * np.pi * np.arange(p) / p
        return rho * np.cos(angles) + 1j * rho * np.sin(angles)

    @staticmethod
    def project_to_unit_circle(z, eps=1e-12):
        radius = abs(z)
        return 1.0 + 0.0j if radius < eps else z / radius

    @staticmethod
    def polygon_key(vertices, decimals=6):
        rounded = np.round(vertices.real, decimals) + 1j * np.round(
            vertices.imag, decimals
        )
        return tuple(np.sort(rounded).tolist())

    @staticmethod
    def wrap_pi(angle):
        return (angle + np.pi) % (2.0 * np.pi) - np.pi

    @classmethod
    def axis_aligned(cls, theta, tol=np.deg2rad(6.0), mode="+"):
        if mode == "+":
            axes = np.array([0.0, np.pi / 2.0, np.pi, 3.0 * np.pi / 2.0])
        else:
            axes = np.array(
                [np.pi / 4.0, 3.0 * np.pi / 4.0, 5.0 * np.pi / 4.0, 7.0 * np.pi / 4.0]
            )
        return np.min(np.abs(cls.wrap_pi(theta - axes))) <= tol

    def __init__(
        self,
        p=4,
        q=5,
        max_polys=1200,
        cutoff=0.97,
        inner_keep=0.26,
        outer_keep=0.80,
        outer_max=0.965,
        decimals=8,
        use_ideal_endpoints=True,
        r_focus=0.22,
        axis_tol_deg=6.0,
        focus_mode="+",
        samples=700,
    ):
        self.p = p
        self.q = q
        self.max_polys = max_polys
        self.cutoff = cutoff
        self.inner_keep = inner_keep
        self.outer_keep = outer_keep
        self.outer_max = outer_max
        self.decimals = decimals
        self.use_ideal_endpoints = use_ideal_endpoints
        self.r_focus = r_focus
        self.axis_tol_deg = axis_tol_deg
        self.focus_mode = focus_mode
        self.samples = samples
        self.polys = None
        self.edges = None
        self.cache = None
        self.r_percentiles = None

    def build(self):
        seed = self.seed_regular_polygon(
            self.p, self.q, rot=np.pi / 4.0 if self.p == 4 else 0.0
        )
        polygons = []
        seen = {self.polygon_key(seed)}
        queue = deque([seed])

        while queue and len(polygons) < self.max_polys:
            polygon = queue.popleft()
            polygons.append(polygon)
            if abs(np.mean(polygon)) > self.cutoff:
                continue
            for i in range(len(polygon)):
                z1 = polygon[i]
                z2 = polygon[(i + 1) % len(polygon)]
                reflected = np.array(
                    [self.reflect_in_geodesic(z, z1, z2) for z in polygon],
                    dtype=complex,
                )
                if np.any(np.abs(reflected) >= 0.999999):
                    continue
                key = self.polygon_key(reflected, self.decimals)
                if key not in seen:
                    seen.add(key)
                    queue.append(reflected)

        edges = []
        seen_edges = set()
        for polygon in polygons:
            center_radius = abs(np.mean(polygon))
            keep_band = center_radius <= self.inner_keep or (
                self.outer_keep <= center_radius <= self.outer_max
            )
            if not keep_band:
                continue
            for i in range(len(polygon)):
                z1 = polygon[i]
                z2 = polygon[(i + 1) % len(polygon)]
                forward = (z1.real, z1.imag, z2.real, z2.imag)
                backward = (z2.real, z2.imag, z1.real, z1.imag)
                a, b = (z1, z2) if forward < backward else (z2, z1)
                key = (
                    round(a.real, self.decimals),
                    round(a.imag, self.decimals),
                    round(b.real, self.decimals),
                    round(b.imag, self.decimals),
                )
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                edges.append((z1, z2))

        cache = []
        radii = []
        for edge_id, (z1, z2) in enumerate(edges):
            r_out = 0.5 * (abs(z1) + abs(z2))
            z1p = self.project_to_unit_circle(z1) if self.use_ideal_endpoints else z1
            z2p = self.project_to_unit_circle(z2) if self.use_ideal_endpoints else z2
            u = np.array([z1p.real, z1p.imag])
            v = np.array([z2p.real, z2p.imag])
            kind, data = self.geodesic_ab_from_uv(u, v)
            if kind == "diameter":
                radius = 1e6
                center = None
                direction = np.asarray(data["dir"], dtype=float)
            else:
                radius = float(data["radius"])
                center = np.asarray(data["center"], dtype=float)
                direction = None
            # NEW: the analytic support of every drawn geodesic travels with the
            # sampled arc, so cell membership can be decided exactly later on.
            cache.append(
                {
                    "id": edge_id,
                    "z1p": z1p,
                    "z2p": z2p,
                    "kind": kind,
                    "center": center,
                    "dir": direction,
                    "R": radius,
                    "r_out": r_out,
                }
            )
            radii.append(radius)

        self.polys = polygons
        self.edges = edges
        self.cache = cache
        self.r_percentiles = tuple(
            float(x) for x in np.percentile(np.asarray(radii), [5.0, 95.0])
        )
        return self

    def prepared_arcs(self):
        """Return the once-filtered arc set used by both model panels."""
        if self.cache is None:
            self.build()
        arcs = []
        dropped_center = 0
        tol = np.deg2rad(self.axis_tol_deg)
        for item in self.cache:
            z1p, z2p = item["z1p"], item["z2p"]
            u = np.array([z1p.real, z1p.imag])
            v = np.array([z2p.real, z2p.imag])
            points = self.sample_geodesic_arc(u, v, n=self.samples)
            if len(points) < 10:
                continue
            point_radii = np.hypot(points[:, 0], points[:, 1])
            if float(point_radii.min()) < self.r_focus:
                k = int(np.argmin(point_radii))
                theta = float(np.arctan2(points[k, 1], points[k, 0]))
                if not self.axis_aligned(theta, tol=tol, mode=self.focus_mode):
                    dropped_center += 1
                    continue
            arcs.append(
                {
                    "id": item["id"],
                    "disk": points,
                    "R": item["R"],
                    "r_out": item["r_out"],
                    "kind": item["kind"],
                    "center": item["center"],
                    "dir": item["dir"],
                }
            )
        return arcs, dropped_center


# --------------------------------------------------------------------------
# Cayley correspondence
# --------------------------------------------------------------------------


def align_diameter_to_real_axis(direction=1j):
    direction = direction / abs(direction)
    return np.conj(direction)


def disk_complex_to_half(z, direction=1j):
    """Cayley map after rotating ``direction`` onto the real diameter."""
    rot = align_diameter_to_real_axis(direction)
    z_aligned = rot * np.asarray(z, dtype=complex)
    return 1j * (1.0 + z_aligned) / (1.0 - z_aligned)


def half_complex_to_disk(w, direction=1j):
    """Exact inverse of :func:`disk_complex_to_half`."""
    rot = align_diameter_to_real_axis(direction)
    z_aligned = (np.asarray(w, dtype=complex) - 1j) / (
        np.asarray(w, dtype=complex) + 1j
    )
    return z_aligned / rot


def split_mapped_polyline(
    points_xy,
    direction=1j,
    xlim=(-8.0, 8.0),
    ylim=(0.0, 10.0),
    pad=1.16,
    target_step=0.02,
    max_samples=24000,
):
    """Map an arc and split it at the Cayley pole / plotting-window jumps.

    The Cayley map stretches enormously near its pole, so the disk polyline is
    first re-densified until consecutive *image* points stay closer than
    ``target_step``; otherwise long arcs arrive in H as dotted fragments.
    """
    z = points_xy[:, 0] + 1j * points_xy[:, 1]
    probe = disk_complex_to_half(z, direction=direction)
    finite = np.isfinite(probe.real) & np.isfinite(probe.imag)
    inside = finite.copy()
    inside[finite] &= (
        (np.abs(probe.real[finite]) <= pad * max(abs(xlim[0]), abs(xlim[1])))
        & (probe.imag[finite] >= 0.0)
        & (probe.imag[finite] <= pad * ylim[1])
    )
    if np.count_nonzero(inside) >= 2:
        visible = probe[inside]
        span = float(np.sum(np.abs(np.diff(visible))))
        needed = int(np.clip(span / target_step, len(z), max_samples))
        if needed > len(z):
            points_xy = _densify_polyline(points_xy, count=needed)
            z = points_xy[:, 0] + 1j * points_xy[:, 1]
    rot = align_diameter_to_real_axis(direction)
    z_aligned = rot * z
    denominator = 1.0 - z_aligned
    valid = np.abs(denominator) > 1e-9
    w = np.full(z.shape, np.nan + 1j * np.nan, dtype=complex)
    w[valid] = 1j * (1.0 + z_aligned[valid]) / denominator[valid]
    valid &= np.isfinite(w.real) & np.isfinite(w.imag) & (w.imag > 1e-10)
    valid &= (w.real >= pad * xlim[0]) & (w.real <= pad * xlim[1])
    valid &= (w.imag >= ylim[0]) & (w.imag <= pad * ylim[1])

    transitions = np.flatnonzero(np.diff(np.r_[False, valid, False].astype(int)))
    segments = []
    for start, stop in transitions.reshape(-1, 2):
        if stop - start >= 2:
            segments.append(np.column_stack([w.real[start:stop], w.imag[start:stop]]))
    return segments


def cayley_real_endpoint(z_ideal, direction=1j, tol=1e-9):
    """Image of an ideal endpoint under A: a point of the real axis, or None."""
    rot = align_diameter_to_real_axis(direction)
    z_aligned = rot * complex(z_ideal)
    denominator = 1.0 - z_aligned
    if abs(denominator) < tol:
        return None  # the Cayley pole: this endpoint goes to infinity
    return float((1j * (1.0 + z_aligned) / denominator).real)


def _visible_theta_intervals(center, radius, xlim, ylim, pad):
    """Angular pieces of the semicircle that fall inside the plotting window."""
    lo = max((pad * xlim[0] - center) / radius, -1.0)
    hi = min((pad * xlim[1] - center) / radius, 1.0)
    if lo >= hi:
        return []
    theta_a, theta_b = np.arccos(hi), np.arccos(lo)
    ceiling = pad * ylim[1]
    if radius > ceiling:
        cut = float(np.arcsin(np.clip(ceiling / radius, 0.0, 1.0)))
        allowed = [(0.0, cut), (np.pi - cut, np.pi)]
    else:
        allowed = [(0.0, np.pi)]
    pieces = []
    for a0, a1 in allowed:
        b0, b1 = max(a0, theta_a), min(a1, theta_b)
        if b1 - b0 > 1e-12:
            pieces.append((b0, b1))
    return pieces


def half_plane_geodesic_segments(
    z1_ideal,
    z2_ideal,
    direction=1j,
    xlim=(-8.0, 8.0),
    ylim=(0.0, 10.0),
    pad=1.16,
    step=0.006,
):
    """Exact image of one complete geodesic in H.

    A Mobius map sends circles to circles, so the image of a geodesic with ideal
    endpoints ``z1``, ``z2`` is the semicircle in H standing on A(z1), A(z2)
    (or a vertical line when one endpoint hits the Cayley pole). Building the
    arc directly in H removes the sampling artefacts that appear when a disk
    polyline is pushed through the pole.
    """
    x1 = cayley_real_endpoint(z1_ideal, direction)
    x2 = cayley_real_endpoint(z2_ideal, direction)
    if x1 is None and x2 is None:
        return []

    if x1 is None or x2 is None:  # vertical line Re w = const
        x0 = x2 if x1 is None else x1
        if not (pad * xlim[0] <= x0 <= pad * xlim[1]):
            return []
        y = np.linspace(1e-6, pad * ylim[1], 800)
        return [np.column_stack([np.full_like(y, x0), y])]

    center = 0.5 * (x1 + x2)
    radius = 0.5 * abs(x1 - x2)
    if radius < 1e-12:
        return []

    segments = []
    for b0, b1 in _visible_theta_intervals(center, radius, xlim, ylim, pad):
        count = int(np.clip(radius * (b1 - b0) / step, 300, 9000))
        theta = np.linspace(b0, b1, count)
        segments.append(
            np.column_stack([center + radius * np.cos(theta), radius * np.sin(theta)])
        )
    return segments


# --------------------------------------------------------------------------
# NEW: the arrangement of cells cut out by the drawn geodesics
# --------------------------------------------------------------------------


def _densify_polyline(points, step=None, count=None):
    """Resample a polyline to ``count`` points, or to a spacing below ``step``."""
    seg = np.hypot(np.diff(points[:, 0]), np.diff(points[:, 1]))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    if total <= 0.0:
        return points
    m = int(count) if count is not None else max(int(total / step) + 2, 2)
    m = max(m, 2)
    t = np.linspace(0.0, total, m)
    return np.column_stack([np.interp(t, s, points[:, 0]), np.interp(t, s, points[:, 1])])


def _label_free_space(free):
    """4-connected labelling of the free (non-wall) pixels."""
    if _HAVE_SCIPY:
        structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
        labels, count = _ndi.label(free, structure=structure)
        return labels.astype(np.int32), int(count)

    # Dependency-free fallback: iterated max-propagation of unique seeds.
    labels = np.zeros(free.shape, dtype=np.int64)
    labels[free] = np.arange(1, int(free.sum()) + 1)
    for _ in range(4 * max(free.shape)):
        previous = labels
        current = labels.copy()
        current[:-1] = np.maximum(current[:-1], labels[1:])
        current[1:] = np.maximum(current[1:], labels[:-1])
        current[:, :-1] = np.maximum(current[:, :-1], labels[:, 1:])
        current[:, 1:] = np.maximum(current[:, 1:], labels[:, :-1])
        current[~free] = 0
        if np.array_equal(current, previous):
            break
        labels = current
    unique, labels = np.unique(labels, return_inverse=True)
    labels = labels.reshape(free.shape).astype(np.int32)
    return labels, int(unique.size - 1)


def build_cell_arrangement(arcs, n=1500, wall_step_px=0.34, boundary_pad=0.998):
    """Rasterize every drawn geodesic and label the closed regions between them.

    Returns
    -------
    labels : (n, n) int32 image, 0 = wall / outside the disk
    axis   : the shared x = y sample coordinates of the raster
    """
    axis = np.linspace(-1.0, 1.0, n)
    h = axis[1] - axis[0]
    xx, yy = np.meshgrid(axis, axis)
    inside = (xx * xx + yy * yy) < boundary_pad**2

    wall = np.zeros((n, n), dtype=bool)
    for arc in arcs:
        pts = _densify_polyline(arc["disk"], step=wall_step_px * h)
        ix = np.rint((pts[:, 0] + 1.0) / h).astype(np.int64)
        iy = np.rint((pts[:, 1] + 1.0) / h).astype(np.int64)
        ok = (ix >= 0) & (ix < n) & (iy >= 0) & (iy < n)
        wall[iy[ok], ix[ok]] = True

    free = inside & ~wall
    labels, count = _label_free_space(free)
    return labels, axis, count


def close_wall_pixels(labels, axis, boundary_pad=0.998):
    """Give every wall pixel the label of its nearest cell.

    The rasterized geodesics are one pixel wide in D, but the Cayley map blows
    that pixel up enormously in H, where it would otherwise show as a ragged
    transparent seam along each cell border. Absorbing the walls into the
    neighbouring cell removes the seam; the drawn arcs still separate the cells.
    """
    if not _HAVE_SCIPY:
        return labels
    xx, yy = np.meshgrid(axis, axis)
    inside = (xx * xx + yy * yy) < boundary_pad**2
    indices = _ndi.distance_transform_edt(
        labels == 0, return_distances=False, return_indices=True
    )
    filled = labels[tuple(indices)]
    filled[~inside] = 0
    return filled.astype(np.int32)


def cell_statistics(labels, axis, count):
    """Area, centroid and a guaranteed-interior representative point per cell."""
    n = labels.shape[0]
    xx, yy = np.meshgrid(axis, axis)
    flat = labels.ravel()
    area = np.bincount(flat, minlength=count + 1).astype(float)
    sum_x = np.bincount(flat, weights=xx.ravel(), minlength=count + 1)
    sum_y = np.bincount(flat, weights=yy.ravel(), minlength=count + 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cx = sum_x / area
        cy = sum_y / area

    # Cells reaching the outer rim are not genuinely closed in the picture.
    rim = (xx * xx + yy * yy) > 0.985**2
    touches_rim = np.bincount(flat[rim.ravel()], minlength=count + 1) > 0

    h = axis[1] - axis[0]
    ix = np.clip(np.rint((cx + 1.0) / h), 0, n - 1)
    iy = np.clip(np.rint((cy + 1.0) / h), 0, n - 1)
    ix = np.nan_to_num(ix, nan=0.0).astype(np.int64)
    iy = np.nan_to_num(iy, nan=0.0).astype(np.int64)
    rep_x, rep_y = cx.copy(), cy.copy()

    # For non-convex cells the centroid can fall on a wall; snap it back.
    bad = labels[iy, ix] != np.arange(count + 1)
    bad[0] = False
    if np.any(bad):
        order = np.argsort(flat, kind="stable")
        starts = np.cumsum(area.astype(np.int64)) - area.astype(np.int64)
        for lab in np.flatnonzero(bad):
            size = int(area[lab])
            if size == 0:
                continue
            group = order[starts[lab] : starts[lab] + size]
            gx = xx.ravel()[group]
            gy = yy.ravel()[group]
            k = int(np.argmin((gx - cx[lab]) ** 2 + (gy - cy[lab]) ** 2))
            rep_x[lab], rep_y[lab] = gx[k], gy[k]

    return {
        "area_px": area,
        "centroid": np.stack([cx, cy], axis=1),
        "rep": np.stack([rep_x, rep_y], axis=1),
        "touches_rim": touches_rim,
    }


def cell_recursion_depth(rep_points, arcs, base=1.7e-5 + 1.1e-5j, chunk=256):
    """Depth = how many drawn geodesics separate a point from the disk center.

    This is a separation count over the prepared drawing records, relative to
    a base point near the origin.  It is the depth used by the colour field;
    BFS generation depth and minimal group word length are separate quantities.
    """
    circles = np.array(
        [[a["center"][0], a["center"][1], a["R"]] for a in arcs if a["kind"] == "circle"],
        dtype=float,
    ).reshape(-1, 3)
    lines = np.array(
        [[-a["dir"][1], a["dir"][0]] for a in arcs if a["kind"] == "diameter"],
        dtype=float,
    ).reshape(-1, 2)

    base_line_side = np.sign(lines @ np.array([base.real, base.imag])) if len(lines) else None
    depth = np.zeros(len(rep_points), dtype=np.int32)
    for start in range(0, len(rep_points), chunk):
        block = rep_points[start : start + chunk]
        count = np.zeros(len(block), dtype=np.int32)
        if len(circles):
            dx = block[:, 0][:, None] - circles[None, :, 0]
            dy = block[:, 1][:, None] - circles[None, :, 1]
            count += np.sum(np.hypot(dx, dy) < circles[None, :, 2], axis=1)
        if len(lines):
            side = np.sign(block @ lines.T)
            count += np.sum(side != base_line_side[None, :], axis=1)
        depth[start : start + chunk] = count
    return depth


# --------------------------------------------------------------------------
# Color encodings
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EdgePalette:
    """HSV ramp used for the geodesic strokes, keyed by orthogonal radius R."""

    name: str = "orthogonal_radius"
    hue: Tuple[float, float] = (0.78, 0.60)  # (small R, large R)
    gamma: float = 1.6
    saturation: float = 0.70
    value: float = 0.85
    n_levels: int = 512

    def colormap(self) -> ListedColormap:
        t = np.linspace(0.0, 1.0, self.n_levels)
        h0, h1 = self.hue
        hue = h1 + (h0 - h1) * (1.0 - t) ** self.gamma
        sat = np.full_like(hue, self.saturation)
        val = np.full_like(hue, self.value)
        rgb = mcolors.hsv_to_rgb(np.stack([hue, sat, val], axis=-1))
        return ListedColormap(rgb, name=self.name)


@dataclass(frozen=True)
class CellPalette:
    """Fully parameterised HSV gradient for the cell fills.

    Every cell carries two normalised coordinates,

        d = depth / depth_ref        (recursion layer, 0 at the central cell)
        t = rho / rho_cap            (relative inside -> outside position)

    and each HSV channel is an independent ramp over a weighted blend of them,

        m_X   = w_X * d + (1 - w_X) * t
        X(d,t) = X_0 + (X_1 - X_0) * m_X ** gamma_X ,   X in {H, S, V}.

    Setting ``w_X = 1`` makes channel X depend on the recursion depth only,
    ``w_X = 0`` on the radial position only; ``gamma_X`` bends the ramp toward
    the inner (gamma > 1) or the outer (gamma < 1) end of its range.

    ``hue_mode='ramp'`` preserves that base ramp but adds a periodic angular
    offset and a very small deterministic per-cell offset.  Consequently two
    cells at the same recursion depth no longer collapse to one flat colour.

    ``hue_mode='adaptive-rainbow'`` wraps hue continuously around the disk and
    phase-shifts the wheel with depth and radius.  Saturation and value retain
    the depth/radius hierarchy, so the rainbow still reads as a gradient rather
    than as unrelated random colours.
    """

    name: str = "orchid"
    hue: Tuple[float, float] = (0.80, 0.595)
    hue_gamma: float = 0.72
    hue_depth_weight: float = 1.0
    hue_mode: str = "ramp"
    hue_cycles: float = 1.0
    angular_hue_span: float = 0.105
    cell_hue_jitter: float = 0.032
    saturation: Tuple[float, float] = (0.10, 0.52)
    saturation_gamma: float = 1.0
    saturation_depth_weight: float = 0.0
    saturation_cell_variation: float = 0.075
    value: Tuple[float, float] = (1.0, 0.70)
    value_gamma: float = 1.0
    value_depth_weight: float = 0.6
    value_cell_variation: float = 0.045

    @staticmethod
    def _ramp(limits, gamma, weight, d, t):
        m = np.clip(weight * d + (1.0 - weight) * t, 0.0, 1.0)
        lo, hi = limits
        return lo + (hi - lo) * m**gamma

    def rgb(self, depth_norm, radial_norm, angular_norm=0.0, cell_phase=0.5):
        """Map cell coordinates to RGB; all arguments may be broadcast arrays."""
        d, t, a, phase = np.broadcast_arrays(
            np.clip(np.asarray(depth_norm, dtype=float), 0.0, 1.0),
            np.clip(np.asarray(radial_norm, dtype=float), 0.0, 1.0),
            np.mod(np.asarray(angular_norm, dtype=float), 1.0),
            np.mod(np.asarray(cell_phase, dtype=float), 1.0),
        )
        base_hue = self._ramp(
            self.hue, self.hue_gamma, self.hue_depth_weight, d, t
        )
        micro = 2.0 * phase - 1.0
        if self.hue_mode == "adaptive-rainbow":
            # A periodic angular wheel remains continuous at theta = +/- pi.
            # Depth and radius rotate that wheel; the small cell phase prevents
            # exact RGB collisions even for cells with nearly equal centroids.
            wheel = np.mod(a + 0.381966 * d + 0.236068 * t, 1.0)
            hue = (
                self.hue[0]
                + self.hue_cycles * wheel
                + self.cell_hue_jitter * micro
            )
        elif self.hue_mode == "ramp":
            hue = (
                base_hue
                + self.angular_hue_span
                * np.sin(2.0 * np.pi * (a + 0.173205 * d))
                + self.cell_hue_jitter * micro
            )
        else:
            raise ValueError(
                "hue_mode must be 'ramp' or 'adaptive-rainbow', "
                f"got {self.hue_mode!r}"
            )
        sat = self._ramp(
            self.saturation,
            self.saturation_gamma,
            self.saturation_depth_weight,
            d,
            t,
        )
        val = self._ramp(self.value, self.value_gamma, self.value_depth_weight, d, t)
        sat = sat * (1.0 + self.saturation_cell_variation * micro)
        val = val * (1.0 - self.value_cell_variation * micro)
        return mcolors.hsv_to_rgb(
            np.stack([np.mod(hue, 1.0), np.clip(sat, 0.0, 1.0), np.clip(val, 0.0, 1.0)], axis=-1)
        )

    def key_image(self, n=192, angular_slice=0.125):
        """A depth/radius slice of the colour field at fixed polar angle."""
        d, t = np.meshgrid(np.linspace(0.0, 1.0, n), np.linspace(0.0, 1.0, n))
        return self.rgb(d, t, angular_norm=angular_slice, cell_phase=0.5)

    def angular_key_image(self, n=256, rows=20, depth=0.55, radius=0.72):
        """Thin legend strip showing within-layer angular HSV variation."""
        angle = np.linspace(0.0, 1.0, n, endpoint=False)
        rgb = self.rgb(depth, radius, angular_norm=angle, cell_phase=0.5)
        return np.repeat(rgb[None, :, :], rows, axis=0)

    def replace(self, **overrides) -> "CellPalette":
        return replace(self, **overrides)


CELL_PALETTES = {
    "adaptive-rainbow": CellPalette(
        name="adaptive-rainbow",
        hue=(0.80, 0.80),
        hue_mode="adaptive-rainbow",
        hue_cycles=1.0,
        cell_hue_jitter=0.018,
        saturation=(0.34, 0.72),
        saturation_gamma=0.82,
        saturation_depth_weight=0.36,
        saturation_cell_variation=0.035,
        value=(0.98, 0.76),
        value_gamma=0.88,
        value_depth_weight=0.62,
        value_cell_variation=0.018,
    ),
    "orchid": CellPalette(),
    "abyss": CellPalette(
        name="abyss",
        hue=(0.52, 0.72),
        hue_gamma=0.9,
        saturation=(0.16, 0.62),
        value=(0.99, 0.52),
        value_depth_weight=0.5,
    ),
    "ember": CellPalette(
        name="ember",
        hue=(0.135, 0.005),
        hue_gamma=0.65,
        saturation=(0.12, 0.66),
        saturation_depth_weight=0.25,
        value=(1.0, 0.74),
        value_depth_weight=0.7,
    ),
    "moss": CellPalette(
        name="moss",
        hue=(0.42, 0.28),
        hue_gamma=0.8,
        hue_depth_weight=0.5,
        saturation=(0.08, 0.45),
        value=(0.99, 0.62),
        value_depth_weight=0.55,
    ),
    "graphite": CellPalette(
        name="graphite",
        hue=(0.70, 0.70),
        saturation=(0.02, 0.09),
        value=(1.0, 0.52),
        value_depth_weight=0.5,
    ),
}

DEFAULT_CELL_PALETTE = CELL_PALETTES["adaptive-rainbow"]
DEFAULT_EDGE_PALETTE = EdgePalette()


def make_edge_cmap(palette: EdgePalette = DEFAULT_EDGE_PALETTE):
    """Backwards-compatible helper: the stroke colormap of ``palette``."""
    return palette.colormap()


def cell_rgb(
    depth_norm,
    radial_norm,
    angular_norm=0.0,
    cell_phase=0.5,
    palette: CellPalette = DEFAULT_CELL_PALETTE,
):
    """Backwards-compatible functional access to ``CellPalette.rgb``."""
    return palette.rgb(depth_norm, radial_norm, angular_norm, cell_phase)


def adaptive_outline_rgb(fill_rgb):
    """Turn palette colours into dark, high-contrast colours of the same family."""
    fill_rgb = np.asarray(fill_rgb, dtype=float)
    hsv = mcolors.rgb_to_hsv(np.clip(fill_rgb, 0.0, 1.0))
    hsv[..., 1] = np.clip(0.32 + 0.68 * hsv[..., 1], 0.0, 0.96)
    hsv[..., 2] = np.clip(0.28 + 0.10 * (1.0 - hsv[..., 2]), 0.28, 0.39)
    return mcolors.hsv_to_rgb(hsv)


def add_adaptive_model_boundaries(
    ax_disk,
    ax_half,
    palette: CellPalette,
    xlim_half=(-8.0, 8.0),
    samples=2400,
):
    """Draw D's circle and H's real boundary with colours derived from the fill."""
    theta = np.linspace(0.0, 2.0 * np.pi, samples + 1)
    disk_xy = np.column_stack([np.cos(theta), np.sin(theta)])
    disk_segments = np.stack([disk_xy[:-1], disk_xy[1:]], axis=1)
    angle_mid = np.mod((theta[:-1] + theta[1:]) / (4.0 * np.pi), 1.0)
    disk_fill = palette.rgb(
        1.0,
        1.0,
        angular_norm=angle_mid,
        cell_phase=np.mod(angle_mid * 0.61803398875, 1.0),
    )
    disk_colors = adaptive_outline_rgb(disk_fill)
    ax_disk.add_collection(
        LineCollection(
            disk_segments,
            colors=disk_colors,
            linewidths=2.30,
            capstyle="round",
            zorder=7,
        )
    )

    x = np.linspace(xlim_half[0], xlim_half[1], samples + 1)
    x_mid = 0.5 * (x[:-1] + x[1:])
    boundary_z = half_complex_to_disk(x_mid + 0.0j, direction=1j)
    boundary_angle = np.mod(np.angle(boundary_z) / (2.0 * np.pi), 1.0)
    half_fill = palette.rgb(
        1.0,
        1.0,
        angular_norm=boundary_angle,
        cell_phase=np.mod(boundary_angle * 0.61803398875, 1.0),
    )
    half_colors = adaptive_outline_rgb(half_fill)
    half_segments = np.stack(
        [
            np.column_stack([x[:-1], np.zeros(samples)]),
            np.column_stack([x[1:], np.zeros(samples)]),
        ],
        axis=1,
    )
    ax_half.add_collection(
        LineCollection(
            half_segments,
            colors=half_colors,
            linewidths=2.30,
            capstyle="butt",
            zorder=7,
        )
    )
    return adaptive_outline_rgb(
        palette.rgb(0.45, 0.35, angular_norm=0.125, cell_phase=0.5)
    )


def _lookup_cell_labels(points_xy, shading: "CellShading"):
    """Nearest arrangement labels in D; zero means invalid/outside."""
    points_xy = np.asarray(points_xy, dtype=float)
    h = shading.axis[1] - shading.axis[0]
    ix = np.rint((points_xy[:, 0] + 1.0) / h).astype(np.int64)
    iy = np.rint((points_xy[:, 1] + 1.0) / h).astype(np.int64)
    ok = (
        (ix >= 0)
        & (ix < shading.raster_n)
        & (iy >= 0)
        & (iy < shading.raster_n)
        & (np.hypot(points_xy[:, 0], points_xy[:, 1]) < 1.0)
    )
    labels = np.zeros(len(points_xy), dtype=np.int32)
    if np.any(ok):
        labels[ok] = shading.labels[iy[ok], ix[ok]]
    return labels


def _lookup_cell_rgba(points_xy, shading: "CellShading", lut):
    """Nearest-cell colour lookup in D; points outside the raster are invalid."""
    labels = _lookup_cell_labels(points_xy, shading)
    rgba = lut[labels].astype(float)
    if np.issubdtype(np.asarray(lut).dtype, np.integer):
        rgba /= 255.0
    return rgba


def _circular_hue_mix(h0, h1, weight):
    z = (1.0 - weight) * np.exp(2j * np.pi * h0) + weight * np.exp(
        2j * np.pi * h1
    )
    return np.mod(np.angle(z) / (2.0 * np.pi), 1.0)


def locally_adapted_stroke_rgb(base_rgb, nearby_rgb, local_weight=0.68):
    """Blend the R hue with adjacent fills and automatically choose contrast."""
    nearby_rgb = np.asarray(nearby_rgb, dtype=float)
    base_rgb = np.broadcast_to(np.asarray(base_rgb, dtype=float), nearby_rgb.shape)
    base_hsv = mcolors.rgb_to_hsv(np.clip(base_rgb, 0.0, 1.0))
    near_hsv = mcolors.rgb_to_hsv(np.clip(nearby_rgb, 0.0, 1.0))

    hue = _circular_hue_mix(base_hsv[:, 0], near_hsv[:, 0], local_weight)
    saturation = np.clip(
        0.34 + 0.38 * base_hsv[:, 1] + 0.28 * near_hsv[:, 1], 0.42, 0.92
    )
    luminance = nearby_rgb @ np.array([0.2126, 0.7152, 0.0722])
    # Smoothly move from a deep stroke on bright cells to a luminous stroke on
    # dark cells.  The sigmoid avoids a hard dark/light switching contour.
    light_choice = 1.0 / (1.0 + np.exp(16.0 * (luminance - 0.43)))
    value = 0.34 + 0.56 * light_choice
    return mcolors.hsv_to_rgb(np.column_stack([hue, saturation, value]))


def _smooth_rgb_path(rgb):
    """Short symmetric filter for soft, even colour flow along one arc."""
    rgb = np.asarray(rgb, dtype=float)
    if len(rgb) < 5:
        return rgb
    kernel = np.array([1.0, 2.5, 4.0, 2.5, 1.0])
    kernel /= kernel.sum()
    padded = np.pad(rgb, ((2, 2), (0, 0)), mode="edge")
    return np.column_stack(
        [np.convolve(padded[:, channel], kernel, mode="valid") for channel in range(3)]
    )


def adaptive_arc_segment_data(
    display_points,
    disk_points,
    base_rgb,
    alpha,
    shading: "CellShading",
    lut,
    palette: CellPalette,
    max_segments=180,
    side_offset_px=2.6,
):
    """Segment geometry plus locally adapted RGBA colours for one geodesic."""
    display_points = np.asarray(display_points, dtype=float)
    disk_points = np.asarray(disk_points, dtype=float)
    if len(display_points) < 2 or len(display_points) != len(disk_points):
        return np.zeros((0, 2, 2)), np.zeros((0, 4))

    if len(display_points) - 1 > max_segments:
        indices = np.linspace(0, len(display_points) - 1, max_segments + 1)
        indices = np.unique(np.rint(indices).astype(np.int64))
        display_points = display_points[indices]
        disk_points = disk_points[indices]

    display_segments = np.stack([display_points[:-1], display_points[1:]], axis=1)
    disk_mid = 0.5 * (disk_points[:-1] + disk_points[1:])
    tangent = disk_points[1:] - disk_points[:-1]
    tangent_norm = np.maximum(np.hypot(tangent[:, 0], tangent[:, 1]), 1e-15)
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]]) / tangent_norm[:, None]
    offset = side_offset_px * (shading.axis[1] - shading.axis[0])

    left = _lookup_cell_rgba(disk_mid + offset * normal, shading, lut)
    right = _lookup_cell_rgba(disk_mid - offset * normal, shading, lut)
    left_ok = left[:, 3] > 0.0
    right_ok = right[:, 3] > 0.0
    count = left_ok.astype(float) + right_ok.astype(float)
    nearby = (
        left[:, :3] * left_ok[:, None] + right[:, :3] * right_ok[:, None]
    ) / np.maximum(count[:, None], 1.0)

    missing = count == 0.0
    if np.any(missing):
        radius = np.clip(np.hypot(disk_mid[missing, 0], disk_mid[missing, 1]), 0.0, 1.0)
        rho_norm = hyperbolic_radius_from_abs_z(radius, shading.rho_cap) / shading.rho_cap
        angle_norm = np.mod(
            np.arctan2(disk_mid[missing, 1], disk_mid[missing, 0]) / (2.0 * np.pi),
            1.0,
        )
        nearby[missing] = palette.rgb(
            rho_norm,
            rho_norm,
            angular_norm=angle_norm,
            cell_phase=0.5,
        )

    rgb = _smooth_rgb_path(locally_adapted_stroke_rgb(base_rgb, nearby))
    rgba = np.column_stack([rgb, np.full(len(rgb), float(alpha))])
    return display_segments, rgba


@dataclass
class CellShading:
    """Everything about the arrangement that does not depend on the palette."""

    labels: np.ndarray  # (n, n) int32, walls already absorbed
    axis: np.ndarray
    n_cells: int
    area_px: np.ndarray
    depth: np.ndarray
    rho: np.ndarray
    abs_z: np.ndarray
    angular_norm: np.ndarray
    valid: np.ndarray
    depth_ref: float
    rho_cap: float
    raster_n: int

    @property
    def depth_norm(self):
        return self.depth / self.depth_ref

    @property
    def radial_norm(self):
        return self.rho / self.rho_cap

    @property
    def cell_phase(self):
        """Stable low-discrepancy phase used only to break exact colour ties."""
        labels = np.arange(self.n_cells + 1, dtype=float)
        return np.mod(
            0.6180339887498949 * labels
            + 0.4142135623730950 * self.depth
            + 0.2718281828459045 * self.radial_norm,
            1.0,
        )

    def lut(self, palette: CellPalette = DEFAULT_CELL_PALETTE, as_uint8=True):
        """Label -> RGBA lookup table; invalid labels stay fully transparent."""
        table = np.zeros((self.n_cells + 1, 4), dtype=np.float32)
        table[self.valid, :3] = palette.rgb(
            self.depth_norm[self.valid],
            self.radial_norm[self.valid],
            self.angular_norm[self.valid],
            self.cell_phase[self.valid],
        )
        table[self.valid, 3] = 1.0
        if as_uint8:
            quantized = np.rint(255.0 * table).astype(np.uint8)
            return self._resolve_quantized_color_collisions(quantized)
        return table

    def _resolve_quantized_color_collisions(self, table):
        """Guarantee distinct exported RGB triples with imperceptible LSB shifts.

        Continuous HSV colours can occasionally quantize to the same 8-bit RGB
        triple.  Search a tiny deterministic neighbourhood around a colliding
        triple; the maximum normal correction is four levels out of 255 and is
        applied before both D and H consume the shared lookup table.
        """
        offsets = [
            (dr, dg, db)
            for radius in range(1, 5)
            for dr in range(-radius, radius + 1)
            for dg in range(-radius, radius + 1)
            for db in range(-radius, radius + 1)
            if max(abs(dr), abs(dg), abs(db)) == radius
        ]
        offsets.sort(key=lambda v: (v[0] ** 2 + v[1] ** 2 + v[2] ** 2, v))

        used = set()
        for label in np.flatnonzero(self.valid):
            base = table[label, :3].astype(np.int16)
            key = tuple(int(x) for x in base)
            if key not in used:
                used.add(key)
                continue
            for offset in offsets:
                candidate = np.clip(base + np.asarray(offset), 0, 255)
                candidate_key = tuple(int(x) for x in candidate)
                if candidate_key not in used:
                    table[label, :3] = candidate.astype(np.uint8)
                    used.add(candidate_key)
                    break
            else:  # extraordinarily dense palette; retain validity over silence
                raise RuntimeError("unable to de-duplicate quantized cell colours")
        return table

    def coverage(self):
        disk_area_px = np.pi / 4.0 * self.raster_n**2
        return float(self.area_px[self.valid].sum() / disk_area_px)


def compute_cell_shading(
    arcs,
    raster_n=2600,
    min_cell_px=1,
    max_cell_area_frac=0.30,
    fill_cutoff=0.997,
    rho_cap=5.0,
    depth_percentile=95.0,
    absorb_walls=True,
) -> CellShading:
    """Label the arrangement and attach (depth, radial position) to every cell."""
    labels, axis, n_cells = build_cell_arrangement(arcs, n=raster_n)
    stats = cell_statistics(labels, axis, n_cells)
    rep = stats["rep"]
    depth = cell_recursion_depth(rep, arcs)
    abs_z = np.hypot(rep[:, 0], rep[:, 1])
    rho = hyperbolic_radius_from_abs_z(abs_z, rho_cap)
    angular_norm = np.mod(np.arctan2(rep[:, 1], rep[:, 0]) / (2.0 * np.pi), 1.0)

    disk_area_px = np.pi / 4.0 * raster_n**2
    valid = (
        (stats["area_px"] >= min_cell_px)
        & (stats["area_px"] <= max_cell_area_frac * disk_area_px)
        & (abs_z <= fill_cutoff)
    )
    valid[0] = False  # label 0 = walls and everything outside the disk

    depth_ref = (
        float(np.percentile(depth[valid], depth_percentile)) if np.any(valid) else 1.0
    )
    if absorb_walls:
        labels = close_wall_pixels(labels, axis)

    return CellShading(
        labels=labels,
        axis=axis,
        n_cells=n_cells,
        area_px=stats["area_px"],
        depth=depth,
        rho=rho,
        abs_z=abs_z,
        angular_norm=angular_norm,
        valid=valid,
        depth_ref=max(depth_ref, 1.0),
        rho_cap=rho_cap,
        raster_n=raster_n,
    )


def hyperbolic_radius_from_abs_z(radius, cap):
    radius = np.clip(np.asarray(radius, dtype=float), 0.0, np.tanh(cap / 2.0))
    return 2.0 * np.arctanh(radius)


def build_boundary_informed_lut(
    arcs,
    shading: CellShading,
    palette: CellPalette,
    edge_cmap,
    edge_norm,
    max_segments=140,
):
    """Final cell colours anchored to the mean colour of their boundary arcs."""
    provisional = shading.lut(palette, as_uint8=False)
    color_sum = np.zeros((shading.n_cells + 1, 3), dtype=np.float64)
    color_count = np.zeros(shading.n_cells + 1, dtype=np.int64)
    offset = 2.8 * (shading.axis[1] - shading.axis[0])

    for arc in arcs:
        points = np.asarray(arc["disk"], dtype=float)
        if len(points) - 1 > max_segments:
            indices = np.unique(
                np.rint(np.linspace(0, len(points) - 1, max_segments + 1)).astype(np.int64)
            )
            points = points[indices]
        mid = 0.5 * (points[:-1] + points[1:])
        tangent = points[1:] - points[:-1]
        tangent_norm = np.maximum(np.hypot(tangent[:, 0], tangent[:, 1]), 1e-15)
        normal = np.column_stack([-tangent[:, 1], tangent[:, 0]]) / tangent_norm[:, None]
        left_labels = _lookup_cell_labels(mid + offset * normal, shading)
        right_labels = _lookup_cell_labels(mid - offset * normal, shading)
        left_rgba = provisional[left_labels]
        right_rgba = provisional[right_labels]
        left_ok = left_rgba[:, 3] > 0.0
        right_ok = right_rgba[:, 3] > 0.0
        count = left_ok.astype(float) + right_ok.astype(float)
        nearby = (
            left_rgba[:, :3] * left_ok[:, None]
            + right_rgba[:, :3] * right_ok[:, None]
        ) / np.maximum(count[:, None], 1.0)

        missing = count == 0.0
        if np.any(missing):
            radius = np.clip(np.hypot(mid[missing, 0], mid[missing, 1]), 0.0, 1.0)
            radial = hyperbolic_radius_from_abs_z(radius, shading.rho_cap) / shading.rho_cap
            angle = np.mod(
                np.arctan2(mid[missing, 1], mid[missing, 0]) / (2.0 * np.pi), 1.0
            )
            nearby[missing] = palette.rgb(
                radial, radial, angular_norm=angle, cell_phase=0.5
            )

        base_edge = edge_cmap(edge_norm(arc["R"]))[:3]
        stroke = _smooth_rgb_path(
            locally_adapted_stroke_rgb(base_edge, nearby, local_weight=0.68)
        )
        for labels_side, ok_side in (
            (left_labels, left_ok),
            (right_labels, right_ok),
        ):
            usable = ok_side & shading.valid[labels_side]
            if np.any(usable):
                np.add.at(color_sum, labels_side[usable], stroke[usable])
                np.add.at(color_count, labels_side[usable], 1)

    mean_line = provisional[:, :3].copy()
    has_boundary = color_count > 0
    mean_line[has_boundary] = color_sum[has_boundary] / color_count[has_boundary, None]

    valid_area = shading.area_px[shading.valid]
    area_ref = float(np.percentile(valid_area, 88.0)) if len(valid_area) else 1.0
    smallness = np.clip(
        1.0 - np.sqrt(shading.area_px / max(area_ref, 1.0)), 0.0, 1.0
    )
    depth = np.clip(shading.depth_norm, 0.0, 1.0)
    radial = np.clip(shading.radial_norm, 0.0, 1.0)
    boundary_weight = np.clip(
        0.34 + 0.26 * smallness + 0.14 * radial + 0.08 * depth,
        0.34,
        0.76,
    )
    boundary_weight[~has_boundary] = 0.0

    base_hsv = mcolors.rgb_to_hsv(np.clip(provisional[:, :3], 0.0, 1.0))
    line_hsv = mcolors.rgb_to_hsv(np.clip(mean_line, 0.0, 1.0))
    hue = _circular_hue_mix(base_hsv[:, 0], line_hsv[:, 0], boundary_weight)
    saturation = (
        (1.0 - boundary_weight) * base_hsv[:, 1]
        + boundary_weight * line_hsv[:, 1]
    )
    saturation *= 0.98 + 0.18 * smallness + 0.06 * radial
    value = (
        (1.0 - boundary_weight) * base_hsv[:, 2]
        + boundary_weight * line_hsv[:, 2]
    )
    hierarchy = 0.58 * depth + 0.42 * radial
    value *= (1.03 - 0.11 * hierarchy) * (0.99 + 0.04 * smallness)

    final_rgb = mcolors.hsv_to_rgb(
        np.column_stack(
            [hue, np.clip(saturation, 0.0, 1.0), np.clip(value, 0.16, 1.0)]
        )
    )
    table = np.zeros((shading.n_cells + 1, 4), dtype=np.uint8)
    table[shading.valid, :3] = np.rint(
        255.0 * final_rgb[shading.valid]
    ).astype(np.uint8)
    table[shading.valid, 3] = 255
    table = shading._resolve_quantized_color_collisions(table)
    return table, smallness, color_count, boundary_weight


def render_cell_interior_lightfield(lut, shading: CellShading, smallness):
    """Smooth deep-edge / luminous-core shading inside every resolved cell."""
    labels = shading.labels
    rgba = lut[labels].astype(np.float32) / 255.0
    valid_px = rgba[..., 3] > 0.0
    if not np.any(valid_px):
        return np.rint(255.0 * rgba).astype(np.uint8)

    boundary = labels == 0
    boundary[1:, :] |= labels[1:, :] != labels[:-1, :]
    boundary[:-1, :] |= labels[:-1, :] != labels[1:, :]
    boundary[:, 1:] |= labels[:, 1:] != labels[:, :-1]
    boundary[:, :-1] |= labels[:, :-1] != labels[:, 1:]

    if _HAVE_SCIPY:
        distance = _ndi.distance_transform_edt(valid_px & ~boundary).astype(np.float32)
        label_ids = np.arange(shading.n_cells + 1)
        max_distance = _ndi.maximum(distance, labels=labels, index=label_ids)
        max_distance = np.nan_to_num(max_distance, nan=0.0).astype(np.float32)
        interior = distance / np.maximum(max_distance[labels], 1.0)
    else:  # pragma: no cover - the normal environment has scipy
        interior = np.full(labels.shape, 0.5, dtype=np.float32)
        interior[boundary] = 0.0
    interior = np.clip(interior, 0.0, 1.0)
    interior = interior * interior * (3.0 - 2.0 * interior)

    rgb = rgba[..., :3]
    small_px = smallness[labels].astype(np.float32)
    depth_px = np.clip(shading.depth_norm[labels], 0.0, 1.0).astype(np.float32)
    radial_px = np.clip(shading.radial_norm[labels], 0.0, 1.0).astype(np.float32)

    # Tiny and edge-near cells receive more chroma, making the asymptotic rings
    # legible without introducing random hue noise.
    luminance = (
        0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    )
    chroma_boost = 1.0 + 0.11 * small_px + 0.04 * radial_px
    rgb[:] = luminance[..., None] + (rgb - luminance[..., None]) * chroma_boost[..., None]

    hierarchy = 0.58 * depth_px + 0.42 * radial_px
    # A narrow, size-independent inner rim makes the cellular partition crisp,
    # while the much weaker broad component avoids a harsh centre-to-edge jump.
    rim = np.exp(-distance / 1.45) if _HAVE_SCIPY else (1.0 - interior)
    edge_factor = (
        1.0
        - (0.070 + 0.025 * hierarchy) * rim
        - 0.022 * (1.0 - interior)
    )
    rgb *= edge_factor[..., None]

    # A colour-preserving fluorescent core: sqrt(rgb) is a brighter version of
    # the same hue, and the smooth interior coordinate keeps the bloom natural.
    glow = (0.035 + 0.045 * (1.0 - hierarchy) + 0.025 * small_px) * interior
    emission = np.sqrt(np.clip(rgb, 0.0, 1.0))
    rgb[:] = (1.0 - glow[..., None]) * rgb + glow[..., None] * emission
    rgb[:] = np.clip(rgb, 0.0, 1.0)
    rgba[~valid_px] = 0.0
    return np.rint(255.0 * rgba).astype(np.uint8)


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------


def render_pair(
    output_path=None,
    palette: CellPalette = DEFAULT_CELL_PALETTE,
    edge_palette: EdgePalette = DEFAULT_EDGE_PALETTE,
    shading: CellShading = None,
    viz: HyperbolicTilingArcVisualizer = None,
    raster_n=2600,
    min_cell_px=1,
    max_cell_area_frac=0.30,
    fill_cutoff=0.997,
    rho_cap=5.0,
):
    if viz is None:
        viz = HyperbolicTilingArcVisualizer().build()
    arcs, dropped_center = viz.prepared_arcs()

    # ----- shared edge encoding -------------------------------------------------
    r_min, r_max = viz.r_percentiles
    edge_cmap = edge_palette.colormap()
    edge_norm = Normalize(r_min, r_max, clip=True)

    xlim_half = (-8.0, 8.0)
    ylim_half = (0.0, 10.0)

    # ----- shared cell encoding -------------------------------------------------
    if shading is None:
        shading = compute_cell_shading(
            arcs,
            raster_n=raster_n,
            min_cell_px=min_cell_px,
            max_cell_area_frac=max_cell_area_frac,
            fill_cutoff=fill_cutoff,
            rho_cap=rho_cap,
        )
    labels, axis = shading.labels, shading.axis
    raster_n, rho_cap = shading.raster_n, shading.rho_cap
    depth, depth_ref = shading.depth, shading.depth_ref
    valid = shading.valid

    # Let the mean colour of every cell's incident geodesics feed back into
    # the fill.  D and H share this exact table and interior lightfield.
    lut, cell_smallness, boundary_sample_count, boundary_weight = (
        build_boundary_informed_lut(
            arcs, shading, palette, edge_cmap, edge_norm
        )
    )
    disk_rgba = render_cell_interior_lightfield(lut, shading, cell_smallness)

    # ----- background field (only visible where no closed cell was resolved) ----
    rho_step = 0.625
    rho_levels = np.arange(rho_step, rho_cap, rho_step)
    background = ListedColormap(
        np.array([mcolors.hsv_to_rgb((0.72, 0.10, 0.985))] * 8)
    )
    fill_norm = Normalize(0.0, rho_cap, clip=True)

    fig = plt.figure(figsize=(17.2, 8.15), facecolor="#f6f6f8")
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=[1.00, 1.58],
        left=0.035,
        right=0.865,
        bottom=0.085,
        top=0.895,
        wspace=0.14,
    )
    ax_disk = fig.add_subplot(grid[0, 0])
    ax_half = fig.add_subplot(grid[0, 1])
    cax_edge = fig.add_axes([0.895, 0.545, 0.013, 0.315])
    ax_key = fig.add_axes([0.895, 0.175, 0.072, 0.205])
    ax_angle = fig.add_axes([0.895, 0.095, 0.072, 0.032])

    for ax in (ax_disk, ax_half):
        ax.set_facecolor("#fbfbfc")

    disk_n = 820
    disk_axis = np.linspace(-1.0, 1.0, disk_n)
    disk_x, disk_y = np.meshgrid(disk_axis, disk_axis)
    disk_abs = np.hypot(disk_x, disk_y)
    disk_rho = hyperbolic_radius_from_abs_z(disk_abs, rho_cap)
    disk_rho[disk_abs >= 1.0] = np.nan
    ax_disk.imshow(
        disk_rho,
        extent=(-1.0, 1.0, -1.0, 1.0),
        origin="lower",
        cmap=background,
        norm=fill_norm,
        interpolation="bilinear",
        zorder=0,
    )
    # ----- the cell fills themselves --------------------------------------------
    ax_disk.imshow(
        disk_rgba,
        extent=(-1.0, 1.0, -1.0, 1.0),
        origin="lower",
        interpolation="antialiased",
        zorder=2,
    )

    # ----- pull the same labelling through A^{-1} into the half-plane ------------
    half_nx, half_ny = 3800, 2380  # supersampled, then filtered down by imshow
    half_x = np.linspace(*xlim_half, half_nx)
    half_y = np.linspace(1e-4, ylim_half[1], half_ny)
    half_xx, half_yy = np.meshgrid(half_x, half_y)
    half_z = half_complex_to_disk(half_xx + 1j * half_yy, direction=1j)
    half_rho = hyperbolic_radius_from_abs_z(np.abs(half_z), rho_cap)
    ax_half.imshow(
        half_rho,
        extent=(*xlim_half, *ylim_half),
        origin="lower",
        cmap=background,
        norm=fill_norm,
        interpolation="bilinear",
        zorder=0,
    )

    h_raster = axis[1] - axis[0]
    ix = np.rint((half_z.real + 1.0) / h_raster)
    iy = np.rint((half_z.imag + 1.0) / h_raster)
    on_grid = (
        (ix >= 0) & (ix < raster_n) & (iy >= 0) & (iy < raster_n) & (np.abs(half_z) < 1.0)
    )
    half_labels = np.zeros(half_z.shape, dtype=np.int32)
    half_labels[on_grid] = labels[
        iy[on_grid].astype(np.int64), ix[on_grid].astype(np.int64)
    ]
    half_rgba = np.zeros((*half_z.shape, 4), dtype=np.uint8)
    half_rgba[on_grid] = disk_rgba[
        iy[on_grid].astype(np.int64), ix[on_grid].astype(np.int64)
    ]
    ax_half.imshow(
        half_rgba,
        extent=(*xlim_half, *ylim_half),
        origin="lower",
        interpolation="antialiased",
        zorder=2,
    )

    # Palette-adaptive model boundaries and the selected vertical diameter.
    axis_color = add_adaptive_model_boundaries(
        ax_disk, ax_half, palette, xlim_half=xlim_half
    )
    ax_disk.plot(
        [0.0, 0.0],
        [-1.0, 1.0],
        color=axis_color,
        lw=0.80,
        alpha=0.48,
        zorder=5,
    )
    ax_half.axvline(0.0, color=axis_color, lw=0.80, alpha=0.48, zorder=5)

    # ----- draw each edge in both panels from the same prepared record ----------
    alpha_inner, alpha_outer = 0.97, 0.38
    alpha_r0, alpha_pow = 0.75, 2.2
    mapped_segments = 0
    mapped_points_for_check = []
    disk_segment_blocks, disk_color_blocks = [], []
    half_segment_blocks, half_color_blocks = [], []

    for arc in arcs:
        base_color = edge_cmap(edge_norm(arc["R"]))[:3]
        fade = np.clip((arc["r_out"] - alpha_r0) / (1.0 - alpha_r0), 0.0, 1.0) ** alpha_pow
        alpha = alpha_inner * (1.0 - fade) + alpha_outer * fade
        points = arc["disk"]
        disk_segments, disk_colors = adaptive_arc_segment_data(
            points,
            points,
            base_color,
            alpha,
            shading,
            lut,
            palette,
            max_segments=180,
        )
        if len(disk_segments):
            disk_segment_blocks.append(disk_segments)
            disk_color_blocks.append(disk_colors)

        if viz.use_ideal_endpoints:
            segments = half_plane_geodesic_segments(
                viz.cache[arc["id"]]["z1p"],
                viz.cache[arc["id"]]["z2p"],
                direction=1j,
                xlim=xlim_half,
                ylim=ylim_half,
            )
        else:
            segments = split_mapped_polyline(
                points, direction=1j, xlim=xlim_half, ylim=ylim_half
            )
        for segment in segments:
            w_segment = segment[:, 0] + 1j * segment[:, 1]
            z_segment = half_complex_to_disk(w_segment, direction=1j)
            disk_lookup = np.column_stack([z_segment.real, z_segment.imag])
            half_segments, half_colors = adaptive_arc_segment_data(
                segment,
                disk_lookup,
                base_color,
                alpha,
                shading,
                lut,
                palette,
                max_segments=240,
            )
            if len(half_segments):
                half_segment_blocks.append(half_segments)
                half_color_blocks.append(half_colors)
            mapped_segments += 1

        z = points[:, 0] + 1j * points[:, 1]
        stable = np.abs(align_diameter_to_real_axis(1j) * z - 1.0) > 2e-4
        if np.any(stable):
            mapped_points_for_check.append(z[stable][::25])

    if disk_segment_blocks:
        disk_adaptive_segments = np.concatenate(disk_segment_blocks, axis=0)
        disk_adaptive_colors = np.concatenate(disk_color_blocks, axis=0)
        disk_glow_colors = disk_adaptive_colors.copy()
        disk_glow_colors[:, :3] = np.sqrt(
            np.clip(disk_glow_colors[:, :3], 0.0, 1.0)
        )
        disk_glow_colors[:, 3] *= 0.080
        ax_disk.add_collection(
            LineCollection(
                disk_adaptive_segments,
                colors=disk_glow_colors,
                linewidths=2.40,
                capstyle="round",
                joinstyle="round",
                antialiased=True,
                zorder=3.7,
            )
        )
        ax_disk.add_collection(
            LineCollection(
                disk_adaptive_segments,
                colors=disk_adaptive_colors,
                linewidths=0.84,
                capstyle="round",
                joinstyle="round",
                antialiased=True,
                zorder=4,
            )
        )
    else:
        disk_adaptive_segments = np.zeros((0, 2, 2))

    if half_segment_blocks:
        half_adaptive_segments = np.concatenate(half_segment_blocks, axis=0)
        half_adaptive_colors = np.concatenate(half_color_blocks, axis=0)
        half_glow_colors = half_adaptive_colors.copy()
        half_glow_colors[:, :3] = np.sqrt(
            np.clip(half_glow_colors[:, :3], 0.0, 1.0)
        )
        half_glow_colors[:, 3] *= 0.072
        ax_half.add_collection(
            LineCollection(
                half_adaptive_segments,
                colors=half_glow_colors,
                linewidths=2.05,
                capstyle="round",
                joinstyle="round",
                antialiased=True,
                zorder=3.7,
            )
        )
        ax_half.add_collection(
            LineCollection(
                half_adaptive_segments,
                colors=half_adaptive_colors,
                linewidths=0.71,
                capstyle="round",
                joinstyle="round",
                antialiased=True,
                zorder=4,
            )
        )
    else:
        half_adaptive_segments = np.zeros((0, 2, 2))

    # ----- axes, labels, keys ---------------------------------------------------
    ax_disk.set_aspect("equal")
    ax_disk.set_xlim(-1.035, 1.035)
    ax_disk.set_ylim(-1.035, 1.035)
    ax_disk.set_xticks([])
    ax_disk.set_yticks([])
    for spine in ax_disk.spines.values():
        spine.set_visible(False)

    ax_half.set_aspect("equal", adjustable="box")
    ax_half.set_xlim(*xlim_half)
    ax_half.set_ylim(*ylim_half)
    ax_half.set_xlabel(r"$\operatorname{Re} w$", fontsize=11)
    ax_half.set_ylabel(r"$\operatorname{Im} w$", fontsize=11)
    ax_half.set_xticks(np.arange(-8, 9, 2))
    ax_half.set_yticks(np.arange(0, 11, 2))
    ax_half.tick_params(labelsize=9, colors="#3a3a42", length=3)
    ax_half.spines["top"].set_visible(False)
    ax_half.spines["right"].set_visible(False)
    ax_half.spines["left"].set_alpha(0.25)
    ax_half.spines["bottom"].set_alpha(0.25)

    ax_disk.set_title(
        "Poincar\u00e9 disk " + r"$\mathbb{D}$",
        fontsize=15,
        fontweight="semibold",
        pad=13,
        color="#202027",
    )
    ax_half.set_title(
        r"Cayley inversion / upper half-plane $\mathbb{H}$",
        fontsize=15,
        fontweight="semibold",
        pad=13,
        color="#202027",
    )
    fig.suptitle(
        "Locally adaptive geodesics and per-cell recursion shading",
        fontsize=18,
        fontweight="semibold",
        color="#18181e",
        y=0.965,
    )
    fig.text(
        0.46,
        0.925,
        r"$A(z)=i\,\dfrac{1-iz}{1+iz}$   |   same cell lightfield "
        r"$F(C(d,t,\theta,\iota),\,\overline{E}_{\partial C})$",
        ha="center",
        va="center",
        fontsize=11.5,
        color="#4b4b57",
    )

    edge_map = ScalarMappable(norm=edge_norm, cmap=edge_cmap)
    edge_map.set_array([])
    edge_bar = fig.colorbar(edge_map, cax=cax_edge, orientation="vertical")
    edge_bar.set_label(r"base hue from radius $R$ (locally adapted)", fontsize=10.0, labelpad=10)
    edge_bar.ax.tick_params(labelsize=8.5, length=3)
    edge_bar.outline.set_alpha(0.35)

    ax_key.imshow(
        palette.key_image(angular_slice=0.125),
        extent=(0.0, depth_ref, 0.0, rho_cap),
        origin="lower",
        aspect="auto",
        interpolation="bilinear",
    )
    ax_key.set_xlabel("recursion depth $d$", fontsize=9.5, labelpad=4)
    ax_key.set_ylabel(r"relative depth $t=\rho/\rho_{\max}$", fontsize=9.5, labelpad=4)
    ax_key.set_title(r"HSV key ($\theta=\pi/4$ slice)", fontsize=9.5, pad=6, color="#3a3a42")
    ax_key.tick_params(labelsize=8, length=3, colors="#3a3a42")
    ax_key.set_xticks(np.linspace(0.0, depth_ref, 3).round())
    ax_key.set_yticks([0.0, 2.5, 5.0])
    for spine in ax_key.spines.values():
        spine.set_alpha(0.3)

    ax_angle.imshow(
        palette.angular_key_image(),
        extent=(0.0, 2.0 * np.pi, 0.0, 1.0),
        origin="lower",
        aspect="auto",
        interpolation="bilinear",
    )
    ax_angle.set_yticks([])
    ax_angle.set_xticks([0.0, np.pi, 2.0 * np.pi])
    ax_angle.set_xticklabels([r"$0$", r"$\pi$", r"$2\pi$"])
    ax_angle.set_xlabel(r"within-layer angle $\theta$", fontsize=8.7, labelpad=1)
    ax_angle.tick_params(labelsize=7.5, length=2, colors="#3a3a42", pad=1)
    for spine in ax_angle.spines.values():
        spine.set_alpha(0.3)

    # ----- numerical checks -----------------------------------------------------
    if mapped_points_for_check:
        z_check = np.concatenate(mapped_points_for_check)
        w_check = disk_complex_to_half(z_check, direction=1j)
        z_roundtrip = half_complex_to_disk(w_check, direction=1j)
        roundtrip_error = float(np.max(np.abs(z_roundtrip - z_check)))
    else:
        roundtrip_error = float("nan")

    t = np.linspace(-0.95, 0.95, 501)
    mapped_midline = disk_complex_to_half(1j * t, direction=1j)
    midline_error = float(np.max(np.abs(mapped_midline.real)))

    valid_colors = lut[valid, :3]
    unique_color_count = (
        int(np.unique(valid_colors, axis=0).shape[0]) if len(valid_colors) else 0
    )
    same_depth_collisions = {}
    for depth_value in np.unique(depth[valid]):
        mask = valid & (depth == depth_value)
        colors_at_depth = lut[mask, :3]
        collisions = len(colors_at_depth) - np.unique(colors_at_depth, axis=0).shape[0]
        if collisions:
            same_depth_collisions[int(depth_value)] = int(collisions)

    if output_path is None:
        output_path = Path(__file__).with_name("poincare_inversion_correspondence.png")
    output_path = Path(output_path)
    fig.savefig(output_path, dpi=240, bbox_inches="tight", facecolor=fig.get_facecolor())

    render_stats = {
        "p_q": (viz.p, viz.q),
        "polygons_generated": len(viz.polys),
        "unique_edges_input": len(viz.edges),
        "paired_arcs_kept": len(arcs),
        "mapped_visible_segments": mapped_segments,
        "disk_locally_colored_line_segments": int(len(disk_adaptive_segments)),
        "half_plane_locally_colored_line_segments": int(len(half_adaptive_segments)),
        "stroke_color_model": "circular HSV blend of base R hue and two adjacent cells",
        "fill_color_model": "base hierarchy hue blended with mean incident-line colour",
        "cells_with_boundary_colour_mean": int(
            np.count_nonzero(valid & (boundary_sample_count > 0))
        ),
        "boundary_feedback_weight_min_max": (
            float(boundary_weight[valid].min()),
            float(boundary_weight[valid].max()),
        ) if np.any(valid) else None,
        "microcells_filled_area_le_5px": int(
            np.count_nonzero(valid & (shading.area_px <= 5))
        ),
        "near_limit_cells_filled_abs_z_ge_0_97": int(
            np.count_nonzero(valid & (shading.abs_z >= 0.97))
        ),
        "dropped_by_one_focus_filter": dropped_center,
        "R_5_95": viz.r_percentiles,
        "cell_palette": palette.name,
        "hue_mode": palette.hue_mode,
        "unique_cell_colors": unique_color_count,
        "same_depth_exact_color_collisions": same_depth_collisions,
        "raster_n": raster_n,
        "cells_labelled": shading.n_cells,
        "cells_filled": int(valid.sum()),
        "filled_area_fraction": shading.coverage(),
        "depth_min_max": (int(depth[valid].min()), int(depth[valid].max()))
        if np.any(valid)
        else None,
        "depth_reference": depth_ref,
        "roundtrip_max_abs_error": roundtrip_error,
        "mapped_vertical_diameter_max_abs_Re_w": midline_error,
        "output": str(output_path.resolve()),
    }
    return fig, (ax_disk, ax_half), render_stats


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", default=None, help="output PNG path")
    parser.add_argument(
        "-p",
        "--palette",
        default="adaptive-rainbow",
        choices=sorted(CELL_PALETTES),
        help="named HSV preset for the cell fills",
    )
    parser.add_argument("--raster", type=int, default=2600, help="cell raster size")
    parser.add_argument("--hue", type=float, nargs=2, metavar=("H0", "H1"))
    parser.add_argument(
        "--hue-mode",
        choices=("ramp", "adaptive-rainbow"),
        default=None,
        help="bounded hue ramp or full adaptive HSV wheel",
    )
    parser.add_argument("--hue-cycles", type=float, default=None)
    parser.add_argument("--angular-hue-span", type=float, default=None)
    parser.add_argument("--cell-hue-jitter", type=float, default=None)
    parser.add_argument("--hue-gamma", type=float, default=None)
    parser.add_argument("--hue-depth-weight", type=float, default=None)
    parser.add_argument("--sat", type=float, nargs=2, metavar=("S0", "S1"))
    parser.add_argument("--sat-gamma", type=float, default=None)
    parser.add_argument("--sat-depth-weight", type=float, default=None)
    parser.add_argument("--val", type=float, nargs=2, metavar=("V0", "V1"))
    parser.add_argument("--val-gamma", type=float, default=None)
    parser.add_argument("--val-depth-weight", type=float, default=None)
    return parser.parse_args(argv)


def palette_from_args(args) -> CellPalette:
    palette = CELL_PALETTES[args.palette]
    overrides = {}
    if args.hue is not None:
        overrides["hue"] = tuple(args.hue)
    if args.sat is not None:
        overrides["saturation"] = tuple(args.sat)
    if args.val is not None:
        overrides["value"] = tuple(args.val)
    for flag, field_name in (
        ("hue_mode", "hue_mode"),
        ("hue_cycles", "hue_cycles"),
        ("angular_hue_span", "angular_hue_span"),
        ("cell_hue_jitter", "cell_hue_jitter"),
    ):
        value = getattr(args, flag)
        if value is not None:
            overrides[field_name] = value
    for flag, field_name in (
        ("hue_gamma", "hue_gamma"),
        ("hue_depth_weight", "hue_depth_weight"),
        ("sat_gamma", "saturation_gamma"),
        ("sat_depth_weight", "saturation_depth_weight"),
        ("val_gamma", "value_gamma"),
        ("val_depth_weight", "value_depth_weight"),
    ):
        value = getattr(args, flag)
        if value is not None:
            overrides[field_name] = value
    return palette.replace(**overrides) if overrides else palette


if __name__ == "__main__":
    _args = _parse_args()
    _, _, stats_out = render_pair(
        output_path=_args.output,
        palette=palette_from_args(_args),
        raster_n=_args.raster,
    )
    for key, value in stats_out.items():
        print(f"{key}: {value}")
