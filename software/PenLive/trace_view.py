"""Incremental Tk trace rendering. Keeps original samples; no invented positions."""
from collections import deque

class TraceView:
    CHUNK_POINTS = 128

    def __init__(self, canvas):
        self.canvas = canvas
        self.key = None
        self.processed = 0
        self.chunks = deque()
        self.dots = deque()
        self.cursor_key = None
        self.current = self.previous = None
        self.dirty = {}
        self.bounds = None
        self.cx = self.cy = 0.
        self.scale = 1.

    def project(self, point):
        return (self.w/2+(point[0]-self.cx)*self.scale,
                self.h/2-(point[1]-self.cy)*self.scale)

    def clear_lines(self):
        self.canvas.delete('trace_line')
        self.canvas.delete('trace_dot')
        self.chunks.clear()
        self.dots.clear()
        self.current = self.previous = None

    def append(self, serial, point):
        if point is None:
            if self.previous is not None and self.current is None:
                last_serial, (x,y) = self.previous
                item = self.canvas.create_oval(x-1.5,y-1.5,x+1.5,y+1.5,
                    fill='#235f9d',outline='',tags='trace_dot')
                self.dots.append((last_serial,item))
            self.previous = self.current = None
            return
        xy = self.project(point)
        if self.previous is not None:
            last_serial, last_xy = self.previous
            if self.current is None or len(self.current['coords']) >= 2*self.CHUNK_POINTS:
                coords = [*last_xy, *xy]
                item = self.canvas.create_line(*coords, fill='#235f9d', width=2.4, capstyle='round', joinstyle='round', tags='trace_line')
                self.current = dict(item=item, coords=coords, first=last_serial, last=serial)
                self.chunks.append(self.current)
            else:
                self.current['coords'].extend(xy)
                self.current['last'] = serial
                self.dirty[self.current['item']] = self.current
        self.previous = serial, xy

    def trim(self, first_kept):
        while self.dots and self.dots[0][0] < first_kept:
            self.canvas.delete(self.dots.popleft()[1])
        while self.chunks and self.chunks[0]['last'] < first_kept:
            old = self.chunks.popleft()
            self.canvas.delete(old['item'])
            if self.current is old:
                self.current = None
        if self.chunks and self.chunks[0]['first'] < first_kept:
            old = self.chunks[0]
            count = first_kept-old['first']
            del old['coords'][:count*2]
            old['first'] = first_kept
            if len(old['coords']) >= 4:
                self.canvas.coords(old['item'], *old['coords'])
            else:
                self.canvas.delete(old['item'])
                self.chunks.popleft()
                if self.current is old:
                    self.current = None

    def draw(self, state, auto=True, swap=False, flip_x=False, flip_y=True):
        c = self.canvas
        self.w, self.h = max(c.winfo_width(), 1), max(c.winfo_height(), 1)
        key = (id(state), state.boot, state.trace_generation, self.w, self.h,
               auto, swap, flip_x, flip_y)
        changed = key != self.key or state.point_serial < self.processed
        if changed:
            self.key = key
            c.delete('all')
            self.chunks.clear()
            self.dots.clear()
            self.current = self.previous = None
            self.processed = 0
            self.bounds = None
            self.cx = self.cy = 0.
            self.scale = max(.00001,min(self.w-60,self.h-60)/200) if auto else 1.
            for x in range(0,self.w,40):c.create_line(x,0,x,self.h,fill='#edf1f5',tags='grid')
            for y in range(0,self.h,40):c.create_line(0,y,self.w,y,fill='#edf1f5',tags='grid')
            self.label = c.create_text(12,13,anchor='nw',fill='#213447')
            self.hint = c.create_text(self.w/2,self.h/2,fill='#7a8a99',font=('Helvetica',15))
            self.dot = c.create_oval(0,0,0,0,fill='#e58b2e',outline='',width=1.5,
                                     state='hidden',tags='cursor')
        cursor_key = (state.active,state.stroke,state.latest_xy,state.cursor_valid)
        if not changed and state.point_serial == self.processed and cursor_key == self.cursor_key:
            return
        self.cursor_key = cursor_key

        def orient(p):
            if p is None:return None
            x,y = p
            if swap:x,y=y,x
            return (-x if flip_x else x, -y if flip_y else y)

        count = min(state.point_serial-self.processed,len(state.points))
        # Index from the deque tail: work is proportional to newly received points.
        if count == len(state.points):
            points = [orient(p) for p in state.points]
        else:
            points = [orient(state.points[i]) for i in range(-count,0)] if count else []
        cursor_xy = state.points[-1] if state.active and state.points and state.points[-1] is not None else state.latest_xy
        cursor = orient(cursor_xy) if state.cursor_valid else None
        extent_points = points + ([cursor] if cursor is not None else [])
        for p in extent_points:
            if p is None:continue
            if self.bounds is None:self.bounds = [p[0],p[0],p[1],p[1]]
            else:
                self.bounds[0]=min(self.bounds[0],p[0]);self.bounds[1]=max(self.bounds[1],p[0])
                self.bounds[2]=min(self.bounds[2],p[1]);self.bounds[3]=max(self.bounds[3],p[1])
        # Expand only when needed, with extra room; don't move the entire trace every sample.
        if auto and self.bounds is not None and any(
                not (30 <= self.project(p)[0] <= self.w-30 and 30 <= self.project(p)[1] <= self.h-30)
                for p in extent_points if p is not None):
            x0,x1,y0,y1 = self.bounds
            self.cx,self.cy = (x0+x1)/2,(y0+y1)/2
            self.scale = max(.00001,min((self.w-80)/max(200,(x1-x0)*1.25),
                                       (self.h-80)/max(200,(y1-y0)*1.25)))
            self.clear_lines()
            points = [orient(p) for p in state.points]
            count = len(points)
        self.dirty.clear()
        for serial,p in enumerate(points,state.point_serial-count+1):
            self.append(serial,p)
        for item, chunk in self.dirty.items():
            c.coords(item,*chunk['coords'])
        self.dirty.clear()
        self.processed = state.point_serial
        self.trim(state.point_serial-len(state.points)+1)
        if cursor is not None:
            px,py = self.project(cursor)
            c.coords(self.dot,px-4,py-4,px+4,py+4)
            c.itemconfigure(self.dot,state='normal',fill='#e58b2e' if state.active else '',
                            outline='' if state.active else '#687d90')
        else:
            c.itemconfigure(self.dot,state='hidden')
        c.itemconfigure(self.hint,text='' if self.bounds is not None else '落笔画线，抬笔移动；等待有效光学位移…')
        mode = '落笔' if state.active else '抬笔（不画线）'
        position = f'X {state.latest_xy[0]}   Y {state.latest_xy[1]}' if state.cursor_valid else '位置暂不可用'
        c.itemconfigure(self.label,text=f'{mode}   {position}   单位：计数')
        c.tag_raise(self.dot)
        c.tag_raise(self.label)

class EventRate:
    """Recent observed event rate; call using arrival times, not UI dequeue time."""
    def __init__(self):
        self.times = deque(maxlen=1000)

    def add(self, now):
        self.times.append(now)

    def hz(self, now):
        while self.times and self.times[0] < now-2:
            self.times.popleft()
        if len(self.times) < 2 or now-self.times[-1] > .5:
            return 0.
        span = self.times[-1]-self.times[0]
        return (len(self.times)-1)/span if span >= .3 else 0.
