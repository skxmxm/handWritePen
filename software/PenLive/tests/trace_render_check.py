"""Real Tk canvas checks for incremental drawing, retention, gaps and transforms."""
import math
import sys
import time
from collections import deque
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_live import PenApp
from pen_protocol import StrokeState

app=PenApp(demo=False)
app.smoothing.set("关闭");app.state.set_smoothing("关闭")
for timer in app.root.tk.call('after','info'):app.root.after_cancel(timer)
app.root.update()
s=app.state;s.boot=1;s.start(1)
app.auto_fit.set(False)
s.append_point((0,0));s.append_point((10,10));s.latest_xy=(10,10)
s.cursor_valid=True
app.draw_trace();app.root.update_idletasks()
lines=app.canvas.find_withtag('trace_line');assert len(lines)==1
first_id=lines[0];first_coords=app.canvas.coords(first_id)
assert first_coords[3]>first_coords[1], 'Y flip must remain enabled'
s.append_point((20,20));s.latest_xy=(20,20);app.draw_trace()
assert app.canvas.find_withtag('trace_line')==(first_id,), 'existing line must be extended, not destroyed'
assert len(app.canvas.coords(first_id))==6
app.draw_trace();assert app.canvas.find_withtag('trace_line')==(first_id,)
# A missing packet marker cannot be bridged by the incremental renderer.
s.append_point(None);s.append_point((40,40));s.append_point((50,50));app.draw_trace()
assert len(app.canvas.find_withtag('trace_line'))==2
# Reflection/viewport changes rebuild retained points with the correct transform.
app.flip_y.set(False);app.draw_trace()
coords=app.canvas.coords(app.canvas.find_withtag('trace_line')[0]);assert coords[3]<coords[1]
app.flip_y.set(True)
# Ring retention trims geometry and keeps item count bounded.
s.clear_canvas();s.start(2);s.points=deque(maxlen=257)
for i in range(800):
    s.append_point((i/10,30*math.sin(i/20)));s.latest_xy=s.points[-1]
    app.draw_trace()
chunks=app.trace_view.chunks
assert len(chunks)<=4
assert chunks[0]['first']==s.point_serial-len(s.points)+1
assert all(len(c['coords'])<=256 for c in chunks)
# Auto scaling stays fixed while incoming points fit, expands only at an edge.
s.clear_canvas();s.start(3);app.auto_fit.set(True)
s.append_point((0,0));app.draw_trace()
view=(app.trace_view.cx,app.trace_view.cy,app.trace_view.scale)
s.append_point((5,5));app.draw_trace()
assert view==(app.trace_view.cx,app.trace_view.cy,app.trace_view.scale)
s.append_point((1000,1000));app.draw_trace()
assert view!=(app.trace_view.cx,app.trace_view.cy,app.trace_view.scale)
x,y=app.trace_view.project((1000,-1000));assert 30<=x<=app.canvas.winfo_width()-30 and 30<=y<=app.canvas.winfo_height()-30
s.clear_canvas();app.draw_trace()
assert not app.canvas.find_withtag('trace_line')
assert app.canvas.itemcget(app.trace_view.dot,'state')=='hidden'
app.close()
print('PASS: incremental item reuse, default Y flip, gaps, ring trimming, scale hysteresis, release clearing.')
