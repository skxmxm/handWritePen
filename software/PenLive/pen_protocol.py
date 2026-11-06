"""R26 BLE v2/v3/v4; v4 separates timestamped optical batches and telemetry."""
import math
import struct
import time
from collections import deque
from trace_filter import TraceFilter, MODES

SERVICE_UUID = '7c7b9001-8e77-4b62-9c3d-4d5d83f4a001'
NOTIFY_UUID = '7c7b9002-8e77-4b62-9c3d-4d5d83f4a001'
CONTROL_UUID = '7c7b9003-8e77-4b62-9c3d-4d5d83f4a001'
BODY = struct.Struct('<IIIQQQQii3h3h3hHhhHIIBBBB')
ACTIVE, OPT, IMU, ACC, GYRO, BAT, ADS, EXC, GSR, USB, CHARGE = [1 << i for i in range(11)]
TIP_EDGE = 1 << 11
RAW_OFF = 1 << 12

def adc_fresh(p):
    return bool(p.get('ads_ok') and not p.get('ads_error')
                and 0 <= p.get('t_us', 0)-p.get('gsr_us', -1000000) <= 500000)

def gsr_display_valid(p):
    if p.get('raw_off'):
        return adc_fresh(p) and not p.get('excitation') and p.get('gsr_state') == 6
    return bool((p.get('v',2)>=4 or p.get('active')) and p.get('gsr_ok') and adc_fresh(p))

def crc16(data):
    crc = 0xffff
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    return crc

def decode_body(raw, version=2):
    if version not in (2, 3, 4):
        return None
    if len(raw) != BODY.size + 2 or crc16(raw[:-2]) != int.from_bytes(raw[-2:], 'little'):
        return None
    v = BODY.unpack(raw[:-2])
    boot, stroke, seq, t, opt_t, imu_t, gsr_t, x, y = v[:9]
    angles, accel, gyro = v[9:12], v[12:15], v[15:18]
    bat, gsr, vex, flags, baud, errors, gs, ae, s1, s2 = v[18:]
    if (flags & ~(0x1fff if version >= 3 else 0x7ff) or gs > 6 or ae > 3 or s1 > 1 or s2 > 1
            or max(opt_t, imu_t, gsr_t) > t or any(abs(a) > 18000 for a in angles)
            or (flags & BAT and not 2400 <= bat <= 4400)):
        return None
    if bool(flags & RAW_OFF) != (gs == 6) or (flags & RAW_OFF and flags & (EXC | GSR)):
        return None
    required=ADS|EXC|(ACTIVE if version<4 else 0)
    if flags & GSR and (flags & required != required
                       or flags & USB or gs != 3 or ae):
        return None
    return dict(v=version, type='data' if flags & ACTIVE else 'state', active=bool(flags & ACTIVE),
                tip_edge=bool(flags & TIP_EDGE), raw_off=bool(flags & RAW_OFF),
                boot=boot, stroke=stroke, seq=seq, t_us=t, opt_us=opt_t, imu_us=imu_t, gsr_us=gsr_t,
                x=x, y=y, angles=[a/100 for a in angles], accel=[a/1000 for a in accel],
                gyro=[a/10 for a in gyro], opt_ok=bool(flags & OPT), imu_ok=bool(flags & IMU),
                acc_ok=bool(flags & ACC), gyro_ok=bool(flags & GYRO), battery_ok=bool(flags & BAT),
                battery_v=bat/1000, ads_ok=bool(flags & ADS), gsr_mv=gsr*.125, vex_mv=vex*.125,
                excitation=bool(flags & EXC), gsr_ok=bool(flags & GSR), usb=bool(flags & USB),
                charging_enabled=bool(flags & CHARGE), imu_baud=baud, opt_errors=errors,
                gsr_state=gs, ads_error=ae, stat1=s1, stat2=s2)

class BleDecoder:
    """Discard partial/out-of-order frames; never join fragments across messages."""
    def __init__(self):
        self.reset()
        self.errors = 0

    def reset(self):
        self.message = None
        self.version = None
        self.next_index = 0
        self.count = 0
        self.buffer = bytearray()
        self.started = 0

    def feed(self, fragment, now=None):
        now = time.monotonic() if now is None else now
        b = bytes(fragment)
        if len(b) < 7 or b[0] != 0xa5 or b[1] not in (2, 3, 4):
            self.errors += 1
            self.reset()
            return None
        message, index, count = int.from_bytes(b[2:4], 'little'), b[4], b[5]
        if not 1 <= count <= 7 or index >= count:
            self.errors += 1
            self.reset()
            return None
        if index == 0:
            self.reset()
            self.message, self.count, self.started, self.version = message, count, now, b[1]
        if (message != self.message or b[1] != self.version or index != self.next_index or count != self.count
                or now-self.started > .5):
            self.errors += 1
            self.reset()
            return None
        self.buffer.extend(b[6:])
        self.next_index += 1
        if len(self.buffer) > BODY.size+2:
            self.errors += 1
            self.reset()
            return None
        if self.next_index == count:
            result = decode_body(bytes(self.buffer), self.version)
            if result is None:
                self.errors += 1
            self.reset()
            return result
        return None

def charger_text(p):
    if not p.get('usb'):
        return '电池供电（USB 未接入）'
    if not p.get('charging_enabled'):
        return 'USB 已接入，软件未允许充电'
    state = p.get('stat1'), p.get('stat2')
    return {(1, 0): '充电中', (1, 1): '充电完成 / 待机 / 被禁止（状态脚无法细分）',
            (0, 1): '可恢复故障（温度、电压等多种原因，不能细分）',
            (0, 0): '锁存故障，检查电源与充电电路'}.get(state, '状态未知')

def rotation(roll, pitch, yaw):
    """Right-handed ZYX Euler: Rz(yaw) Ry(pitch) Rx(roll), degrees."""
    r, p, y = map(math.radians, (roll, pitch, yaw))
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return ((cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr),
            (sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr), (-sp, cp*sr, cp*cr))

def transpose(a):
    return tuple(zip(*a))

def multiply(a, b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)) for i in range(3))

def apply(a, v):
    return tuple(sum(a[i][j]*v[j] for j in range(3)) for i in range(3))

class StrokeState:
    def __init__(self,smoothing='关闭'):
        self.boot = None
        self.stroke = -1
        self.last_device_us = -1
        self.last_rx = 0.0
        self.seq = None
        self.closed = False
        self.active = False
        self.points = deque(maxlen=20000)
        self.raw_records = deque(maxlen=20000)
        self.filter = TraceFilter(smoothing)
        self.opt_seq = None
        self.opt_device_us = -1
        self.opt_rx = 0.
        self.queue_drops = 0
        self.point_serial = 0
        self.trace_generation = 0
        self.cursor_valid = False
        self._origin = None
        self._raw_xy = None
        self.angles = None
        self.pose_rx = 0.0
        self.pose_device_us = -1
        self.status = {}
        self.gaps = 0
        self.opt_errors = 0
        self.latest_xy = (0, 0)
        self.data = {}
        self.gsr_history = deque(maxlen=600)
        self.gsr_device_us = -1

    def clear_canvas(self):
        self.active = False
        self.points.clear()
        self.raw_records.clear()
        self.filter.reset()
        self.opt_seq=None;self.opt_device_us=-1;self.opt_rx=0.
        self.point_serial = 0
        self.trace_generation += 1
        self.cursor_valid = False
        self._origin = self._raw_xy = None
        self.angles = None
        self.pose_device_us = -1
        self.data = {}
        self.latest_xy = (0, 0)
        self.gsr_history.clear()
        self.gsr_device_us = -1

    def clear_trace(self):
        """New paper at the current position; leave acquisition and diagnostics alone."""
        self.points.clear()
        self.raw_records.clear()
        self.filter.reset()
        self.point_serial = 0
        self.trace_generation += 1
        self._origin = self._raw_xy if self.cursor_valid else None
        if self.status.get('v', 2) >= 3:
            self.latest_xy = (0, 0)
        if self.active and self.cursor_valid:
            self.append_point(self.latest_xy,self.opt_device_us if self.status.get("v",2)>=4 else self.last_device_us)

    def break_trace(self):
        if self.points and self.points[-1] is not None:
            self.append_point(None)

    def append_point(self, point, t_us=None, flush=False):
        stamp=self.last_device_us if t_us is None else t_us
        self.raw_records.append((point,stamp,flush))
        self.points.append(self.filter.apply(point,stamp,flush))
        self.point_serial += 1

    def set_smoothing(self,mode):
        if mode not in MODES:raise ValueError(mode)
        self.filter=TraceFilter(mode)
        self.points.clear()
        for point,stamp,flush in self.raw_records:
            self.points.append(self.filter.apply(point,stamp,flush))
        self.trace_generation+=1

    def link_lost(self):
        self.clear_canvas()
        self.status = {}
        self.closed = True
        self.last_rx = 0.

    def start(self, stroke):
        self.clear_canvas()
        self.stroke = stroke
        self.closed = False
        self.active = True
        self.seq = None
        self.gaps = 0
        self.opt_errors = 0

    def accept(self, p, now=None):
        now = time.monotonic() if now is None else now
        if p.get('v',2)>=4:
            return self.accept_telemetry(p,now)
        if self.boot != p['boot']:
            self.clear_canvas()
            self.boot, self.stroke, self.last_device_us = p['boot'], -1, -1
            self.seq = None
            self.closed = False
        if p['t_us'] < self.last_device_us or p['stroke'] < self.stroke:
            return False
        if ((p.get('v', 2) >= 3 or p['stroke'] == self.stroke) and self.seq is not None
                and not 0 < ((p['seq']-self.seq) & 0xffffffff) < 0x80000000):
            return False
        if self.closed and p['active'] and p['stroke'] == self.stroke:
            if not p.get('raw_off'):
                return False
            # Resume raw telemetry after a timeout without reviving an old ink stroke.
            self.last_rx, self.last_device_us = now, p['t_us']
            self.status, self.seq = p, p['seq']
            self.observe_raw(p)
            return True
        self.last_rx = now
        self.last_device_us = p['t_us']
        if bool(self.status.get('raw_off')) != bool(p.get('raw_off')):
            self.gsr_history.clear()
            self.gsr_device_us = -1
        self.status = p  # Battery and supply state are refreshed even while pen is up.
        if p.get('v', 2) >= 3:
            return self._accept_continuous(p, now)
        if not p['active']:
            self.stroke, self.seq = p['stroke'], p['seq']
            self.clear_canvas()
            self.closed = True
            return True
        if self.closed and p['stroke'] == self.stroke:
            return False
        if p['stroke'] != self.stroke:
            self.start(p['stroke'])
        self.active = True
        gap = ((self.seq is not None and (p['seq']-self.seq) & 0xffffffff != 1)
               or p['opt_errors'] != self.opt_errors)
        self.seq, self.opt_errors = p['seq'], p['opt_errors']
        self.data = p
        self.latest_xy = p['x'], p['y']
        self._raw_xy = self.latest_xy
        self.cursor_valid = bool(p['opt_ok'] and 0 <= p['t_us']-p['opt_us'] <= 100000)
        if gap:
            self.gaps += 1
            self.append_point(None)
        if p['opt_ok'] and 0 <= p['t_us']-p['opt_us'] <= 100000:
            if not self.points or self.points[-1] != self.latest_xy:
                self.append_point(self.latest_xy)
        elif not self.points or self.points[-1] is not None:
            self.append_point(None)
        if p['imu_ok'] and 0 <= p['t_us']-p['imu_us'] <= 250000:
            self.angles = tuple(p['angles'])
            if self.pose_device_us != p['imu_us']:
                self.pose_rx, self.pose_device_us = now, p['imu_us']
        else:
            self.angles = None
        if p.get('gsr_ok') and 0 <= p['t_us']-p['gsr_us'] <= 500000:
            if self.gsr_device_us != p['gsr_us']:
                self.gsr_history.append((p['gsr_us']/1e6, p['gsr_mv']))
                self.gsr_device_us = p['gsr_us']
        return True

    def _accept_continuous(self, p, now):
        new_stroke = p['stroke'] != self.stroke
        was_active = self.active
        gap = ((self.seq is not None and (p['seq']-self.seq) & 0xffffffff != 1)
               or p['opt_errors'] != self.opt_errors)
        valid = bool(p['opt_ok'] and 0 <= p['t_us']-p['opt_us'] <= 100000)
        if new_stroke or gap or not valid or not self.cursor_valid:
            self.break_trace()
        if gap:
            self.gaps += 1
        self.stroke, self.seq, self.opt_errors = p['stroke'], p['seq'], p['opt_errors']
        if valid:
            self._raw_xy = p['x'], p['y']
            if self._origin is None:
                self._origin = self._raw_xy
            self.latest_xy = tuple(a-b for a,b in zip(self._raw_xy, self._origin))
        self.cursor_valid = valid
        # Only an explicit release-boundary snapshot can finish the last ink segment.
        # A later idle snapshot might already include pen-up travel.
        release_edge = (was_active and not new_stroke and not p['active']
                        and p.get('tip_edge', False) and not gap)
        if valid and (p['active'] or release_edge):
            if not self.points or self.points[-1] != self.latest_xy:
                self.append_point(self.latest_xy)
        self.active = bool(p['active'])
        self.closed = not self.active
        self.data = p if self.active else {}
        if new_stroke or not self.active:
            self.angles = None
            self.pose_device_us = -1
            if not p.get('raw_off'):
                self.gsr_history.clear()
                self.gsr_device_us = -1
        if p.get('raw_off'):
            self.observe_raw(p)
        if not self.active:
            self.break_trace()
            return True
        if p['imu_ok'] and 0 <= p['t_us']-p['imu_us'] <= 250000:
            self.angles = tuple(p['angles'])
            if self.pose_device_us != p['imu_us']:
                self.pose_rx, self.pose_device_us = now, p['imu_us']
        else:
            self.angles = None
        if p.get('gsr_ok') and 0 <= p['t_us']-p['gsr_us'] <= 500000:
            if self.gsr_device_us != p['gsr_us']:
                self.gsr_history.append((p['gsr_us']/1e6, p['gsr_mv']))
                self.gsr_device_us = p['gsr_us']
        return True

    def observe_raw(self, p):
        if not gsr_display_valid(p):
            if self.gsr_history and self.gsr_history[-1] is not None:
                self.gsr_history.append(None)
            return
        if p['gsr_us'] <= self.gsr_device_us:
            return
        if (self.gsr_device_us >= 0 and p['gsr_us']-self.gsr_device_us > 500000
                and self.gsr_history and self.gsr_history[-1] is not None):
            self.gsr_history.append(None)
        self.gsr_history.append((p['gsr_us']/1e6, p['gsr_mv']))
        self.gsr_device_us = p['gsr_us']

    def reset_boot(self,boot):
        self.clear_canvas();self.boot=boot;self.stroke=-1;self.seq=None
        self.last_device_us=-1;self.last_rx=0.;self.closed=False;self.status={};self.queue_drops=0

    def accept_telemetry(self,p,now):
        if p['boot']!=self.boot:self.reset_boot(p['boot'])
        if p['t_us']<self.last_device_us or (self.seq is not None and not 0<(p['seq']-self.seq)&0xffffffff<0x80000000):
            return False
        self.last_rx=now;self.last_device_us=p['t_us'];self.seq=p['seq'];self.status=self.data=p
        if p['imu_ok'] and 0<=p['t_us']-p['imu_us']<=250000:
            self.angles=tuple(p['angles'])
            if self.pose_device_us!=p['imu_us']:
                self.pose_rx,self.pose_device_us=now,p['imu_us']
        else:self.angles=None
        self.observe_raw(p) # Same fresh-sample/gap storage, now gated by continuous GSR validity.
        return True

    def accept_optical(self,batch,now=None):
        now=time.monotonic() if now is None else now
        if batch['boot']!=self.boot:self.reset_boot(batch['boot'])
        self.queue_drops=batch['dropped'];accepted=0
        for p in batch['points']:
            if (p['t_us']<self.opt_device_us or
                (self.opt_seq is not None and not 0<(p['seq']-self.opt_seq)&0xffffffff<0x80000000)):
                continue
            gap=self.opt_seq is not None and (p['seq']-self.opt_seq)&0xffffffff!=1
            gap=gap or (self.opt_device_us>=0 and p['t_us']-self.opt_device_us>100000)
            new=p['stroke']!=self.stroke;was_active=self.active
            valid=p['opt_ok'];blocked=self.closed and p['active'] and not new
            if gap or new or not valid or not self.cursor_valid:self.break_trace()
            if gap:self.gaps+=1
            self.opt_seq=p['seq'];self.opt_device_us=p['t_us'];self.opt_rx=now;self.stroke=p['stroke']
            if valid:
                self._raw_xy=(p['x'],p['y'])
                if self._origin is None:self._origin=self._raw_xy
                self.latest_xy=tuple(a-b for a,b in zip(self._raw_xy,self._origin))
            self.cursor_valid=valid
            release=was_active and not p['active'] and not new and p['tip_edge'] and not gap
            if valid and not blocked and (p['active'] or release):
                self.append_point(self.latest_xy,p['t_us'],flush=release)
            self.active=bool(p['active'] and not blocked)
            self.closed=not self.active
            if not self.active:self.break_trace()
            accepted+=1
        return accepted

    def expire(self, now=None):
        now = time.monotonic() if now is None else now
        if self.last_rx and now-self.last_rx > .8:
            self.link_lost()  # Delayed packets cannot resurrect this stroke.
        elif self.angles is not None and now-self.pose_rx > .30:
            self.angles = None
        if self.opt_rx and now-self.opt_rx>.20:
            self.break_trace();self.cursor_valid=False;self.active=False;self.closed=True
