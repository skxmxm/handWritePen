import sys, unittest, math, random, statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_protocol import StrokeState, decode_body, crc16, ADS, EXC, GSR, IMU, USB, ACTIVE, gsr_display_valid
from optical_protocol import HEADER, RECORD, decode_optical, OpticalDecoder
from trace_filter import TraceFilter
from stream_stats import StreamStats
from test_protocol import wire

def telemetry(seq=1,active=False,**kw):
    t=seq*100000
    args=dict(seq=seq,t_us=t,imu_us=t,opt_us=t,gsr_us=t,
              flags=ADS|EXC|GSR|IMU|(ACTIVE if active else 0))
    args.update(kw)
    return decode_body(wire(**args),4)

def point(seq,x=0,y=0,active=True,stroke=1,**kw):
    p=dict(seq=seq,t_us=seq*5000,x=x,y=y,active=active,stroke=stroke,opt_ok=True,tip_edge=False)
    p.update(kw);return p

def batch(*points,boot=1,acquired=200,dropped=0):
    return dict(boot=boot,acquired=acquired,dropped=dropped,points=list(points))

def optical_wire(b):
    body=HEADER.pack(b['boot'],b['acquired'],b['dropped'],len(b['points']))
    for p in b['points']:
        flags=int(p['active'])|int(p['opt_ok'])*2|int(p['tip_edge'])*4
        body+=RECORD.pack(p['seq'],p['t_us'],p['x'],p['y'],p['stroke'],flags)
    return body+crc16(body).to_bytes(2,'little')

def optical_fragments(raw,chunk=176,message=0):
    count=math.ceil(len(raw)/chunk)
    return [b'\xa6\x01'+message.to_bytes(2,'little')+bytes((i,count))+raw[i*chunk:(i+1)*chunk] for i in range(count)]

class ContinuousTests(unittest.TestCase):
    def test_tip_up_gsr_and_pose_valid_v4_only(self):
        p=telemetry();self.assertTrue(gsr_display_valid(p))
        self.assertFalse(p['active']);self.assertTrue(p['excitation'])
        self.assertIsNone(decode_body(wire(flags=ADS|EXC|GSR|IMU),3))
        self.assertIsNone(telemetry(flags=ADS|EXC|GSR|USB))
        self.assertIsNone(telemetry(flags=ADS|GSR))

    def test_independent_streams_do_not_erase_gsr_pose_or_duplicate_ink(self):
        s=StrokeState();s.accept(telemetry(),1)
        s.accept_optical(batch(point(1),point(2,10)),1.01)
        s.accept_optical(batch(point(3,12,active=False,tip_edge=True)),1.02)
        self.assertEqual(list(s.points),[(0,0),(10,0),(12,0),None])
        self.assertTrue(s.gsr_history);self.assertIsNotNone(s.angles)
        before=list(s.points)
        s.accept(telemetry(2,True,x=10000,y=9999),1.1)
        self.assertEqual(list(s.points),before);self.assertFalse(s.active)
        s.accept_optical(batch(point(4,100,active=False),point(5,105,stroke=2)),1.12)
        self.assertEqual(s.points[-1],(105,0));self.assertEqual(len(s.gsr_history),2)

    def test_usb_pauses_gsr_but_not_pose_or_ink(self):
        s=StrokeState();s.accept(telemetry(),1)
        s.accept_optical(batch(point(1)),1)
        s.accept(telemetry(2,flags=USB|ADS|IMU,gs=4),1.1)
        self.assertFalse(gsr_display_valid(s.status));self.assertIsNone(s.gsr_history[-1])
        self.assertIsNotNone(s.angles);self.assertTrue(s.points)
        s.accept(telemetry(3),1.2)
        self.assertTrue(gsr_display_valid(s.status));self.assertEqual(len(s.gsr_history),3)

    def test_batched_edges_and_drops_do_not_join_strokes(self):
        s=StrokeState()
        s.accept_optical(batch(point(1),point(2,10),point(3,11,active=False,tip_edge=True),
                               point(4,100,active=False),point(5,101,stroke=2)),1)
        self.assertEqual(list(s.points),[(0,0),(10,0),(11,0),None,(101,0)])
        s.accept_optical(batch(point(9,150,stroke=3),dropped=3),1.02)
        self.assertEqual(list(s.points)[-2:],[None,(150,0)])
        self.assertEqual(s.queue_drops,3);self.assertEqual(s.gaps,1)
        s.accept_optical(batch(point(10,999,stroke=3,opt_ok=False)),1.03)
        self.assertFalse(s.cursor_valid);self.assertEqual(s.latest_xy,(150,0))

    def test_lost_release_edge_never_draws_hover_travel(self):
        s=StrokeState();s.accept_optical(batch(point(1)),1)
        s.accept_optical(batch(point(5,1000,active=False,tip_edge=True)),1.02)
        self.assertEqual(list(s.points),[(0,0),None]);self.assertEqual(s.latest_xy,(1000,0))

    def test_timeouts_are_independent_and_new_boot_optical_first(self):
        s=StrokeState();s.accept(telemetry(),1)
        s.accept_optical(batch(point(1)),1)
        s.accept(telemetry(2),1.3);s.expire(1.3)
        self.assertFalse(s.active);self.assertIsNotNone(s.angles);self.assertTrue(s.gsr_history)
        s.accept_optical(batch(point(2,10)),1.31)
        self.assertFalse(s.active)
        s.accept_optical(batch(point(3,20,active=False),point(4,30,stroke=2)),1.32)
        self.assertTrue(s.active)
        s.expire(2.2);self.assertFalse(s.status)
        s.accept(telemetry(3),2.21);self.assertIsNotNone(s.angles)
        s.accept_optical(batch(point(1),boot=2),3)
        s.expire(3.01);self.assertTrue(s.cursor_valid);self.assertTrue(s.points)

    def test_order_wrap_and_dual_stream_clock_separation(self):
        s=StrokeState();s.accept(telemetry(50),1)
        s.accept_optical(batch(point(0xffffffff,t_us=1),point(0,t_us=5001)),1.01)
        self.assertEqual(s.gaps,0);self.assertTrue(s.active)
        self.assertEqual(s.accept_optical(batch(point(0,t_us=5001)),1.02),0)
        self.assertEqual(s.accept_optical(batch(point(0xfffffffe,t_us=5002)),1.03),0)

    def test_clear_and_filter_switch_preserve_raw_data_and_sensors(self):
        s=StrokeState('轻度');s.accept(telemetry(),1)
        s.accept_optical(batch(point(1,100),point(2,110),point(3,120)),1.01)
        raw=list(s.raw_records)
        s.set_smoothing('关闭');self.assertEqual(list(s.points),[(0,0),(10,0),(20,0)])
        s.set_smoothing('标准');self.assertEqual(list(s.raw_records),raw)
        s.clear_trace();self.assertEqual(list(s.points),[(0,0)])
        self.assertTrue(s.gsr_history);self.assertIsNotNone(s.angles)

class OpticalWireTests(unittest.TestCase):
    def test_all_fragment_sizes_and_batch_lengths(self):
        for count in range(1,7):
            raw=optical_wire(batch(*(point(i,i*7) for i in range(count))))
            for size in range(14,177):
                d=OpticalDecoder()
                for i,f in enumerate(optical_fragments(raw,size)):
                    decoded=d.feed(f,1+i*.001)
                self.assertEqual(len(decoded['points']),count)
                self.assertEqual(d.errors,0)

    def test_corruption_flags_time_and_length_rejected(self):
        raw=optical_wire(batch(point(1),point(2)))
        for i in range(len(raw)):
            bad=bytearray(raw);bad[i]^=1;self.assertIsNone(decode_optical(bad))
        self.assertIsNone(decode_optical(raw[:-1]))
        self.assertIsNone(decode_optical(optical_wire(batch())))
        self.assertIsNone(decode_optical(optical_wire(batch(point(2),point(1)))))
        self.assertIsNone(decode_optical(optical_wire(batch(point(1),point(1)))))
        self.assertIsNone(decode_optical(optical_wire(batch(point(1,t_us=20),point(2,t_us=10)))))

    def test_partial_missing_duplicate_and_timeout(self):
        fs=optical_fragments(optical_wire(batch(*(point(i) for i in range(6)))),14)
        for order in ([0,2,3,4,5,6,7,8,9,10,11],[0,1,1,2,3,4,5,6,7,8,9,10,11],list(reversed(range(12)))):
            d=OpticalDecoder()
            self.assertTrue(all(d.feed(fs[i],1+n*.001) is None for n,i in enumerate(order)))
        d=OpticalDecoder();d.feed(fs[0],1);self.assertIsNone(d.feed(fs[1],1.6))
        for i,f in enumerate(fs):p=d.feed(f,2+i*.001)
        self.assertEqual(len(p['points']),6)

    def test_cpp_wire(self):
        raw=bytes.fromhex((Path(__file__).parents[1]/'reports/cpp_optical.hex').read_text())
        p=decode_optical(raw)
        self.assertEqual((p['boot'],p['acquired'],p['dropped']),(123,200,2))
        self.assertEqual([v['seq'] for v in p['points']],[0xffffffff,0,1])
        self.assertEqual(p['points'][0]['x'],-2048)
        self.assertEqual(p['points'][2]['t_us'],(1<<40)+10000)
        self.assertTrue(p['points'][2]['tip_edge']);self.assertFalse(p['points'][2]['active'])

class FilterTests(unittest.TestCase):
    def test_stationary_jitter_reduced_and_raw_mode_exact(self):
        rng=random.Random(26);points=[(rng.gauss(0,1),rng.gauss(0,1)) for _ in range(1000)]
        raw_rms=math.sqrt(statistics.mean(x*x+y*y for x,y in points[100:]))
        f=TraceFilter('轻度');out=[f.apply(p,i*5000) for i,p in enumerate(points)]
        rms=math.sqrt(statistics.mean(x*x+y*y for x,y in out[100:]))
        self.assertLess(rms,raw_rms*.55)
        f=TraceFilter('关闭')
        self.assertEqual([f.apply(p,i*5000) for i,p in enumerate(points)],points)

    def test_fast_motion_lag_bound_and_exact_release_endpoint(self):
        f=TraceFilter('轻度');lags=[]
        for i in range(300):
            x=i*5;out=f.apply((x,0),i*5000)
            if i>100:lags.append(x-out[0])
        self.assertLess(max(lags),7) # <7ms at 1000 counts/s, synthetic constant speed.
        self.assertEqual(f.apply((1500,0),1500000,flush=True),(1500,0))
        f.apply(None,1505000);self.assertEqual(f.apply((5000,5000),1510000),(5000,5000))

    def test_corner_does_not_overshoot_or_cross_large_gap(self):
        f=TraceFilter('轻度')
        for i in range(100):f.apply((i,0),i*5000)
        for i in range(100,200):
            x,y=f.apply((99,i-100),i*5000)
            self.assertTrue(-1e-10<=x<=99+1e-10 and -1e-10<=y<=i-100+1e-10)
        self.assertEqual(f.apply((999,999),2000000),(999,999))

class StatsTests(unittest.TestCase):
    def test_rates_use_counts_not_packet_or_ui_rate(self):
        s=StreamStats()
        for i in range(101):
            b=batch(*(point(i*4+j) for j in range(4)),acquired=i*4)
            b['_wire_bytes_total']=i*120
            s.optical(b,1+i*.02)
        acquisition,arrival,throughput=s.rates(3)
        self.assertAlmostEqual(acquisition,200);self.assertAlmostEqual(arrival,200)
        self.assertAlmostEqual(throughput,6000)
        self.assertEqual(s.rates(4),(0,0,0))

if __name__=='__main__':unittest.main()
