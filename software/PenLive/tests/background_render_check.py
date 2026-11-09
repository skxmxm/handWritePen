"""Background paper: whole image stays on screen, and the cursor cannot leave it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from pen_live import PenApp
from trace_view import background_window_plan, centered_box, contain_size, window_origin

show_w, show_h, scale = contain_size(4000, 2000, 1800, 900)
assert (show_w, show_h) == (1800, 900) and scale == 0.45
show_w, show_h, scale = contain_size(120, 80, 900, 700)
assert (show_w, show_h) == (120, 80) and scale == 1
box, scale = centered_box(500, 400, 120, 80)
assert box == (190, 160, 310, 240) and scale == 1
plan = background_window_plan(80, 60, 40, 180, 1920, 1080, 720, 600)
assert plan['window'] == (720, 600) and plan['scale'] == 1
plan = background_window_plan(4000, 3000, 40, 180, 1920, 1080, 720, 600)
assert plan['window'][0] <= plan['max_window'][0] and plan['window'][1] <= plan['max_window'][1]
assert plan['scale'] < 1
assert plan['display'][0] <= 1920 - 16 - 40 and plan['display'][1] <= 1080 - 72 - 180
assert abs(plan['display'][0] / plan['display'][1] - 4 / 3) < 0.02
assert window_origin(1800, 900, 400, 300, 1920, 1080) == (1520, 780)
assert window_origin(-20, -10, 400, 300, 1920, 1080) == (0, 0)

def cursor_center(canvas, item):
    x0, y0, x1, y1 = canvas.coords(item)
    return (x0 + x1) / 2, (y0 + y1) / 2

def assert_inside(point, box, pad=4):
    x, y = point
    assert box[0] + pad - 0.2 <= x <= box[2] - pad + 0.2, (point, box)
    assert box[1] + pad - 0.2 <= y <= box[3] - pad + 0.2, (point, box)

app = PenApp(demo=False)
app.smoothing.set('关闭')
app.state.set_smoothing('关闭')
for timer in app.root.tk.call('after', 'info'):
    app.root.after_cancel(timer)
app.root.update()
screen_w, screen_h = app.root.winfo_screenwidth(), app.root.winfo_screenheight()
before = (app.root.winfo_width(), app.root.winfo_height())

small = Image.new('RGB', (120, 80), '#f6e7c1')
app.set_background_image(small, 'paper.png')
app.root.update()
assert app.background_text.get() == 'paper.png'
assert app.root.winfo_width() <= screen_w and app.root.winfo_height() <= screen_h
assert app.root.winfo_width() + 2 >= before[0] and app.root.winfo_height() + 2 >= before[1]
box = app.trace_view.background_box
assert (box[2] - box[0], box[3] - box[1]) == (120, 80)
assert any(app.canvas.type(item) == 'image' for item in app.canvas.find_withtag('background'))
s = app.state
s.boot = 1
s.cursor_valid = True
s.active = True
s.append_point((0, 0))
s.append_point((8000, -8000))
s.latest_xy = (8000, -8000)
app.draw_trace()
app.root.update_idletasks()
assert_inside(cursor_center(app.canvas, app.trace_view.dot), box)
for item in app.canvas.find_withtag('trace_line'):
    coords = app.canvas.coords(item)
    for x, y in zip(coords[0::2], coords[1::2]):
        assert_inside((x, y), box)
order = list(app.canvas.find_all())
image_item = next(item for item in app.canvas.find_withtag('background') if app.canvas.type(item) == 'image')
assert order.index(image_item) < order.index(app.canvas.find_withtag('trace_line')[0])

wide = Image.new('RGB', (min(screen_w - 1, before[0] + 280), 220), '#d5e4f7')
app.set_background_image(wide, 'wide.png')
app.root.update()
assert app.root.winfo_width() <= screen_w and app.root.winfo_height() <= screen_h
assert app.root.winfo_x() >= 0 and app.root.winfo_y() >= 0
assert app.root.winfo_x() + app.root.winfo_width() <= screen_w + 1
assert app.root.winfo_y() + app.root.winfo_height() <= screen_h + 1
box = app.trace_view.background_box
canvas_w, canvas_h = app.canvas.winfo_width(), app.canvas.winfo_height()
expect, fit_scale = centered_box(canvas_w, canvas_h, wide.width, wide.height)
assert box == expect
assert 0 <= box[0] and 0 <= box[1] and box[2] <= canvas_w and box[3] <= canvas_h
shown_w, shown_h = box[2] - box[0], box[3] - box[1]
assert abs(shown_w / shown_h - wide.width / wide.height) < 0.03
assert shown_w <= wide.width and shown_h <= wide.height
if wide.width > canvas_w or wide.height > canvas_h:
    assert canvas_w - shown_w <= 1 or canvas_h - shown_h <= 1
    assert fit_scale < 1

huge = Image.new('RGB', (screen_w + 480, screen_h + 320), '#e7eef6')
app.set_background_image(huge, 'huge.png')
app.root.update()
assert app.root.winfo_width() <= screen_w and app.root.winfo_height() <= screen_h
assert app.root.winfo_x() + app.root.winfo_width() <= screen_w + 1
assert app.root.winfo_y() + app.root.winfo_height() <= screen_h + 1
box = app.trace_view.background_box
canvas_w, canvas_h = app.canvas.winfo_width(), app.canvas.winfo_height()
expect, fit_scale = centered_box(canvas_w, canvas_h, huge.width, huge.height)
assert box == expect and fit_scale < 1
shown_w, shown_h = box[2] - box[0], box[3] - box[1]
assert abs(shown_w / shown_h - huge.width / huge.height) < 0.03
assert canvas_w - shown_w <= 1 or canvas_h - shown_h <= 1
s.latest_xy = (20000, 20000)
s.append_point((20000, 20000))
app.draw_trace()
assert_inside(cursor_center(app.canvas, app.trace_view.dot), box)

app.root.geometry('640x460+0+0')
app.root.update()
box = app.trace_view.background_box
canvas_w, canvas_h = app.canvas.winfo_width(), app.canvas.winfo_height()
expect, _scale = centered_box(canvas_w, canvas_h, huge.width, huge.height)
assert box == expect
assert box[2] <= canvas_w and box[3] <= canvas_h
assert (box[2] - box[0]) < huge.width and (box[3] - box[1]) < huge.height

app.clear_background()
app.root.update()
assert app.trace_view.background_box is None
assert not app.canvas.find_withtag('background')
assert app.background_text.get() == '未设置'
app.auto_fit.set(False)
s.clear_canvas()
s.cursor_valid = True
s.active = True
s.append_point((0, 0))
s.append_point((1000, 0))
s.latest_xy = (1000, 0)
app.draw_trace()
cx, _cy = cursor_center(app.canvas, app.trace_view.dot)
assert abs(cx - app.trace_view.project((1000, 0))[0]) < 0.2
assert cx > app.canvas.winfo_width()
app.close()
print('PASS: background fits the screen, keeps aspect, and clamps the cursor to the image.')
