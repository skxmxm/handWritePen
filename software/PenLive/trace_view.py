"""Incremental Tk trace rendering. Keeps original samples; no invented positions."""
from collections import deque

def contain_size(img_w, img_h, bounds_w, bounds_h):
    """Largest size that shows the whole image inside the bounds, never upscaling."""
    img_w, img_h = int(img_w), int(img_h)
    bounds_w, bounds_h = int(bounds_w), int(bounds_h)
    if min(img_w, img_h, bounds_w, bounds_h) <= 0:
        return 1, 1, 1.0
    scale = min(1.0, bounds_w / img_w, bounds_h / img_h)
    show_w = min(bounds_w, max(1, int(round(img_w * scale))))
    show_h = min(bounds_h, max(1, int(round(img_h * scale))))
    return show_w, show_h, scale

def centered_box(canvas_w, canvas_h, img_w, img_h):
    """Pixel box of a contained image, centered in the canvas. Returns (x0, y0, x1, y1), scale."""
    show_w, show_h, scale = contain_size(img_w, img_h, canvas_w, canvas_h)
    x0 = max(0, (int(canvas_w) - show_w) // 2)
    y0 = max(0, (int(canvas_h) - show_h) // 2)
    return (x0, y0, x0 + show_w, y0 + show_h), scale

def background_window_plan(img_w, img_h, chrome_w, chrome_h, screen_w, screen_h,
                           current_w, current_h, margin=(16, 72)):
    """Grow the drawing window so the whole image fits, capped to the screen.

    An image smaller than the current window does not shrink the window.
    An image larger than the available area is reported in display size via contain_size.
    """
    margin_x, margin_y = margin
    screen_w, screen_h = max(1, int(screen_w)), max(1, int(screen_h))
    max_w = screen_w if margin_x >= screen_w else screen_w - margin_x
    max_h = screen_h if margin_y >= screen_h else screen_h - margin_y
    chrome_w, chrome_h = max(0, int(chrome_w)), max(0, int(chrome_h))
    avail_w = max(1, max_w - chrome_w)
    avail_h = max(1, max_h - chrome_h)
    show_w, show_h, scale = contain_size(img_w, img_h, avail_w, avail_h)
    desired_w = min(max_w, chrome_w + show_w)
    desired_h = min(max_h, chrome_h + show_h)
    new_w = min(max_w, max(int(current_w), desired_w))
    new_h = min(max_h, max(int(current_h), desired_h))
    return {'window': (new_w, new_h), 'display': (show_w, show_h), 'scale': scale,
            'max_window': (max_w, max_h)}

def window_origin(x, y, win_w, win_h, screen_w, screen_h):
    """Shift a window so its client area stays inside the screen."""
    x, y = int(x), int(y)
    if x + win_w > screen_w:
        x = max(0, int(screen_w) - int(win_w))
    if y + win_h > screen_h:
        y = max(0, int(screen_h) - int(win_h))
    return max(0, x), max(0, y)

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
        self.background = None
        self.background_box = None
        self.background_epoch = 0

    def set_background(self, photo, box):
        """Show photo inside box=(x0, y0, x1, y1). None clears it and releases the cursor."""
        self.background = photo
        self.background_box = tuple(int(v) for v in box) if box else None
        self.background_epoch += 1

    def project(self, point):
        x = self.w/2+(point[0]-self.cx)*self.scale
        y = self.h/2-(point[1]-self.cy)*self.scale
        box = self.background_box
        if box:
            x0, y0, x1, y1 = box
            pad = 4 if (x1-x0) > 8 and (y1-y0) > 8 else 0
            x = min(max(x, x0+pad), x1-pad)
            y = min(max(y, y0+pad), y1-pad)
        return (x, y)

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
               auto, swap, flip_x, flip_y, self.background_epoch, self.background_box)
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
            if self.background_box:
                x0, y0, x1, y1 = self.background_box
                self.scale = max(.00001, min(x1-x0, y1-y0)/200)
                if self.background is not None:
                    c.create_image(x0, y0, image=self.background, anchor='nw', tags='background')
                    c.create_rectangle(x0, y0, x1, y1, outline='#c5d0dc', width=1, tags='background')
            else:
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
        if auto and not self.background_box and self.bounds is not None and any(
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
        if self.bounds is not None:
            hint = ''
        elif self.background_box:
            hint = '背景已固定。落笔画线，抬笔移动；光标保持在图片内。'
        else:
            hint = '落笔画线，抬笔移动；等待有效光学位移…'
        c.itemconfigure(self.hint,text=hint)
        mode = '落笔' if state.active else '抬笔（不画线）'
        position = f'X {state.latest_xy[0]}   Y {state.latest_xy[1]}' if state.cursor_valid else '位置暂不可用'
        c.itemconfigure(self.label,text=f'{mode}   {position}   单位：计数')
        if self.background_box:
            c.tag_lower('background')
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
