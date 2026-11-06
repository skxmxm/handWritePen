"""v4 wire decoders -> dual stream state -> actual Tk canvases, no hardware."""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_live import PenApp
from optical_protocol import OpticalDecoder
from test_continuous import telemetry, batch, point, optical_wire, optical_fragments
from pen_protocol import USB,ADS,IMU
app=PenApp(demo=False)
for timer in app.root.tk.call('after','info'):app.root.after_cancel(timer)
app.root.update();app.auto_fit.set(False);decoder=OpticalDecoder()

def optics(*points):
    for i,f in enumerate(optical_fragments(optical_wire(batch(*points)),14,points[0]['seq'])):
        p=decoder.feed(f,1+i*.001)
    assert p is not None
    app.state.accept_optical(p,time.monotonic())
    app.draw_trace();app.draw_pose();app.draw_health();app.root.update_idletasks()

def health(p):
    assert app.state.accept(p,time.monotonic())
    app.diagnostics.observe_packet(p);app.draw_pose();app.draw_health();app.root.update_idletasks()

health(telemetry(1,flags=USB|ADS|IMU,gs=4))
assert all('按住笔尖' not in app.gsr_canvas.itemcget(i,'text') for i in app.gsr_canvas.find_all() if app.gsr_canvas.type(i)=='text')
app.state.reset_boot(1)
health(telemetry(1));optics(point(1),point(2,10),point(3,20))
raw=list(app.state.raw_records)
filtered=app.canvas.coords(app.canvas.find_withtag('trace_line')[0])
app.smoothing.set('关闭');app.change_smoothing()
assert list(app.state.raw_records)==raw
assert app.canvas.coords(app.canvas.find_withtag('trace_line')[0])!=filtered
optics(point(4,25,active=False,tip_edge=True))
coords=[app.canvas.coords(i) for i in app.canvas.find_withtag('trace_line')]
optics(point(5,100,active=False))
assert [app.canvas.coords(i) for i in app.canvas.find_withtag('trace_line')]==coords
assert any(app.pose_canvas.type(i)=='polygon' for i in app.pose_canvas.find_all())
assert app.gsr_text.get()!='— mV'
health(telemetry(2));assert len(app.state.gsr_history)==2
health(telemetry(3,flags=USB|ADS|IMU,gs=4))
assert app.gsr_text.get()=='— mV';assert 'USB' in app.gsr_state_text.get()
assert any(app.pose_canvas.type(i)=='polygon' for i in app.pose_canvas.find_all())
optics(point(6,105,stroke=2),point(7,110,stroke=2),point(10,120,stroke=2),point(11,125,stroke=2))
assert len(app.canvas.find_withtag('trace_line'))==3 # original + new stroke split by gap
health(telemetry(4));health(telemetry(5))
assert len(app.gsr_canvas.find_withtag('gsr_line'))==2
app.zero_pose();assert app.reference is not None
app.clear_trace();assert app.state.gsr_history and app.state.angles
assert '最近约 60 秒' in app.gsr_footer.get()
assert '旧固件' not in app.gsr_title.get()
app.close()
print('PASS: v4 decode/render, continuous GSR/pose, USB pause, hover without ink, gap separation, raw/filter switch and independent clear.')
