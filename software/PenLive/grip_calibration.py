"""Grip-angle correction from one horizontal stroke.

Rotate the accumulated count position once. The canvas rounds to pixels;
those integers are not fed back into the sum, so the error does not accumulate.
"""
import math

MIN_GRIP_CHORD = 200

def line_angle(start, end, minimum=MIN_GRIP_CHORD):
    """Tilt of an undirected stroke, in radians within (-pi/2, pi/2].

    Travel right-to-left differs by 180 degrees and does not flip the result.
    Returns None when the chord is shorter than `minimum` counts.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if dx*dx + dy*dy < minimum*minimum:
        return None
    angle = math.atan2(dy, dx)
    half = math.pi / 2
    if angle > half:
        angle -= math.pi
    elif angle < -half:
        angle += math.pi
    return angle

def rotate_point(point, angle):
    """Rotate a count position by -angle so a line of that tilt lands on +X."""
    if point is None or not angle:
        return point
    x, y = point
    cosine, sine = math.cos(angle), math.sin(angle)
    return (x*cosine + y*sine, -x*sine + y*cosine)

def last_ink_stroke(records):
    """Points of the newest ink segment, and whether it ended on a pen-up edge."""
    points = []
    released = False
    seen_ink = False
    for point, _stamp, flush in reversed(records):
        if point is None:
            if points:
                break
            continue
        if not seen_ink:
            released = bool(flush)
            seen_ink = True
        points.append(point)
    points.reverse()
    return points, released
