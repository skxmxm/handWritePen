"""Real Tk + decoded v3 BLE packets: retained strokes and ink-free hover travel."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_live import PenApp
from pen_protocol import BleDecoder, ACTIVE, OPT, BAT, TIP_EDGE
from test_protocol import wire, fragments

app=PenApp(demo=False)
app.smoothing.set("关闭");app.state.set_smoothing("关闭")
for timer in app.root.tk.call('after','info'):app.root.after_cancel(timer)
app.root.update();app.auto_fit.set(False)
decoder=BleDecoder();seq=0

def send(x,y=0,down=False,stroke=0,edge=False):
    global seq
    seq+=1;t=seq*20000
    raw=wire(seq=seq,stroke=stroke,t_us=t,opt_us=t,imu_us=0,gsr_us=0,x=x,y=y,
             flags=OPT|BAT|(ACTIVE if down else 0)|(TIP_EDGE if edge else 0),gs=0)
    p=None
    for i,f in enumerate(fragments(raw,14,seq)):
        p=decoder.feed(f[:1]+b'\x03'+f[2:],1+seq*.1+i*.001)
    assert p is not None and app.state.accept(p,1+seq*.1)
    app.draw_trace();app.draw_pose();app.root.update_idletasks()

send(100)
send(110,down=True,stroke=1,edge=True)
send(130,10,True,1)
send(135,10,False,1,True)
lines=app.canvas.find_withtag('trace_line');assert len(lines)==1
first=lines[0];coords=app.canvas.coords(first)
cursor_before=app.canvas.coords(app.trace_view.dot)
send(200,40,False,1)
assert app.canvas.find_withtag('trace_line')==(first,)
assert app.canvas.coords(first)==coords
assert app.canvas.coords(app.trace_view.dot)!=cursor_before
assert app.canvas.itemcget(app.trace_view.dot,'fill')==''
send(200,40,True,2,True)
send(220,60,True,2)
send(220,60,False,2,True)
lines=app.canvas.find_withtag('trace_line');assert len(lines)==2
assert app.canvas.coords(first)==coords
second=app.canvas.coords(lines[1])
# Second stroke starts at the moved-to point; no connecting segment from first stroke.
assert second[:2]==list(app.trace_view.project((100,-40)))
assert second[2:]==list(app.trace_view.project((120,-60)))
assert app.state.angles is None and not app.state.gsr_history
assert '抬笔' in app.acquisition_status()
# A brief point without movement remains ink when the cursor moves away.
send(240,60,True,3,True);send(240,60,False,3,True)
assert len(app.canvas.find_withtag('trace_dot'))==1
send(270,60,False,3)
assert len(app.canvas.find_withtag('trace_dot'))==1
# Orientation controls affect hover cursor and ink together.
app.flip_y.set(False);app.swap_xy.set(True);app.draw_trace()
cx,cy=app.trace_view.project((60,170))
assert app.canvas.coords(app.trace_view.dot)==[cx-4,cy-4,cx+4,cy+4]
# The actual user button clears only the page and rebases at current cursor.
app.clear_trace_button.invoke();app.root.update_idletasks()
assert not app.canvas.find_withtag('trace_line')
assert not app.canvas.find_withtag('trace_dot')
assert app.state.latest_xy==(0,0) and app.state.cursor_valid
send(280,60,False,3)
assert not app.canvas.find_withtag('trace_line')
send(280,60,True,4,True);send(290,60,True,4)
assert list(app.state.points)==[(10,0),(20,0)]
app.state.link_lost();app.draw_trace()
assert not app.canvas.find_withtag('trace_line')
assert app.canvas.itemcget(app.trace_view.dot,'state')=='hidden'
app.close()
print('PASS: v3 BLE decode to real Tk, pen-up cursor without ink, retained multi-strokes, boundary endpoints, single-dot ink, transforms, clear button, disconnect.')
