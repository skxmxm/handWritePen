"""Grip calibration rotates accumulated counts once and keeps a slanted grip line horizontal."""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grip_calibration import line_angle, rotate_point
from pen_live import PenApp

assert line_angle((0, 0), (1000, 0)) == 0
assert line_angle((0, 0), (-1000, 0)) == 0
assert line_angle((0, 0), (100, 0)) is None
tilt = math.radians(-15)
assert abs(line_angle((0, 0), (1000*math.cos(tilt), 1000*math.sin(tilt))) - tilt) < 1e-12
opposite = (-1000*math.cos(tilt), -1000*math.sin(tilt))
assert abs(line_angle((0, 0), opposite) - tilt) < 1e-12
left = rotate_point((3, 5), 0.4)
right = rotate_point((7, -2), 0.4)
both = rotate_point((10, 3), 0.4)
assert abs(both[0] - (left[0]+right[0])) < 1e-9
assert abs(both[1] - (left[1]+right[1])) < 1e-9
assert rotate_point((40, -7), 0) == (40, -7)

app = PenApp(demo=False)
app.smoothing.set('关闭')
app.state.set_smoothing('关闭')
app.auto_fit.set(False)
for timer in app.root.tk.call('after', 'info'):
    app.root.after_cancel(timer)
app.root.update()
angle = math.radians(20)
length = 1000
app.grip_button.invoke()
assert app.grip_calibrating
for step in range(11):
    unit = step / 10
    along = (length*unit*math.cos(angle), length*unit*math.sin(angle))
    app.state.append_point((along[0], -along[1]), flush=step == 10)
    app.state.latest_xy = app.state.raw_records[-1][0]
app.state.cursor_valid = True
app.state.active = False
app.state.break_trace()
app._observe_grip()
assert not app.grip_calibrating
assert abs(app.trace_view.grip_angle - angle) < 1e-12
assert '已校正' in app.grip_text.get()
stored = next(item[0] for item in reversed(app.state.raw_records) if item[0] is not None)
assert abs(stored[1]) > 100
app.draw_trace()
app.root.update_idletasks()
coords = []
for item in app.canvas.find_withtag('trace_line'):
    coords.extend(app.canvas.coords(item))
ys = coords[1::2]
assert max(ys) - min(ys) < 0.05
cx, cy = ((app.canvas.coords(app.trace_view.dot)[0] + app.canvas.coords(app.trace_view.dot)[2]) / 2,
          (app.canvas.coords(app.trace_view.dot)[1] + app.canvas.coords(app.trace_view.dot)[3]) / 2)
assert abs(cy - ys[-1]) < 0.05

app.grip_button.invoke()
app.state.append_point((0, 0))
app.state.append_point((80, 0), flush=True)
app.state.active = False
app.state.break_trace()
kept = app.trace_view.grip_angle
app._observe_grip()
assert app.grip_calibrating and app.trace_view.grip_angle == kept

app.clear_grip()
app.draw_trace()
app.root.update_idletasks()
raw_ys = []
for item in app.canvas.find_withtag('trace_line'):
    raw_ys.extend(app.canvas.coords(item)[1::2])
assert max(raw_ys) - min(raw_ys) > 50
app.close()
print('PASS: grip angle comes from the horizontal chord, rotates the sum once, and levels the cursor.')
