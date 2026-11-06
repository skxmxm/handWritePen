"""Opens the three real Tk windows; no BLE scan or hardware access."""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_live import PenApp
app=PenApp(demo=True)
app.root.update()
# Real demo state drives all three canvases and voltage labels.
now=time.monotonic();app.demo_start=now-1
app.demo_packet(now);app.demo_packet(now+.1)
app.draw_trace();app.draw_pose();app.draw_health();app.root.update()
assert app.state.active and app.state.points and app.state.angles
assert len(app.state.gsr_history)>=2
assert app.battery_text.get().endswith('V')
assert app.gsr_text.get()!='— mV'
assert any(app.pose_canvas.type(i)=='polygon' for i in app.pose_canvas.find_all())
assert any(app.canvas.type(i)=='oval' for i in app.canvas.find_all())
# Both pose and GSR persist through release in the v4 demo.
app.demo_packet(now+5)
app.draw_trace();app.draw_pose();app.draw_health();app.root.update()
assert not app.state.active and app.state.points and app.state.angles is not None
assert any(app.pose_canvas.type(i)=='polygon' for i in app.pose_canvas.find_all())
assert app.canvas.itemcget(app.trace_view.dot,'state')=='normal'
assert app.canvas.itemcget(app.trace_view.dot,'fill')==''
assert app.state.gsr_history
assert '皮肤电输出' in app.gsr_title.get()
assert app.gsr_text.get()!='— mV'
assert app.battery_text.get()!='— V'
# Retained fault diagnostics remain visible after release/current VEX returning to zero.
app.demo=False
legacy=dict(app.state.status,raw_off=False,gsr_state=0,vex_mv=0,excitation=False,gsr_ok=False,
            seq=app.state.seq+1,t_us=app.state.last_device_us+1000)
assert app.state.accept(legacy,time.monotonic())
app.diagnostics.observe_packet(app.state.status)
app.diagnostics.observe_fault(dict(boot=123456,stroke=1,reason=8,phase=2,
    sample_valid=True,adc_error=0,vex_mv=12.5,age_ms=2))
app.diagnostics.battery.observe(dict(boot=123456,stroke=1,before_valid=True,
    minimum_valid=True,complete=True,running=False,started=True,samples=6,
    before_v=4.02,minimum_v=3.74,before_age_ms=25))
app.draw_health();app.root.update()
assert 'E08' in app.diagnostic_text.get()
assert '12.500 mV' in app.diagnostic_text.get()
assert '3.740 V' in app.diagnostic_text.get()
app.copy_button.invoke();app.root.update_idletasks()
copied=app.root.clipboard_get()
assert '12.500 mV' in copied and 'VEX_now_mV=0' in copied
assert 'excitation_command=0' in copied
assert 'battery_sample_drop_mV=280.0' in copied
for widget in (app.diagnostic_label,app.copy_button,app.gsr_canvas):
    assert widget.winfo_ismapped()
    assert widget.winfo_rooty()+widget.winfo_height()<=app.health.winfo_rooty()+app.health.winfo_height()
assert app.gsr_canvas.winfo_height()>=50
# Loss of telemetry hides previous power values.
app.state.link_lost();app.draw_health()
assert app.battery_text.get()=='— V'
assert 'E08' in app.diagnostic_text.get() # clearly labelled historical record
app.disconnect();app.draw_health()
assert 'E08' not in app.diagnostic_text.get()
app.close()
print('PASS: three native Tk windows, pen-up retains ink/cursor, continuous GSR and pose, legacy diagnostic clipboard, battery and disconnect clearing.')
