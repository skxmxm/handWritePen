"""Battery samples around the GSR command window; not a transient oscilloscope."""
import struct
from collections import OrderedDict
from pen_protocol import crc16

BATTERY_DIAGNOSTIC_UUID='7c7b9005-8e77-4b62-9c3d-4d5d83f4a001'
BATTERY_PACKET=struct.Struct('<BBIIBBHHHH')

def decode_battery_diagnostic(raw):
    if len(raw)!=20 or crc16(raw[:18])!=int.from_bytes(raw[18:],'little'):
        return None
    magic,version,boot,stroke,flags,samples,before,minimum,age,crc=BATTERY_PACKET.unpack(raw)
    if magic!=0xd8 or version!=1 or flags&~31:
        return None
    baseline=bool(flags&1);valid=bool(flags&2);complete=bool(flags&4)
    running=bool(flags&8);started=bool(flags&16)
    if valid!=bool(samples) or (running and complete):
        return None
    if not started and flags:
        return None
    if started and not (running or complete):
        return None
    if (baseline and age>100) or (not baseline and (before or age!=65535)):
        return None
    if not valid and minimum:
        return None
    return dict(boot=boot,stroke=stroke,before_valid=baseline,minimum_valid=valid,
                complete=complete,running=running,started=started,samples=samples,
                before_v=before/1000,minimum_v=minimum/1000,before_age_ms=age)

class BatteryDiagnostics:
    def __init__(self):self.reset()

    def reset(self):
        self.supported=None;self.error='';self.boot=None;self.latest=None
        self.records=OrderedDict()

    def observe_boot(self,boot):
        if self.boot is not None and self.boot!=boot:
            self.records.clear();self.latest=None
        self.boot=boot

    def observe(self,p):
        if self.boot is not None and p['boot']!=self.boot:
            return False
        if self.latest is not None:
            delta=(p['stroke']-self.latest['stroke'])&0xffffffff
            if delta>=0x80000000:return False
            if delta==0:
                old=self.latest
                if old['complete'] and not p['complete']:return False
                if p['samples']<old['samples']:return False
                if old['minimum_valid'] and p['minimum_valid'] and p['minimum_v']>old['minimum_v']:
                    return False
        self.boot=p['boot'];self.supported=True;self.error='';self.latest=p
        if p['started']:
            key=(p['boot'],p['stroke']);self.records[key]=p;self.records.move_to_end(key)
            while len(self.records)>8:self.records.popitem(last=False)
        return True

    def select(self,fault=None):
        return self.records.get((fault['boot'],fault['stroke'])) if fault else self.latest

    def text(self,fault=None):
        p=self.select(fault)
        if self.error:return self.error
        if self.supported is False:return '电池压降：当前固件未提供窗口记录。'
        if not p or not p['started']:
            return ('同次故障的电池记录尚未收到 / 未建立开启窗口。' if fault
                    else '电池压降：等待激励启动窗口的记录。')
        before=f"{p['before_v']:.3f} V" if p['before_valid'] else '未取得开前新采样'
        low=f"{p['minimum_v']:.3f} V" if p['minimum_valid'] else '尚无开启期间采样'
        return f"第 {p['stroke']} 次电池：开前 {before}；开启期间采样最低 {low}"

    def report(self,fault=None):
        lines=[self.text(fault)]
        p=self.select(fault)
        if p and p['started']:
            lines.append(f"power_boot={p['boot']} power_stroke={p['stroke']} samples={p['samples']} "
                         f"complete={int(p['complete'])} before_age_ms={p['before_age_ms']}")
            if p['before_valid'] and p['minimum_valid']:
                lines.append(f"battery_sample_drop_mV={(p['before_v']-p['minimum_v'])*1000:.1f}")
            lines.append('约50ms间隔、分压RC滤波及8次平均；最低值仅限采样点，不排除更短掉压。')
            lines.append('测的是VBAT，不是3V45/VAA；开启指软件命令窗口，不证明激励开关已物理导通。')
        return '\n'.join(lines)
