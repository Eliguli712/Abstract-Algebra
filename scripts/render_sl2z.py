#!/usr/bin/env python3
"""Reproduce a finite, exact-matrix modular tessellation in the upper half-plane.

Dependencies: Python 3, numpy, matplotlib. No input images or network are needed.
Depth is the shortest word length for {S,T,T^{-1}} in PSL(2,Z), NOT a denominator.
"""
from __future__ import annotations

import colorsys
import json
import math
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

OUT = Path(__file__).resolve().parents[1] / "outputs" / "sl2z"
I = (1, 0, 0, 1)
S = (0, -1, 1, 0)
T = (1, 1, 0, 1)
TI = (1, -1, 0, 1)
RHO_L = complex(-0.5, math.sqrt(3) / 2)
RHO_R = complex(0.5, math.sqrt(3) / 2)


def canon(g):
    a, b, c, d = g
    return tuple(-x for x in g) if c < 0 or (c == 0 and d < 0) else g


def mul(g, h):
    a, b, c, d = g
    e, f, k, l = h
    return canon((a*e+b*k, a*f+b*l, c*e+d*k, c*f+d*l))


def inverse(g):
    a, b, c, d = g
    return canon((d, -b, -c, a))


def act(g, z):
    a, b, c, d = g
    x, y = z.real, z.imag
    den = (c*x+d)**2 + (c*y)**2
    return complex(((a*x+b)*(c*x+d)+a*c*y*y)/den, y/den)


def enumerate_tiles(n=18):
    tiles = [(I, 0)]
    seen = {I: 0}
    for g, depth in tiles:
        if depth == n:
            continue
        for gen in (S, T, TI):
            h = mul(g, gen)
            if h not in seen:
                seen[h] = depth + 1
                tiles.append((h, depth + 1))
    return tiles, seen


def reduce_point(z):
    """Return (w,h) with w=h*z in the closed standard domain, away from tie edges."""
    h = I
    for _ in range(100):
        n = math.floor(z.real + 0.5)
        if n:
            z -= n
            h = mul((1, -n, 0, 1), h)
        if abs(z)**2 >= 1 - 1e-12:
            return z, h
        z = -1/z
        h = mul(S, h)
    raise RuntimeError("Reduction did not converge")


def arc_geometry(p, q):
    if abs(p.real-q.real) < 1e-12:
        return None
    center = (abs(p)**2-abs(q)**2)/(2*(p.real-q.real))
    radius = abs(p-center)
    theta1 = math.atan2(max(0, p.imag), p.real-center)
    theta2 = math.atan2(max(0, q.imag), q.real-center)
    return center, radius, theta1, theta2


def geodesic_points(p, q):
    """Cubic Bezier circle segments, error far below an output pixel."""
    geom = arc_geometry(p, q)
    if geom is None:
        return [(q.real, q.imag)], [MplPath.LINETO]
    center, radius, t1, t2 = geom
    n = max(1, math.ceil(abs(t2-t1)/(math.pi/4)))
    verts, codes = [], []
    for i in range(n):
        a = t1+(t2-t1)*i/n
        b = t1+(t2-t1)*(i+1)/n
        k = 4/3*math.tan((b-a)/4)
        za = complex(center+radius*math.cos(a), radius*math.sin(a))
        zb = complex(center+radius*math.cos(b), radius*math.sin(b))
        da = complex(-radius*math.sin(a), radius*math.cos(a))
        db = complex(-radius*math.sin(b), radius*math.cos(b))
        for zz in (za+k*da, zb-k*db, zb):
            verts.append((zz.real, zz.imag))
            codes.append(MplPath.CURVE4)
    return verts, codes


def tile_geometry(g, top=3.2):
    p, q = act(g, RHO_L), act(g, RHO_R)
    if g[2] == 0:
        vv = [(p.real, p.imag), (p.real, top), (q.real, top), (q.real, q.imag)]
        cc = [MplPath.MOVETO, MplPath.LINETO, MplPath.LINETO, MplPath.LINETO]
        extra, codes = geodesic_points(q, p)
        vv += extra
        cc += codes
        ymax = top
        bounds = (min(p.real, q.real), max(p.real, q.real), ymax)
    else:
        cusp = complex(g[0]/g[2], 0)
        vv, cc = [(cusp.real, 0)], [MplPath.MOVETO]
        ymax = max(p.imag, q.imag)
        for z1, z2 in ((cusp, q), (q, p), (p, cusp)):
            extra, codes = geodesic_points(z1, z2)
            vv += extra
            cc += codes
            geom = arc_geometry(z1, z2)
            if geom:
                _, radius, t1, t2 = geom
                if min(t1,t2) <= math.pi/2 <= max(t1,t2):
                    ymax = max(ymax, radius)
        bounds = (min(p.real, q.real, cusp.real), max(p.real, q.real, cusp.real), ymax)
    vv.append(vv[0])
    cc.append(MplPath.CLOSEPOLY)
    return MplPath(vv, cc), bounds, (p,q)


def validate(tiles, depths):
    assert mul(S,S) == I
    assert mul(mul(S,T),mul(mul(S,T),mul(S,T))) == I
    max_inverse_error = 0.0
    for g, _ in tiles:
        assert g[0]*g[3]-g[1]*g[2] == 1
        assert mul(g,inverse(g)) == I
        z = act(g, 0.13+1.7j)
        w, h = reduce_point(z)
        assert inverse(h) == g, (g, h)
        max_inverse_error = max(max_inverse_error,abs(w-(0.13+1.7j)))
    rng = np.random.default_rng(712)
    reduced = []
    for z in rng.uniform(-2.55,2.55,1000)+1j*rng.uniform(0.012,2.0,1000):
        w,h = reduce_point(z)
        assert -.5000001 <= w.real <= .5000001 and abs(w)>=1-1e-10
        assert abs(act(h,z)-w) < 1e-8
        reduced.append(inverse(h) in depths)
    area = 2*math.asin(0.5)
    return {"max_depth": max(depths.values()), "tiles":len(tiles),
            "depth_counts":dict(Counter(d for _,d in tiles)),
            "all_determinants_one":True, "all_inverse_reductions_passed":True,
            "maximum_inverse_error":max_inverse_error,
            "random_reduction_checks":1000,
            "random_points_in_finite_display":sum(reduced),
            "note":"Finite generator depth need not cover all points in the viewport.",
            "hyperbolic_area_of_F":area}


def render(tiles, n=18):
    plt.rcParams.update({"font.family":"DejaVu Sans", "mathtext.fontset":"dejavusans",
                         "svg.fonttype":"none", "savefig.facecolor":"#050b17"})
    bg, cyan, pale = "#050b17", "#68cce9", "#e2edf4"
    fig = plt.figure(figsize=(18,8.9), facecolor=bg)
    ax = fig.add_axes([.055,.16,.91,.71], facecolor=bg)
    ax.set_xlim(-2.65,2.65)
    ax.set_ylim(0,2.06)
    ax.set_aspect("equal", adjustable="box")
    patches, fills, edges, widths = [], [], [], []
    vertices = {}
    for g, depth in tiles:
        path,bounds,ends = tile_geometry(g)
        lo,hi,ymax = bounds
        if lo>2.66 or hi< -2.66 or ymax<.0011 or (hi-lo)<.0005:
            continue
        patches.append(PathPatch(path))
        hue = (.54+.085*math.sin(1.7*(lo+hi))+.09*depth/18)%1
        rgb = colorsys.hsv_to_rgb(hue,.53,.63)
        fills.append((*rgb, .12+.13*(1-depth/(n+3))))
        edges.append((*matplotlib.colors.to_rgb(cyan), .35+.43*math.sqrt(min(1,ymax/.6))))
        widths.append(.34+.23*min(1,ymax/.6))
        for z in ends:
            if -2.66<z.real<2.66 and z.imag>.021:
                vertices[(round(z.real,8),round(z.imag,8))]=z
    # Soft, restrained halo, then precise boundaries.
    glow = PatchCollection(patches, facecolors="none", edgecolors=(*matplotlib.colors.to_rgb(cyan),.045), linewidths=2.5)
    ax.add_collection(glow)
    coll = PatchCollection(patches, facecolors=fills, edgecolors=edges, linewidths=widths)
    ax.add_collection(coll)
    fpath,_,_=tile_geometry(I)
    ax.add_patch(PathPatch(fpath, facecolor="#d7b75b",alpha=.19,edgecolor="none"))
    ax.add_patch(PathPatch(fpath, facecolor="none",edgecolor="#e8c66e",linewidth=1.22,alpha=.94))
    zz=list(vertices.values())
    for size,alpha in ((38,.025),(16,.065),(4,.72)):
        ax.scatter([z.real for z in zz],[z.imag for z in zz],s=[size*min(1,z.imag/.4)+.25 for z in zz],
                   c=cyan,alpha=alpha,edgecolors="none",zorder=5)
    for n0 in range(-2,3):
        label = r"$\mathcal{F}$" if n0==0 else (r"$T\mathcal{F}$" if n0==1 else (r"$T^{-1}\mathcal{F}$" if n0==-1 else rf"$T^{{{n0}}}\mathcal{{F}}$"))
        ax.text(n0,1.40,label,color="#e8cb80" if n0==0 else pale,fontsize=17,ha="center")
        label2 = r"$S\mathcal{F}$" if n0==0 else (r"$TS\mathcal{F}$" if n0==1 else (r"$T^{-1}S\mathcal{F}$" if n0==-1 else rf"$T^{{{n0}}}S\mathcal{{F}}$"))
        ax.text(n0,.62,label2,color=pale,fontsize=13,ha="center",alpha=.92)
    for n0 in (-2,-1,0,1,2):
        ax.text(n0,1.96,r"$\uparrow\,\infty$",color=pale,fontsize=10,ha="center",alpha=.6)
    ax.scatter([0],[1],s=14,c="#e8c66e",zorder=8)
    ax.annotate(r"$i$",(0,1),xytext=(10,9),textcoords="offset points",color="#e8cb80",fontsize=13)
    for x,t in ((-.5,r"$\rho=-\frac{1}{2}+\frac{\sqrt{3}}{2}i$"),(.5,r"$\rho+1$")):
        ax.annotate(t,(x,math.sqrt(3)/2),xytext=(-12 if x<0 else 12,13),textcoords="offset points",ha="right" if x<0 else "left",color=pale,fontsize=11)
    ax.set_xticks([-2,-1.5,-1,-.5,0,.5,1,1.5,2])
    ax.set_xticklabels([r"$-2$",r"$-3/2$",r"$-1$",r"$-1/2$",r"$0$",r"$1/2$",r"$1$",r"$3/2$",r"$2$"])
    ax.set_yticks([.5,1,1.5,2])
    ax.tick_params(colors="#8fa8ba",labelsize=10,length=3,width=.6,pad=9)
    for k,spine in ax.spines.items():
        spine.set_visible(k in ("bottom","left"))
        spine.set_color("#446073")
        spine.set_linewidth(.6)
    ax.set_xlabel(r"$\operatorname{Re} z$",color="#a0b7c7",fontsize=12,labelpad=12)
    ax.set_ylabel(r"$\operatorname{Im} z$",color="#a0b7c7",fontsize=12,labelpad=12)
    fig.text(.058,.94,r"$\mathrm{SL}_2(\mathbb{Z})$  /  DIE OBERE HALBEBENE",color=pale,fontsize=23)
    fig.text(.06,.892,r"$\mathcal{F}=\{z\in\mathbb{H}:\ |\operatorname{Re}z|\leq\frac{1}{2},\ |z|\geq1\}$",color="#a5bfce",fontsize=15)
    fig.text(.626,.9,r"$S(z)=-1/z\qquad T(z)=z+1$",color="#c2dbe6",fontsize=15)
    fig.text(.06,.055,"GEODÄTEN SENKRECHT ZUR REELLEN ACHSE  /  RATIONALE SPITZEN",color="#91aabd",fontsize=9)
    fig.text(.94,.055,f"ENDLICHE ENTWICKLUNG  N = {n}   |   g und −g wirken identisch",color="#91aabd",fontsize=9,ha="right")
    fig.savefig(OUT/"SL2Z_H_Tessellation.png",dpi=240,facecolor=bg)
    fig.savefig(OUT/"SL2Z_H_Tessellation.svg",facecolor=bg)
    plt.close(fig)
    return len(patches)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    tiles,depths=enumerate_tiles(18)
    report=validate(tiles,depths)
    report["drawn_tiles"]=render(tiles)
    (OUT/"validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
