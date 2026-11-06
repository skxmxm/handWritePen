"""Sample the finished rear-shell neck walls; mm, CadQuery 2.8.

This independently reads exported STEP solids. It checks transverse ray lengths
through the outermost wall at critical section changes; it is not a general
minimum-wall solver or a physical strength test.
"""
from pathlib import Path
import json

import cadquery as cq

R = Path(__file__).resolve().parents[1]
base = cq.importers.importStep(str(R / 'cad/03_rear_base.step')).val()
cover = cq.importers.importStep(str(R / 'cad/04_press_release_cover.step')).val()
shell = base.fuse(cover).clean()

# Include both sides of collar, former long cylindrical cavity, shoulder, and
# main-cavity transitions. The old 0.2 mm floor fails at X=77.9 and 78.01.
stations = [
    69.05, 70, 71.49, 71.51, 71.79, 71.81, 72, 73, 74,
    74.19, 74.21, 75, 75.89, 75.91, 76.05, 76.09, 76.11,
    76.19, 76.21, 76.8, 76.99, 77.01, 77.09, 77.11,
    77.5, 77.9, 77.99, 78.01, 78.09, 78.2, 78.5,
]
threshold = 1.0


def outer_segment(start, end):
    """Return the first continuous solid interval met from an external start."""
    a, b = cq.Vector(*start), cq.Vector(*end)
    direction = b.sub(a).normalized()
    line = cq.Edge.makeLine(a, b)
    sections = shell.intersect(line).Edges()
    intervals = []
    for edge in sections:
        ds = sorted(cq.Vector(*v.toTuple()).sub(a).dot(direction)
                    for v in edge.Vertices())
        if len(ds) == 2 and ds[1] - ds[0] > 1e-7:
            intervals.append(ds)
    intervals.sort()
    if not intervals:
        return None
    first = intervals[0]
    for next_interval in intervals[1:]:
        if next_interval[0] > first[1] + 1e-6:
            break
        first[1] = max(first[1], next_interval[1])
    point0 = a.add(direction.multiply(first[0])).toTuple()
    point1 = a.add(direction.multiply(first[1])).toTuple()
    return {
        'wall_mm': round(first[1] - first[0], 6),
        'outer_point_mm': [round(v, 6) for v in point0],
        'inner_point_mm': [round(v, 6) for v in point1],
    }


samples = []
for x in stations:
    for y in (-4.5, -1.5, 0.0, 1.5, 4.5):
        for face, start, end in (
            ('bottom', (x, y, -10), (x, y, 0)),
            ('top', (x, y, 10), (x, y, 0)),
        ):
            result = outer_segment(start, end)
            samples.append({'x_mm': x, 'face': face, 'offset_mm': y,
                            **(result or {'wall_mm': None})})
    for z in (-2.0, -0.5, 0.5, 2.0):
        for face, start, end in (
            ('left', (x, -20, z), (x, 0, z)),
            ('right', (x, 20, z), (x, 0, z)),
        ):
            result = outer_segment(start, end)
            samples.append({'x_mm': x, 'face': face, 'offset_mm': z,
                            **(result or {'wall_mm': None})})

failures = [s for s in samples
            if s['wall_mm'] is None or s['wall_mm'] < threshold - 1e-5]
minimum = min((s for s in samples if s['wall_mm'] is not None),
              key=lambda s: s['wall_mm'])
report = {
    'units': 'mm',
    'minimum_required_sampled_wall_mm': threshold,
    'sample_count': len(samples),
    'minimum_sample': minimum,
    'failures': failures,
    'samples': samples,
    'scope': ('Finite transverse rays on exported rear-shell STEP solids, '
              'focused on the neck/collar/cavity transitions. Does not certify '
              'global minimum wall, printed strength, or print tolerances.'),
}
(R / 'reports/neck_validation.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != 'samples'},
                 ensure_ascii=False, indent=2), flush=True)
assert not failures, 'Rear neck has a missing or sub-1.0 mm sampled wall'
