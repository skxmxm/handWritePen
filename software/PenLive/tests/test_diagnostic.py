import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gsr_diagnostic import PACKET, GsrDiagnostics, decode_diagnostic
from pen_protocol import crc16
from test_protocol import packet

def fixture():
    return bytes.fromhex((Path(__file__).parents[1]/'reports/cpp_diagnostic.hex').read_text())

def fault(**kw):
    p=decode_diagnostic(fixture());p.update(kw);return p

class DiagnosticTests(unittest.TestCase):
    def test_cpp_fault_fixture_fits_small_mtu(self):
        self.assertEqual(PACKET.size,20)
        p=decode_diagnostic(fixture())
        self.assertEqual(p,dict(boot=123,stroke=4,reason=8,phase=2,sample_valid=True,
                               adc_error=0,vex_mv=1.,age_ms=2))

    def test_corruption_length_and_invalid_fields(self):
        raw=fixture()
        for i in range(len(raw)):
            damaged=bytearray(raw);damaged[i]^=1
            self.assertIsNone(decode_diagnostic(damaged))
        self.assertIsNone(decode_diagnostic(raw[:-1]))
        self.assertIsNone(decode_diagnostic(raw+b'x'))
        for index,value in ((0,0),(1,2),(4,10),(5,0),(6,2),(7,4)):
            fields=list(PACKET.unpack(raw));fields[index]=value
            bad=PACKET.pack(*fields)[:18];bad+=crc16(bad).to_bytes(2,'little')
            self.assertIsNone(decode_diagnostic(bad))

    def test_original_voltage_retained_after_shutdown_release_and_new_attempt(self):
        g=GsrDiagnostics();g.observe_packet(packet(boot=123,stroke=4))
        g.observe_fault(fault(vex_mv=42))
        current=packet(boot=123,stroke=4,active=False,excitation=False,gsr_state=0,vex_mv=0)
        g.observe_packet(current)
        text=g.text(current)
        self.assertIn('42.000 mV',text)
        self.assertIn('E08',text)
        g.observe_fault(fault(stroke=5,reason=0,phase=0,sample_valid=False))
        self.assertEqual(g.last_fault['stroke'],4)
        self.assertIn('VEX_now_mV=0',g.report(current))
        self.assertIn('fault_ADC_error=0',g.report(current))

    def test_reset_and_reboot_clear_previous_fault(self):
        g=GsrDiagnostics();g.observe_fault(fault()) # diagnostic may arrive before main packet
        g.observe_packet(packet(boot=124))
        self.assertIsNone(g.last_fault)
        self.assertFalse(g.observe_fault(fault()))
        g.observe_fault(fault(boot=124));self.assertIsNotNone(g.last_fault)
        g.reset();self.assertIsNone(g.last_fault);self.assertIsNone(g.supported)

    def test_stale_read_cannot_replace_newer_notification(self):
        g=GsrDiagnostics();g.observe_fault(fault(stroke=6,reason=9))
        self.assertFalse(g.observe_fault(fault(stroke=4)))
        self.assertEqual(g.last_fault['reason'],9)
        g.reset();g.observe_fault(fault(stroke=0xffffffff))
        self.assertTrue(g.observe_fault(fault(stroke=0)))

    def test_invalid_adc_data_is_not_shown_as_fault_voltage(self):
        g=GsrDiagnostics();g.observe_fault(fault(reason=1,adc_error=1,sample_valid=False,vex_mv=555))
        self.assertIn('无有效采样',g.text({}))
        self.assertNotIn('555.000',g.text({}))

    def test_old_firmware_and_transport_failure_are_explicit(self):
        g=GsrDiagnostics();g.supported=False
        self.assertIn('需烧录',g.text({}))
        g.supported=True;g.transport_error='读取失败'
        self.assertIn('读取失败',g.text(dict(gsr_state=5)))
        g.observe_fault(fault());self.assertEqual(g.transport_error,'')

if __name__=='__main__':unittest.main()
