"""Simulated 50 Hz producer -> real event queue -> Tk. No radio access."""
import sys,time,math,threading,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_live import PenApp
from test_protocol import packet

app=PenApp(demo=False)
app.auto_fit.set(False)
s=app.state;s.boot=1;s.start(1)
for i in range(18000):s.append_point((90*math.sin(i*.03),70*math.cos(i*.05)))
s.latest_xy=s.points[-1];s.cursor_valid=True
# Measure an already visible, laid-out view; exclude initial window allocation.
app.root.update_idletasks()
app.draw_trace();app.root.update_idletasks()
try:
    from AppKit import NSApplication
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
except ImportError:
    pass
stop=threading.Event()
result={}
def producer():
    seq=0;started=time.monotonic();due=started
    while not stop.is_set():
        now=time.monotonic()
        if now<due:
            stop.wait(due-now);continue
        seq+=1;t=int((now-started+1)*1e6)
        p=packet(v=3,seq=seq,t_us=t,opt_us=t,imu_us=t,gsr_us=t//100000*100000,
                 x=round(90*math.sin(seq*.05)),y=round(70*math.cos(seq*.04)),
                 battery_ok=True,battery_v=3.94,gsr_ok=True,gsr_mv=150.,vex_mv=500.,
                 usb=False,charging_enabled=False,ads_ok=True,gsr_state=3,imu_baud=9600,_rx_at=now)
        app.events.put(('packet',p));due+=.02
    now=time.monotonic()
    app.events.put(('packet',dict(p,seq=seq+1,active=False,type='state',t_us=t+100000,_rx_at=now)))

def measure():
    now=time.monotonic()
    result.update(received_packets_per_s=round(app.rx_rate.hz(now),2),
                  ui_ticks_per_s=round(app.ui_rate.hz(now),2),retained_points=len(s.points))
    stop.set()
    app.root.after(300,finish)

def finish():
    result['release_retained_ink']=not app.state.active and bool(app.state.points) and bool(app.canvas.find_withtag('trace_line'))
    app.close()

worker=threading.Thread(target=producer,daemon=True);worker.start()
app.root.after(5000,measure);app.root.mainloop();worker.join(timeout=1)
assert result['release_retained_ink']
# Measurements are reported, not asserted against hardware-dependent timing thresholds.
result['scope']='synthetic 50Hz input, foreground native macOS Tk, 18000-point history, 5s run; no actual BLE / display VSYNC measurement'
report=Path(__file__).resolve().parents[1]/'reports/refresh_smoke.json'
report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
