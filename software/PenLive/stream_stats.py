"""Rolling measured rates; distinguish device polls, received samples and UI ticks."""
from collections import deque

class StreamStats:
    def __init__(self):
        self.samples=deque(maxlen=500)
        self.traffic=deque(maxlen=500)
        self.total=0
        self.host_drops=0
        self.boot=None

    def optical(self,batch,now):
        if self.boot!=batch['boot']:
            self.samples.clear();self.total=0;self.boot=batch['boot']
        self.total+=len(batch['points'])
        self.samples.append((now,batch['points'][-1]['t_us'],batch['acquired'],self.total))
        self.bytes(batch,now)

    def bytes(self,packet,now):
        total=packet.get('_wire_bytes_total')
        if total is not None:
            if self.traffic and total<self.traffic[-1][1]:self.traffic.clear()
            self.traffic.append((now,total))

    def rates(self,now):
        for values in (self.samples,self.traffic):
            while values and values[0][0]<now-2:values.popleft()
        acquired=received=byte_rate=0.
        if len(self.samples)>1 and now-self.samples[-1][0]<.5:
            first,last=self.samples[0],self.samples[-1]
            wall=last[0]-first[0];device=(last[1]-first[1])/1e6
            if wall>=.3:received=(last[3]-first[3])/wall
            if device>=.3:acquired=((last[2]-first[2])&0xffffffff)/device
        if len(self.traffic)>1 and now-self.traffic[-1][0]<.5:
            first,last=self.traffic[0],self.traffic[-1]
            if last[0]-first[0]>=.3:byte_rate=(last[1]-first[1])/(last[0]-first[0])
        return acquired,received,byte_rate
