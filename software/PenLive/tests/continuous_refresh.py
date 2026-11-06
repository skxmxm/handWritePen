"""Synthetic 200 Hz optical points in 50 Hz batches + 25 Hz telemetry through Tk."""
import sys,time,math,threading,json,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_live import PenApp
from pen_protocol import BleDecoder, crc16, ADS,EXC,GSR,IMU
from optical_protocol import OpticalDecoder
from test_protocol import wire,fragments
from test_continuous import batch,point,optical_wire,optical_fragments

app=PenApp(demo=False);app.auto_fit.set(False);app.optical_support=True
s=app.state;s.reset_boot(1);s.stroke=1;s.active=True;s.cursor_valid=True;s._origin=(0,0)
for i in range(18000):s.append_point((90*math.sin(i*.03),70*math.cos(i*.05)),i*5000)
s.latest_xy=s.points[-1]
app.root.update_idletasks();app.draw_trace();app.root.update_idletasks()
try:
    from AppKit import NSApplication
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
except ImportError:pass
stage_times={}
for name in ('draw_trace','draw_pose','draw_health','show_status'):
 original_method=getattr(app,name);measurements=[];stage_times[name]=measurements
 def timed(method=original_method,values=measurements):
  start=time.perf_counter();ret=method();values.append((time.perf_counter()-start)*1000);return ret
 setattr(app,name,timed)
original_idle=app.root.update_idletasks;stage_times['update_idletasks']=[]
def idle():
 start=time.perf_counter();ret=original_idle();stage_times['update_idletasks'].append((time.perf_counter()-start)*1000);return ret
app.root.update_idletasks=idle
stop=threading.Event();result={};latencies=[];max_queue=[0];produced=[0];accepted=[0]
original=s.accept_optical
def measured(b,arrived):
    latencies.append((time.monotonic()-arrived)*1000)
    max_queue[0]=max(max_queue[0],app.events.qsize())
    count=original(b,arrived);accepted[0]+=count;return count
s.accept_optical=measured

def producer():
    due=time.monotonic();batch_seq=0;total_bytes=0;op=OpticalDecoder();tele=BleDecoder()
    while not stop.is_set():
        now=time.monotonic()
        if now<due:stop.wait(due-now);continue
        points=[]
        for j in range(4):
            seq=batch_seq*4+j+1;t=90000000+seq*5000
            points.append(point(seq,round(90*math.sin(seq*.015)),round(70*math.cos(seq*.01)),t_us=t))
        raw=optical_wire(batch(*points,acquired=seq))
        for f in optical_fragments(raw,176,batch_seq%65536):
            total_bytes+=len(f);p=op.feed(f)
        p['_rx_at']=time.monotonic();p['_wire_bytes_total']=total_bytes
        app.events.put(('optical',p));produced[0]+=len(points)
        if batch_seq%2==0:
            raw=wire(seq=batch_seq+1,t_us=t,opt_us=t,imu_us=t,gsr_us=t//100000*100000,
                     flags=ADS|EXC|GSR|IMU,angles=(1000,2000,(batch_seq*10)%18000))
            for f in fragments(raw,176,batch_seq%65536):
                f=f[:1]+b'\x04'+f[2:];total_bytes+=len(f);p=tele.feed(f)
            p['_rx_at']=time.monotonic();p['_wire_bytes_total']=total_bytes
            app.events.put(('packet',p))
        batch_seq+=1;due+=.020

def measure():
    now=time.monotonic();a,r,b=app.stream_stats.rates(now)
    result.update(acquisition_counter_hz=round(a,2),received_points_per_s=round(r,2),
                  received_telemetry_per_s=round(app.rx_rate.hz(now),2),payload_bytes_per_s=round(b,2),
                  ui_ticks_per_s=round(app.ui_rate.hz(now),2),retained_points=len(s.points),
                  queue_wait_ms_p95=round(sorted(latencies)[int(len(latencies)*.95)],2),
                  queue_wait_ms_max=round(max(latencies),2),max_observed_queue=max_queue[0],
                  missing_sequence_gaps=s.gaps,host_stale_drops=app.stream_stats.host_drops)
    stop.set();app.root.after(150,finish)

def finish():
    result.update(produced=produced[0],accepted=accepted[0],remaining_queue=app.events.qsize())
    app.close()
worker=threading.Thread(target=producer,daemon=True)
app.root.after(500,worker.start)
app.root.after(5500,measure);app.root.mainloop();worker.join(timeout=1)
assert result['produced']==result['accepted'] and result['remaining_queue']==0
assert result['host_stale_drops']==0 and result['missing_sequence_gaps']==0
result['stage_mean_ms']={k:round(statistics.mean(v),3) for k,v in stage_times.items() if v}
result['scope']='Synthetic decoded 200 Hz optical / 25 Hz telemetry, foreground macOS Tk, 18000-point history, 500 ms window warm-up then 5 seconds. No physical BLE, sensor or display VSYNC measurement.'
(Path(__file__).resolve().parents[1]/'reports/continuous_refresh.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
