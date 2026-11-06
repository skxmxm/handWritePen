import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from battery_diagnostic import BATTERY_PACKET, BatteryDiagnostics, decode_battery_diagnostic
from gsr_diagnostic import GsrDiagnostics
from pen_protocol import crc16
from test_protocol import packet
from test_diagnostic import fault

def fixture():
    return bytes.fromhex((Path(__file__).parents[1]/'reports/cpp_battery.hex').read_text())

def observation(**kw):
    p=decode_battery_diagnostic(fixture());p.update(kw);return p

class BatteryDiagnosticTests(unittest.TestCase):
    def test_cpp_wire_layout_and_small_mtu(self):
        self.assertEqual(BATTERY_PACKET.size,20)
        p=observation()
        self.assertEqual((p['boot'],p['stroke'],p['before_v'],p['minimum_v'],p['samples']),
                         (123,4,4.020,3.740,4))
        self.assertTrue(p['complete']);self.assertFalse(p['running'])
        self.assertTrue(p['before_valid']);self.assertEqual(p['before_age_ms'],30)

    def test_corrupt_and_inconsistent_packet_rejected(self):
        raw=fixture()
        for i in range(20):
            bad=bytearray(raw);bad[i]^=1
            self.assertIsNone(decode_battery_diagnostic(bad))
        self.assertIsNone(decode_battery_diagnostic(raw[:-1]))
        for index,value in [(0,0),(1,2),(4,255),(4,31),(4,0),(5,0),(8,101)]:
            fields=list(BATTERY_PACKET.unpack(raw));fields[index]=value
            body=BATTERY_PACKET.pack(*fields)[:18]
            self.assertIsNone(decode_battery_diagnostic(body+crc16(body).to_bytes(2,'little')))

    def test_pair_by_fault_boot_and_stroke_not_latest_voltage(self):
        g=GsrDiagnostics();g.observe_packet(packet(boot=123))
        g.battery.observe(observation());g.observe_fault(fault())
        g.battery.observe(observation(stroke=5,before_v=4.1,minimum_v=4.0))
        r=g.report(packet(boot=123,stroke=5,battery_v=4.2))
        self.assertIn('4.020 V',r);self.assertIn('3.740 V',r)
        self.assertIn('battery_sample_drop_mV=280.0',r)
        self.assertIn('power_stroke=4',r)
        self.assertNotIn('4.100 V',r)

    def test_late_read_cannot_undo_complete_window_or_minimum(self):
        b=BatteryDiagnostics();b.observe(observation())
        self.assertFalse(b.observe(observation(complete=False,running=True)))
        self.assertFalse(b.observe(observation(samples=3)))
        self.assertFalse(b.observe(observation(minimum_v=3.9)))
        self.assertFalse(b.observe(observation(stroke=3)))
        self.assertEqual(b.latest['minimum_v'],3.74)

    def test_reboot_disconnect_and_bounded_history(self):
        g=GsrDiagnostics();g.observe_packet(packet(boot=123))
        for stroke in range(12):g.battery.observe(observation(stroke=stroke))
        self.assertEqual(len(g.battery.records),8)
        self.assertIsNone(g.battery.select(fault(stroke=1)))
        g.observe_packet(packet(boot=124));self.assertFalse(g.battery.records)
        self.assertFalse(g.battery.observe(observation()))
        g.battery.observe(observation(boot=124));g.reset()
        self.assertIsNone(g.battery.latest)

    def test_missing_sample_not_presented_as_zero_voltage(self):
        b=BatteryDiagnostics()
        b.observe(observation(before_valid=False,before_v=0,minimum_valid=False,
                              samples=0,minimum_v=0,before_age_ms=65535))
        r=b.report()
        self.assertIn('未取得开前新采样',r)
        self.assertIn('尚无开启期间采样',r)
        self.assertNotIn('0.000 V',r);self.assertNotIn('battery_sample_drop_mV',r)

    def test_unsupported_error_and_unmatched_fault_are_explicit(self):
        b=BatteryDiagnostics();b.supported=False
        self.assertIn('当前固件未提供',b.text())
        b.observe(observation());self.assertIn('同次故障',b.text(fault(stroke=5)))
        b.error='电池诊断读取失败';self.assertIn('读取失败',b.text())
        b.observe(observation());self.assertEqual(b.error,'')

if __name__=='__main__':unittest.main()
