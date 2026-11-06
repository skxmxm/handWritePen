import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pen_protocol import StrokeState, BleDecoder, decode_body, TIP_EDGE, ACTIVE, OPT, BAT
from test_protocol import packet, wire, fragments


def sample(seq, x=0, y=0, active=False, stroke=0, **kw):
    t=seq*20000
    p=packet(v=3,seq=seq,t_us=t,opt_us=t,imu_us=t,gsr_us=t,
             x=x,y=y,active=active,stroke=stroke,tip_edge=False,
             imu_ok=active,gsr_ok=active)
    p.update(kw)
    return p


class PenUpTests(unittest.TestCase):
    def test_hover_updates_position_without_ink(self):
        s=StrokeState()
        s.accept(sample(1,100,200),1)
        s.accept(sample(2,130,180),1.02)
        self.assertEqual(s.latest_xy,(30,-20))
        self.assertTrue(s.cursor_valid)
        self.assertFalse(s.points)
        self.assertFalse(s.active)

    def test_two_strokes_keep_placement_without_hover_line(self):
        s=StrokeState()
        frames=[sample(1),sample(2,10,active=True,stroke=1,tip_edge=True),
                sample(3,20,active=True,stroke=1),sample(4,22,stroke=1,tip_edge=True),
                sample(5,80,stroke=1),sample(6,100,active=True,stroke=2,tip_edge=True),
                sample(7,110,active=True,stroke=2)]
        for p in frames:self.assertTrue(s.accept(p,1+p['seq']*.02))
        self.assertEqual(list(s.points),[(10,0),(20,0),(22,0),None,(100,0),(110,0)])
        self.assertEqual(s.latest_xy,(110,0))
        self.assertEqual(len(s.gsr_history),2)

    def test_release_preserves_ink_but_clears_pose_and_gsr(self):
        s=StrokeState();s.accept(sample(1,active=True,stroke=1),1)
        s.accept(sample(2,5,active=True,stroke=1),1.02)
        s.accept(sample(3,8,stroke=1,tip_edge=True),1.04)
        self.assertEqual(list(s.points),[(0,0),(5,0),(8,0),None])
        self.assertIsNone(s.angles)
        self.assertFalse(s.gsr_history)
        self.assertFalse(s.data)
        self.assertTrue(s.status)

    def test_missing_release_edge_cannot_draw_later_hover_motion(self):
        s=StrokeState();s.accept(sample(1,active=True,stroke=1),1)
        s.accept(sample(3,200,stroke=1),1.04)
        self.assertEqual(list(s.points),[(0,0),None])
        self.assertEqual(s.latest_xy,(200,0))
        self.assertEqual(s.gaps,1)

    def test_missing_both_edges_still_separates_strokes(self):
        s=StrokeState();s.accept(sample(1,active=True,stroke=1),1)
        s.accept(sample(4,300,active=True,stroke=2),1.06)
        self.assertEqual(list(s.points),[(0,0),None,(300,0)])

    def test_invalid_stale_and_error_samples_break_ink(self):
        s=StrokeState();s.accept(sample(1,active=True,stroke=1),1)
        s.accept(sample(2,100,active=True,stroke=1,opt_ok=False),1.02)
        self.assertFalse(s.cursor_valid)
        self.assertEqual(s.latest_xy,(0,0))
        s.accept(sample(3,110,active=True,stroke=1,opt_errors=1),1.04)
        self.assertEqual(list(s.points),[(0,0),None,(110,0)])
        s.accept(sample(10,500,active=True,stroke=1,opt_us=1,opt_errors=1),1.18)
        self.assertFalse(s.cursor_valid)
        self.assertEqual(s.latest_xy,(110,0))

    def test_clear_only_trace_rebases_cursor_and_preserves_acquisition(self):
        s=StrokeState();s.accept(sample(1,100,active=True,stroke=1),1)
        s.accept(sample(2,120,active=True,stroke=1),1.02)
        angles=s.angles;history=list(s.gsr_history);generation=s.trace_generation
        s.clear_trace()
        self.assertTrue(s.active)
        self.assertEqual(s.angles,angles)
        self.assertEqual(list(s.gsr_history),history)
        self.assertEqual(s.trace_generation,generation+1)
        self.assertEqual(list(s.points),[(0,0)])
        s.accept(sample(3,125,active=True,stroke=1),1.04)
        self.assertEqual(list(s.points),[(0,0),(5,0)])

    def test_clear_while_hovering_then_move_and_write(self):
        s=StrokeState();s.accept(sample(1,100),1)
        s.accept(sample(2,200),1.02);s.clear_trace()
        s.accept(sample(3,210),1.04)
        self.assertFalse(s.points)
        s.accept(sample(4,215,active=True,stroke=1),1.06)
        self.assertEqual(list(s.points),[(15,0)])

    def test_reboot_and_disconnect_reset_page_without_stale_revival(self):
        s=StrokeState();s.accept(sample(1,active=True,stroke=1),1)
        s.accept(sample(2,20,active=True,stroke=1),1.02)
        s.link_lost()
        self.assertFalse(s.points);self.assertFalse(s.cursor_valid)
        self.assertFalse(s.accept(sample(3,30,active=True,stroke=1),1.04))
        s.accept(sample(4,40,stroke=1),1.06)
        s.accept(sample(5,50,active=True,stroke=2),1.08)
        self.assertEqual(list(s.points),[(10,0)])
        s.accept(sample(1,100,boot=2),1.1)
        self.assertFalse(s.points);self.assertEqual(s.latest_xy,(0,0))

    def test_old_hover_packets_cannot_move_cursor_backwards(self):
        s=StrokeState();s.accept(sample(1),1);s.accept(sample(3,30),1.04)
        self.assertFalse(s.accept(sample(2,20),1.06))
        self.assertEqual(s.latest_xy,(30,0))

    def test_v3_wire_has_explicit_version_and_boundary_flag(self):
        raw=wire(flags=ACTIVE|OPT|BAT|TIP_EDGE,gs=0)
        self.assertIsNone(decode_body(raw,2))
        self.assertTrue(decode_body(raw,3)['tip_edge'])
        self.assertTrue(decode_body(raw,4)['tip_edge'])
        self.assertIsNone(decode_body(raw,5))
        for size in (14,40,176):
            decoder=BleDecoder();result=None
            for i,f in enumerate(fragments(raw,size)):
                result=decoder.feed(f[:1]+b'\x03'+f[2:],1+i*.01)
            self.assertEqual(result['v'],3)
            self.assertTrue(result['tip_edge'])

    def test_mixed_version_fragments_are_rejected(self):
        f=fragments(wire());d=BleDecoder()
        d.feed(f[0][:1]+b'\x03'+f[0][2:],1)
        self.assertIsNone(d.feed(f[1],1.01))
        self.assertEqual(d.errors,1)


if __name__=='__main__':unittest.main()
