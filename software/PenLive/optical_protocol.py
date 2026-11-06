"""CRC-protected optical batches, independent of slower health telemetry."""
import struct
import time
from pen_protocol import crc16
OPTICAL_UUID='7c7b9006-8e77-4b62-9c3d-4d5d83f4a001'
HEADER=struct.Struct('<IIIB')
RECORD=struct.Struct('<IQiiIB')

def decode_optical(raw):
    if len(raw)<40 or crc16(raw[:-2])!=int.from_bytes(raw[-2:],'little'):
        return None
    boot,acquired,dropped,count=HEADER.unpack_from(raw)
    if not 1<=count<=6 or len(raw)!=HEADER.size+count*RECORD.size+2:
        return None
    points=[]
    for i in range(count):
        seq,t,x,y,stroke,flags=RECORD.unpack_from(raw,HEADER.size+i*RECORD.size)
        if flags&~7 or (points and (t<points[-1]['t_us'] or not 0<(seq-points[-1]['seq'])&0xffffffff<0x80000000)):
            return None
        points.append(dict(seq=seq,t_us=t,x=x,y=y,stroke=stroke,
                           active=bool(flags&1),opt_ok=bool(flags&2),tip_edge=bool(flags&4)))
    return dict(boot=boot,acquired=acquired,dropped=dropped,points=points)

class OpticalDecoder:
    def __init__(self):
        self.errors=0;self.reset()
    def reset(self):
        self.message=None;self.index=0;self.count=0;self.buffer=bytearray();self.started=0
    def feed(self,data,now=None):
        now=time.monotonic() if now is None else now;b=bytes(data)
        if len(b)<7 or b[:2]!=b'\xa6\x01' or not 1<=b[5]<=12 or b[4]>=b[5]:
            self.errors+=1;self.reset();return None
        message=int.from_bytes(b[2:4],'little');index,count=b[4:6]
        if index==0:
            self.reset();self.message=message;self.count=count;self.started=now
        if message!=self.message or index!=self.index or count!=self.count or now-self.started>.5:
            self.errors+=1;self.reset();return None
        self.buffer.extend(b[6:]);self.index+=1
        if len(self.buffer)>165:
            self.errors+=1;self.reset();return None
        if self.index==count:
            result=decode_optical(bytes(self.buffer))
            if result is None:self.errors+=1
            self.reset();return result
        return None
