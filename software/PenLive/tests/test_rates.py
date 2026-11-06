import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trace_view import EventRate
from pen_protocol import StrokeState
from test_protocol import packet,event

class RateTests(unittest.TestCase):
    def test_packet_rate_uses_arrival_spacing_and_expires(self):
        r=EventRate()
        for i in range(101):r.add(1+i*.02)
        self.assertAlmostEqual(r.hz(3),50)
        self.assertEqual(r.hz(3.6),0)
        self.assertEqual(r.hz(6),0)

    def test_bursty_delivery_not_confused_with_ui_polling_rate(self):
        r=EventRate()
        # Three packets received in each 60 ms connection batch, UI polls independently.
        for i in range(30):
            for j in range(3):r.add(1+i*.06+j*.0001)
        self.assertGreater(r.hz(2.75),49)
        self.assertLess(r.hz(2.75),52)

    def test_point_serial_survives_ring_buffer_eviction_and_resets(self):
        from collections import deque
        s=StrokeState();s.points=deque(maxlen=3)
        for i in range(5):s.append_point((i,i))
        self.assertEqual(s.point_serial,5)
        self.assertEqual(list(s.points),[(2,2),(3,3),(4,4)])
        s.clear_canvas();self.assertEqual(s.point_serial,0)

    def test_arrival_timestamp_can_expire_a_delayed_dequeue(self):
        s=StrokeState();s.accept(packet(),1)
        s.expire(2)
        self.assertFalse(s.active)
        self.assertFalse(s.points)
        self.assertFalse(s.status)

if __name__=='__main__':unittest.main()
