"""Causal One Euro position filter. No invented points or cross-stroke blending."""
import math
MODES={'关闭':None,'轻度':(12.,.018),'标准':(6.,.012)}

class TraceFilter:
    def __init__(self,mode='轻度'):
        self.mode=mode;self.reset()
    def reset(self):
        self.raw=self.filtered=None;self.velocity=(0.,0.);self.time=None
    @staticmethod
    def alpha(cutoff,dt):
        return 1/(1+1/(2*math.pi*cutoff*dt))
    def apply(self,point,t_us,flush=False):
        if point is None:
            self.reset();return None
        xy=tuple(point)
        if self.mode=='关闭' or self.raw is None or flush or t_us is None or (self.time is not None and t_us-self.time>100000):
            self.raw=self.filtered=xy;self.time=t_us;self.velocity=(0.,0.);return xy
        dt=max(.001,min(.1,(t_us-self.time)/1e6));a=self.alpha(1.,dt)
        velocity=tuple((xy[i]-self.raw[i])/dt for i in range(2))
        self.velocity=tuple(a*velocity[i]+(1-a)*self.velocity[i] for i in range(2))
        minimum,beta=MODES[self.mode]
        cutoff=minimum+beta*math.hypot(*self.velocity);weight=self.alpha(cutoff,dt)
        self.filtered=tuple(weight*xy[i]+(1-weight)*self.filtered[i] for i in range(2))
        self.raw,self.time=xy,t_us
        return self.filtered
