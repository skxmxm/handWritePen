import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pen_protocol import (RAW_OFF, ADS, BAT, ACTIVE, EXC, GSR, USB, decode_body,
                          BleDecoder, StrokeState, gsr_display_valid)
from gsr_diagnostic import GsrDiagnostics
from test_protocol import wire, fragments


def sample(seq, active=False, stroke=0, **kw):
    t = seq * 100000
    args = dict(seq=seq, stroke=stroke, t_us=t, opt_us=t, imu_us=t, gsr_us=t,
                flags=RAW_OFF | ADS | BAT | (ACTIVE if active else 0),
                gs=6, vex=0, gsr=-1)
    args.update(kw)
    return decode_body(wire(**args), 3)


class RawOffTests(unittest.TestCase):
    def test_off_wire_contract_signed_values_and_all_fragment_sizes(self):
        raw = wire(flags=RAW_OFF | ADS | BAT, gs=6, vex=0, gsr=-1)
        self.assertIsNone(decode_body(raw, 2))
        for size in range(14, 177):
            d = BleDecoder()
            for i, f in enumerate(fragments(raw, size)):
                p = d.feed(f[:1]+b'\x03'+f[2:], 1+i*.001)
            self.assertTrue(p['raw_off'])
            self.assertFalse(p['excitation'])
            self.assertFalse(p['gsr_ok'])
            self.assertEqual(p['gsr_mv'], -.125)
            self.assertTrue(gsr_display_valid(p))

    def test_conflicting_mode_and_enable_flags_rejected(self):
        for flags, gs in [(RAW_OFF|ADS|EXC, 6), (RAW_OFF|GSR, 6),
                          (RAW_OFF|ADS, 0), (ADS, 6), (0x2000, 0)]:
            self.assertIsNone(decode_body(wire(flags=flags, gs=gs), 3))

    def test_continuous_across_down_release_and_new_stroke(self):
        s = StrokeState()
        for p in [sample(1), sample(2, True, 1), sample(3, False, 1),
                  sample(4, True, 2), sample(5, False, 2)]:
            self.assertTrue(s.accept(p, 1+p['seq']*.1))
        self.assertEqual(len(s.gsr_history), 5)
        self.assertFalse(s.active)
        self.assertTrue(gsr_display_valid(s.status))

    def test_adc_duplicates_errors_and_stale_samples(self):
        s = StrokeState(); s.accept(sample(1), 1)
        s.accept(sample(2, gsr_us=100000), 1.1)
        self.assertEqual(len(s.gsr_history), 1)
        p = sample(3, ae=1, flags=RAW_OFF|BAT)
        s.accept(p, 1.2)
        self.assertFalse(gsr_display_valid(p))
        self.assertIsNone(s.gsr_history[-1])
        s.accept(sample(4), 1.3)
        p = sample(10, gsr_us=400000)
        s.accept(p, 1.4)
        self.assertFalse(gsr_display_valid(p))
        self.assertIsNone(s.gsr_history[-1])
        s.accept(sample(11), 1.5)
        self.assertEqual(sum(p is None for p in s.gsr_history), 2)

    def test_missing_adc_interval_breaks_curve_even_if_ble_continues(self):
        s = StrokeState(); s.accept(sample(1), 1)
        s.accept(sample(7), 1.6)
        self.assertEqual(list(s.gsr_history), [(.1, -.125), None, (.7, -.125)])

    def test_timeout_raw_recovery_while_held_does_not_revive_ink(self):
        s = StrokeState(); s.accept(sample(1, True, 1), 1)
        s.expire(1.9)
        self.assertFalse(s.status)
        self.assertTrue(s.accept(sample(2, True, 1), 2))
        self.assertTrue(gsr_display_valid(s.status))
        self.assertTrue(s.gsr_history)
        self.assertFalse(s.active)
        self.assertFalse(s.points)
        s.accept(sample(3, False, 1), 2.1)
        s.accept(sample(4, True, 2), 2.2)
        self.assertTrue(s.active)
        self.assertEqual(len(s.gsr_history), 3)

    def test_clear_trace_preserves_raw_and_reboot_clears(self):
        s = StrokeState(); s.accept(sample(1), 1)
        s.clear_trace(); self.assertEqual(len(s.gsr_history), 1)
        s.accept(sample(2, boot=2), 1.1)
        self.assertEqual(len(s.gsr_history), 1)
        s.link_lost(); self.assertFalse(s.gsr_history)

    def test_usb_raw_still_readable_and_vex_warning_not_hidden(self):
        p = sample(1, flags=RAW_OFF|ADS|BAT|USB, vex=800)
        self.assertTrue(gsr_display_valid(p))
        diag = GsrDiagnostics()
        self.assertIn('超过 ±50 mV', diag.text(p))
        self.assertIn('取下指套', diag.text(p))
        self.assertIn('excitation_command=0', diag.report(p))
        self.assertNotIn('开启后 VEX 低于', diag.report(p))

    def test_cpp_off_wire_fixture(self):
        fixture = Path(__file__).parents[1]/'reports/cpp_raw_off.hex'
        p = decode_body(bytes.fromhex(fixture.read_text().strip()), 3)
        self.assertTrue(p['raw_off'])
        self.assertFalse(p['active'])
        self.assertTrue(gsr_display_valid(p))
        self.assertEqual(p['gsr_mv'], -.125)


if __name__ == '__main__':
    unittest.main()
