"""Optional GSR fault characteristic; v4 uses excitation sessions independently of tip strokes."""
import struct
from pen_protocol import crc16, adc_fresh
from battery_diagnostic import BatteryDiagnostics
DIAGNOSTIC_UUID='7c7b9004-8e77-4b62-9c3d-4d5d83f4a001'
PACKET=struct.Struct('<BBIIBBBBhHH')
REASONS={
    1:'ADC 通信失败（I²C 应答 / 读取异常）',
    2:'ADC 配置读回不符',
    3:'ADC 转换超时',
    4:'开启前 1 秒内未取得合格的新采样',
    5:'关闭时 VEX 超过 ±50 mV',
    6:'开启后 ADC 数据无效',
    7:'开启后 ADC 数据超过 500 ms 未更新',
    8:'开启后 VEX 低于 350 mV',
    9:'开启后 VEX 高于 700 mV',
}
PHASES={1:'开启前检查',2:'开启后稳定检查',3:'有效采集中'}

def decode_diagnostic(raw):
    if len(raw)!=PACKET.size or crc16(raw[:18])!=int.from_bytes(raw[18:],'little'):
        return None
    magic,version,boot,stroke,reason,phase,flags,adc,vex,age,crc=PACKET.unpack(raw)
    if magic!=0xd7 or version!=1 or reason>9 or flags&~1 or adc>3:
        return None
    if reason and phase not in PHASES:
        return None
    return dict(boot=boot,stroke=stroke,reason=reason,phase=phase,sample_valid=bool(flags&1),
                adc_error=adc,vex_mv=vex*.125,age_ms=age)

class GsrDiagnostics:
    def __init__(self):
        self.reset()

    def reset(self):
        self.supported=None
        self.last_fault=None
        self.boot=None
        self.latest=None
        self.live=None
        self.transport_error=''
        self.battery=BatteryDiagnostics()

    def observe_packet(self,p):
        if self.boot is not None and self.boot!=p['boot']:
            self.last_fault=self.latest=None
        self.boot=p['boot']
        self.live=p
        self.battery.observe_boot(p['boot'])

    def observe_fault(self,p):
        if self.boot is not None and p['boot']!=self.boot:
            return False
        if self.latest is not None:
            delta=(p['stroke']-self.latest['stroke'])&0xffffffff
            if delta>=0x80000000:
                return False  # An initial read must not replace a later notification.
        self.boot=p['boot']
        self.supported=True
        self.transport_error=''
        self.latest=p
        if p['reason']:
            self.last_fault=p
        return True

    def text(self,current):
        if current.get('raw_off'):
            text = '无激励观察版：不执行激励开启检查。'
            if current.get('ads_error'):
                text += '\nADC 异常：'+REASONS.get(current['ads_error'], '未知错误')
            elif not adc_fresh(current):
                text += '\nADC 尚无新鲜数据。'
            elif abs(current.get('vex_mv', 0)) > 50:
                text += '\nVEX 关闭状态仍超过 ±50 mV；软件关闭不证明实物已关闭。'
            else:
                text += '\nVEX 接近零；这不能证明模拟供电或生理信号有效。'
            if current.get('usb'):
                text += '\nUSB 已连接，调试时取下指套。'
            return text
        prefix=(self.transport_error+'\n') if self.transport_error else ''
        if self.last_fault:
            p=self.last_fault
            sample=(f"{p['vex_mv']:.3f} mV，采样距故障 {p['age_ms']} ms"
                    if p['sample_valid'] else '无有效采样（不把旧值当故障电压）')
            label="次激励启动" if (current or self.live or {}).get("v",2)>=4 else "次按下"
            return (prefix+f"最近故障 E{p['reason']:02d} · 第 {p['stroke']} {label}\n"
                    f"{PHASES[p['phase']]}：{REASONS[p['reason']]}\n"
                    f"故障当时 VEX：{sample}")
        if self.supported is False:
            return '当前固件未提供故障快照；需烧录诊断版后定位具体原因。'
        if current.get('gsr_state')==5:
            return prefix+'等待固件的具体故障快照…'
        return prefix+'尚无故障记录；故障发生后会保留原因和当时的 VEX。'

    def report(self,current):
        raw = bool(current.get('raw_off'))
        lines=['R26 无激励原始电压观察' if raw else 'R26 GSR 诊断（窗口当前连接）',self.text(current)]
        if self.last_fault and not raw:
            f=self.last_fault
            lines.append(f"fault_boot={f['boot']} fault_stroke={f['stroke']} fault_ADC_error={f['adc_error']}")
        if not raw:
            lines.append(self.battery.report(self.last_fault))
            if (current or self.live or {}).get('v',2)>=4:
                lines.append('v4: fault_stroke / power_stroke 为激励启动编号；stroke 为书写笔画编号，两者独立。')
        else:
            lines.append('显示 ADC A0 板上输出电压；未标定，不是两指电位差、电导或压力值。')
        if current:
            lines.extend([
                f"boot={current['boot']} stroke={current['stroke']} USB={int(current.get('usb',False))} active={int(current.get('active',False))}",
                f"GSR_state={current.get('gsr_state')} excitation_command={int(current.get('excitation',False))} ADC_error={current.get('ads_error')}",
                f"ADC_valid={int(current.get('ads_ok',False))} VEX_now_mV={current.get('vex_mv')} GSR_now_mV={current.get('gsr_mv')}",
                f"battery_V={current.get('battery_v')} optical_ok={int(current.get('opt_ok',False))} imu_ok={int(current.get('imu_ok',False))}",
                'excitation_command 是软件命令，不是 EXC_EN 引脚实测电平。'])
        else:
            lines.append('当前无实时数据；上方若有记录，只是本次连接中的历史故障。')
        return '\n'.join(lines)
