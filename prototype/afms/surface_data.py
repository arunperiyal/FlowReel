"""Wall shear and sectional forces on the cylinder, for every step of the window.

Usage: python surface_data.py CASE_DIR OUT_DIR [--t1 5000] [--t2 5600] [--step 5] [--jobs 8]

Writes OUT_DIR/step_<n>.npz with the body surface (points, cells), and per cell: the
outward normal, area, pressure and the skin-friction vector cf. It also holds the
sectional lift and drag coefficients of SECTIONS strips along the span.

Everything comes from velocity and pressure in the PLT. The stored vorticity, which the
flexflow wall_shear output uses, is a nodal sum whose size depends on the mesh, so it is
not used. With U = D = 1, the traction on the body is t = -p n + mu (grad u + grad u^T) n,
mu = rho / Re, and

    cf  = 2 / Re * ((grad u + grad u^T) n)        (viscous traction / q, q = rho U^2 / 2)
    CL  = F_y / (q D dx),  CD = F_z / (q D dx)     per strip of length dx = L / SECTIONS

Eddy viscosity is zero at the wall, so mu is the molecular viscosity. Frames already in
OUT_DIR are skipped.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

# Importing render_frames also sets the rendering and thread options.
import render_frames as rf
import pyvista as pv
from scipy.spatial import cKDTree

from fxplt import PltFile

RE, RHO = 1000.0, 1000.0
Q = 0.5 * RHO  # U = 1
SPAN, SECTIONS = 12.0, 48
NEAR = ((-1, 13), (-2.5, 2.5), (-2.5, 2.5))  # enough flow around the body for its gradient


def surface(case, step):
    """Body surface cells with pressure, and the velocity gradient at its nodes."""
    plt = PltFile(str(Path(case) / "binary" / f"riser.{step}.plt"))
    names = [zone["name"] for zone in plt.zones]
    cyl_points, cyl_conn, cyl_data, _ = plt.load_zone(names.index("cyl"))
    cyl_type = plt.zones[names.index("cyl")]["ztype"]
    index = plt.first_volume_zone()
    points, conn, data, _ = plt.load_zone(index)
    ztype = plt.zones[index]["ztype"]
    plt.close()
    saved = rf.CROP
    rf.CROP = NEAR
    mesh = rf.grid(*rf.crop(points, conn, {k: data[k] for k in ("U", "V", "W")}), ztype)
    rf.CROP = saved
    mesh["vel"] = np.c_[mesh["U"], mesh["V"], mesh["W"]]
    grad = mesh.compute_derivative(scalars="vel", gradient="grad")["grad"].reshape(-1, 3, 3)
    gap, nearest = cKDTree(mesh.points).query(cyl_points)
    body = rf.grid(cyl_points, cyl_conn, {"Pressure": cyl_data["Pressure"]}, cyl_type)
    body = body.extract_surface(algorithm="dataset_surface").triangulate()
    # One winding for every cell, so that their normals all face the same side.
    body = body.compute_normals(cell_normals=True, point_normals=False, consistent_normals=True,
                                auto_orient_normals=False, split_vertices=False)
    return body, grad[nearest], float(gap.max())


def compute(job):
    case, out, step = job
    target = Path(out) / f"step_{step}.npz"
    if target.exists():
        return step, None
    body, grad_nodes, gap = surface(case, step)
    cells = body.faces.reshape(-1, 4)[:, 1:]
    corners = body.points[cells]
    centre = corners.mean(1)
    normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    area = 0.5 * np.linalg.norm(normal, axis=1)
    normal /= 2 * area[:, None]
    # Outward from the body: away from the axis (the mean of each strip), taken over the
    # whole body, since groove walls face along the surface.
    strip = np.clip((centre[:, 0] / SPAN * SECTIONS).astype(int), 0, SECTIONS - 1)
    axis = np.zeros((SECTIONS, 3))
    for k in range(SECTIONS):
        axis[k] = centre[strip == k].mean(0)
    radial = centre - axis[strip]
    radial[:, 0] = 0
    normal *= np.sign((normal * radial).sum())
    grad = grad_nodes[cells].mean(1)  # per cell, from its corners
    strain2 = grad + grad.transpose(0, 2, 1)
    cf = 2 / RE * np.einsum("cij,cj->ci", strain2, normal)
    pressure = body["Pressure"][cells].mean(1)
    force = (-pressure[:, None] * normal + Q * cf) * area[:, None]  # on the body
    dx = SPAN / SECTIONS
    lift = np.bincount(strip, force[:, 1], SECTIONS) / (Q * dx)
    drag = np.bincount(strip, force[:, 2], SECTIONS) / (Q * dx)
    np.savez_compressed(target, points=body.points, cells=cells, normal=normal, area=area,
                        pressure=pressure, cf=cf, lift=lift, drag=drag, step=step)
    return step, gap


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case")
    parser.add_argument("out")
    parser.add_argument("--t1", type=int, default=5000)
    parser.add_argument("--t2", type=int, default=5600)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    case = Path(args.case).resolve()
    jobs = [(case, args.out, s) for s in range(args.t1, args.t2 + 1, args.step)]
    with ProcessPoolExecutor(args.jobs) as pool:
        for step, gap in pool.map(compute, jobs):
            if gap is not None:
                print(f"{step}: body nodes matched to the flow within {gap:.1e}", flush=True)


if __name__ == "__main__":
    main()
