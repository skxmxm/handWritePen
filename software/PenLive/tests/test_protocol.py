import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_protocol import (BleDecoder, BODY, crc16, decode_body, StrokeState,
                          rotation, apply, multiply, transpose, charger_text,
                          ACTIVE, OPT, IMU, ACC, GYRO, BAT, ADS, EXC, GSR, USB, CHARGE)

def wire(**kw):
    p=dict(boot=1,stroke=1,seq=1,t_us=100000,opt_us=99000,imu_us=90000,gsr_us=80000,
           x=10,y=-5,angles=(1000,2000,3000),accel=(0,0,1000),gyro=(0,0,0),battery=3930,
           gsr=1234,vex=4000,flags=ACTIVE|OPT|IMU|BAT|ADS|EXC|GSR,baud=9600,errors=0,
           gs=3,ae=0,s1=1,s2=1)
    p.update(kw)
    b=BODY.pack(*(p[k] for k in ('boot','stroke','seq','t_us','opt_us','imu_us','gsr_us','x','y')),
                *p['angles'],*p['accel'],*p['gyro'],*(p[k] for k in ('battery','gsr','vex','flags','baud','errors','gs','ae','s1','s2')))
    return b+crc16(b).to_bytes(2,'little')

def packet(**kw):
    d=decode_body(wire())
    d.update(kw)
    return d

def event(active=False,**kw):
    return packet(type='state',active=active,seq=2,**kw)

def fragments(data,chunk=14,message=0):
    count=(len(data)+chunk-1)//chunk
    return [b'\xa5\x02'+message.to_bytes(2,'little')+bytes((i,count))+data[i*chunk:(i+1)*chunk] for i in range(count)]

class ProtocolTests(unittest.TestCase):
    def test_cpp_wire_contract(self):
        fixture=Path(__file__).parents[1]/'reports/cpp_packet.hex'
        d=decode_body(bytes.fromhex(fixture.read_text().strip()))
        self.assertEqual(BODY.size,90)
        self.assertEqual((d['boot'],d['stroke'],d['seq']),(123,4,5))
        self.assertEqual((d['x'],d['y']),(-2048,2047))
        self.assertEqual(d['angles'],[-180,90,12.34])
        self.assertEqual(d['gyro'][2],-2000)
        self.assertEqual(d['battery_v'],3.912)
        self.assertEqual(d['gsr_mv'],154.25)
        self.assertTrue(d['gsr_ok'])

    def test_crc_reference(self):
        self.assertEqual(crc16(b'123456789'),0x29b1)

    def test_all_ble_fragment_sizes(self):
        for size in range(14,177):
            decoder=BleDecoder();result=None
            for i,b in enumerate(fragments(wire(),size)):
                result=decoder.feed(b,1+i*.01)
            self.assertEqual(result['x'],10)
            self.assertEqual(decoder.errors,0)

    def test_damaged_bytes_are_rejected(self):
        b=wire()
        for i in range(len(b)):
            damaged=bytearray(b);damaged[i]^=1
            self.assertIsNone(decode_body(damaged))
        self.assertIsNone(decode_body(b[:-1]))

    def test_out_of_order_missing_duplicate_and_timeout(self):
        f=fragments(wire())
        for order in [(0,2,3,4,5,6),(0,1,1,2,3,4,5,6),(6,5,4,3,2,1,0)]:
            d=BleDecoder()
            self.assertTrue(all(d.feed(f[i],1+n*.01) is None for n,i in enumerate(order)))
        d=BleDecoder();d.feed(f[0],1)
        self.assertIsNone(d.feed(f[1],1.6))
        self.assertTrue(d.errors)

    def test_release_can_replace_unfinished_data(self):
        d=BleDecoder();d.feed(fragments(wire(),14,65535)[0],1)
        end=wire(seq=2,flags=BAT|ADS,gs=0)
        result=None
        for i,f in enumerate(fragments(end,14,0)):
            result=d.feed(f,1+i*.01)
        self.assertFalse(result['active'])
        self.assertEqual(result['seq'],2)

    def test_validation_and_inconsistent_gsr(self):
        for args in [dict(gs=6),dict(ae=4),dict(s1=2),dict(angles=(18001,0,0)),
                     dict(opt_us=100001),dict(battery=5000),dict(flags=0x8000),
                     dict(flags=ACTIVE|ADS|EXC|GSR|USB),dict(flags=GSR),dict(gs=2)]:
            self.assertIsNone(decode_body(wire(**args)),args)
        d=decode_body(wire(flags=ADS|USB,gs=4))
        self.assertFalse(d['gsr_ok']);self.assertTrue(d['usb'])
        for b in (b'',b'123456',b'\xa5\x02\x00\x00\x00\x08x',b'\xa5\x02\x00\x00\x00\x01'+b'x'*93):
            self.assertIsNone(BleDecoder().feed(b))

    def test_release_clears_both_and_old_data_cannot_revive(self):
        s=StrokeState();s.accept(packet(),1.)
        self.assertTrue(s.points);self.assertIsNotNone(s.angles);self.assertTrue(s.gsr_history)
        s.accept(event(t_us=120000),1.1)
        self.assertFalse(s.active);self.assertFalse(s.points);self.assertIsNone(s.angles);self.assertFalse(s.gsr_history)
        self.assertFalse(s.accept(packet(seq=3,t_us=130000),1.2))
        self.assertFalse(s.points)
        s.accept(packet(stroke=2,seq=4,t_us=150000,imu_us=149000,x=0,y=0),1.3)
        self.assertEqual(list(s.points),[(0,0)])

    def test_idle_keeps_power_fresh(self):
        s=StrokeState();s.accept(event(battery_v=3.87),1)
        self.assertEqual(s.status['battery_v'],3.87)
        self.assertFalse(s.active)
        s.expire(1.9)
        self.assertFalse(s.status)

    def test_dropped_begin_end_and_reboot(self):
        s=StrokeState();s.accept(packet(),1.)
        s.accept(event(t_us=120000),1.2)
        self.assertFalse(s.active)
        s.accept(packet(boot=2,stroke=1,t_us=10,imu_us=9,opt_us=9,gsr_us=9),1.3)
        self.assertTrue(s.active);self.assertEqual(s.boot,2)

    def test_gap_marks_break_but_uses_absolute_counts(self):
        s=StrokeState();s.accept(packet(),1.)
        s.accept(packet(seq=3,t_us=150000,x=30,opt_errors=0),1.05)
        self.assertEqual(list(s.points),[(10,-5),None,(30,-5)])
        self.assertEqual(s.gaps,1)
        s.accept(packet(seq=4,t_us=160000,opt_ok=False),1.06)
        self.assertIsNone(s.points[-1])

    def test_unsigned_sequence_wrap_and_duplicate_reject(self):
        s=StrokeState();s.accept(packet(seq=0xffffffff),1)
        s.accept(packet(seq=0,t_us=110000),1.1)
        self.assertEqual(s.gaps,0)
        self.assertFalse(s.accept(packet(seq=0,t_us=110000),1.2))
        self.assertFalse(s.accept(packet(seq=0xfffffffe,t_us=120000),1.3))

    def test_stale_angle_is_hidden_and_repeated_timestamp_not_refreshed(self):
        s=StrokeState();s.accept(packet(),1.)
        s.accept(packet(seq=2,t_us=110000),1.2)
        s.expire(1.31);self.assertIsNone(s.angles)
        s.accept(packet(seq=3,t_us=1000000,imu_us=10000),1.4)
        self.assertIsNone(s.angles)

    def test_gsr_repeats_not_duplicated(self):
        s=StrokeState();s.accept(packet(),1.)
        s.accept(packet(seq=2,t_us=110000),1.1)
        self.assertEqual(len(s.gsr_history),1)
        s.accept(packet(seq=3,t_us=180000,gsr_us=170000),1.2)
        self.assertEqual(len(s.gsr_history),2)

    def test_timeout_clears_and_requires_new_stroke(self):
        s=StrokeState();s.accept(packet(),1.)
        s.expire(1.9)
        self.assertFalse(s.active);self.assertFalse(s.points)
        self.assertFalse(s.accept(packet(seq=2,t_us=200000),2.))
        s.accept(packet(stroke=2,seq=3,t_us=300000,imu_us=299000,opt_us=299000),2.1)
        self.assertTrue(s.active)

    def test_charger_does_not_claim_temperature(self):
        p=packet(usb=True,charging_enabled=True)
        self.assertEqual(charger_text(dict(p,stat1=1,stat2=0)),'充电中')
        self.assertIn('不能细分',charger_text(dict(p,stat1=0,stat2=1)))
        self.assertIn('待机',charger_text(dict(p,stat1=1,stat2=1)))
        self.assertIn('电池供电',charger_text(dict(p,usb=False)))

    def test_rotation_and_reference(self):
        v=apply(rotation(0,0,90),(1,0,0))
        self.assertAlmostEqual(v[0],0,places=6);self.assertAlmostEqual(v[1],1,places=6)
        v=apply(rotation(0,90,0),(1,0,0));self.assertAlmostEqual(v[2],-1,places=6)
        r=rotation(37,-25,133);identity=multiply(transpose(r),r)
        for i in range(3):
            for j in range(3):self.assertAlmostEqual(identity[i][j],int(i==j),places=6)

if __name__=='__main__':unittest.main()
