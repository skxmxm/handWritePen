#!/usr/bin/env python3
"""Three-window BLE viewer for the R26 smart pen. --demo needs no hardware."""
import argparse
import asyncio
import base64
import io
import math
import queue
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from pen_protocol import (StrokeState, rotation, transpose, multiply, apply, charger_text,
                          adc_fresh, gsr_display_valid)
from ble_transport import BleWorker, discover_pens
from trace_view import (TraceView, EventRate, background_window_plan, centered_box,
                        window_origin)
from grip_calibration import last_ink_stroke, line_angle
from gsr_diagnostic import GsrDiagnostics
from stream_stats import StreamStats
from trace_filter import MODES

def _pil_resample():
    from PIL import Image
    return getattr(getattr(Image, 'Resampling', Image), 'LANCZOS')

def _photo_from_image(master, image):
    """Tk photo without PIL.ImageTk, which is absent on some Linux Pillow builds."""
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return tk.PhotoImage(data=base64.b64encode(buffer.getvalue()), master=master)

BACKGROUND = '#f5f7fa'
INK = '#235f9d'
TEXT = '#213447'
FRAME_SECONDS = 1/60

class PenApp:
    def __init__(self, address=None, demo=False):
        self.root = tk.Tk()
        self.root.title('手写笔 · 书写轨迹 · BLE')
        self.root.geometry('720x600+25+60')
        self.root.configure(bg=BACKGROUND)
        self.pose = tk.Toplevel(self.root)
        self.pose.title('手写笔 · 空间姿态')
        self.pose.geometry('600x560+760+60')
        self.pose.configure(bg=BACKGROUND)
        self.health = tk.Toplevel(self.root)
        self.health.title('手写笔 · 电池与皮肤电')
        self.health.geometry('620x800+540+30')
        self.health.configure(bg=BACKGROUND)
        for window in (self.root, self.pose, self.health):
            window.protocol('WM_DELETE_WINDOW', self.close)
            window.minsize(560, 460)
        self.root.minsize(640, 460)
        self.health.minsize(620, 760)
        self.state = StrokeState('轻度')
        self.diagnostics = GsrDiagnostics()
        self.events = queue.Queue(maxsize=2000)
        self.worker = None
        self.running = True
        self.demo = demo
        if demo:
            for window in (self.root, self.pose, self.health):
                window.title(window.title()+' · 模拟数据')
        self.demo_start = time.monotonic()
        self.demo_seq = 0
        self.reference = None
        self.rx_rate, self.ui_rate = EventRate(), EventRate()
        self.stream_stats = StreamStats()
        self.optical_support = None
        self.optical_error = ''
        self.rate_updated = 0.
        self.next_frame_at = time.perf_counter()+FRAME_SECONDS
        self.summary_key = None
        self.pose_key = self.health_key = None
        self.reference_boot = None
        self.status_text = tk.StringVar(value='未连接。先扫描，选择 SmartPen-R26，再连接。')
        self.measure_text = tk.StringVar(value='光学：等待　｜　IMU：等待')
        self.rate_text = tk.StringVar(value='接收 — 包/秒　｜　界面 — 次/秒')
        self.pose_text = tk.StringVar(value='等待姿态数据')
        self.smoothing = tk.StringVar(value='轻度')
        self.device_var = tk.StringVar(value=address or '')
        self.devices = {}
        self.axis = tk.StringVar(value='X')
        self.flip_x = tk.BooleanVar(value=False)
        self.flip_y = tk.BooleanVar(value=True)
        self.swap_xy = tk.BooleanVar(value=False)
        self.auto_fit = tk.BooleanVar(value=True)
        self.pose_mode = tk.StringVar(value='传感器参考坐标')
        self.background_text = tk.StringVar(value='未设置')
        self._bg_source = None
        self._bg_photo = None
        self._bg_layout_lock = False
        self._bg_canvas_size = None
        self.battery_text = tk.StringVar(value='— V')
        self.charge_text = tk.StringVar(value='等待 BLE 数据')
        self.gsr_text = tk.StringVar(value='— mV')
        self.vex_text = tk.StringVar(value='激励监测：—')
        self.gsr_state_text = tk.StringVar(value='等待连接')
        self.gsr_title = tk.StringVar(value='皮肤电输出 · 等待数据')
        self.gsr_footer = tk.StringVar(value='连接后连续采集；USB 接入时关闭激励。未标定为皮肤电导。')
        self.diagnostic_text = tk.StringVar(value='尚无故障记录')
        self.copy_text = tk.StringVar(value='复制诊断')
        self.grip_text = tk.StringVar(value='未校正')
        self.grip_calibrating = False
        self.grip_set = False
        self._grip_seen_serial = -1
        self.make_ui()
        self.trace_view = TraceView(self.canvas)
        for variable in (self.flip_x, self.flip_y, self.swap_xy):
            variable.trace_add('write', self._grip_frame_changed)
        self.root.after(16, self.tick)
        if address and not demo:
            self.root.after(200, self.connect)

    def make_ui(self):
        style = ttk.Style()
        # Native Aqua dark-mode frames ignore background colors; use a consistent readable theme.
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TFrame', background=BACKGROUND)
        style.configure('TLabel', background=BACKGROUND, foreground=TEXT)
        style.configure('Title.TLabel', font=('Helvetica', 20, 'bold'))
        style.configure('Value.TLabel', font=('Helvetica', 27, 'bold'))
        header = ttk.Frame(self.root, padding=(18, 15)); header.pack(fill='x')
        ttk.Label(header, text='书写轨迹', style='Title.TLabel').pack(anchor='w')
        ttk.Label(header, text='BLE 无线采集 · 落笔画线 · 抬笔移动 · 保留已有笔画').pack(anchor='w', pady=(5, 10))
        row = ttk.Frame(header); row.pack(fill='x')
        self.device_box = ttk.Combobox(row, textvariable=self.device_var, width=29)
        self.device_box.pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='扫描', command=self.scan).pack(side='left', padx=3)
        ttk.Button(row, text='连接', command=self.connect).pack(side='left', padx=3)
        ttk.Button(row, text='断开', command=self.disconnect).pack(side='left', padx=3)
        row = ttk.Frame(header); row.pack(fill='x', pady=(10, 0))
        self.auto_fit_check = None
        for label, var in [('自动缩放', self.auto_fit), ('交换XY', self.swap_xy), ('反转X', self.flip_x), ('反转Y', self.flip_y)]:
            widget = ttk.Checkbutton(row, text=label, variable=var)
            widget.pack(side='left', padx=(0, 8))
            if var is self.auto_fit:
                self.auto_fit_check = widget
        ttk.Button(row, text='重试传感器', command=self.retry_sensors).pack(side='right')
        self.clear_trace_button = ttk.Button(row, text='清空轨迹', command=self.clear_trace)
        self.clear_trace_button.pack(side='right', padx=4)
        row = ttk.Frame(header); row.pack(fill='x', pady=(8, 0))
        ttk.Label(row, text='轨迹平滑：').pack(side='left')
        selector = ttk.Combobox(row, textvariable=self.smoothing, values=list(MODES), state='readonly', width=6)
        selector.pack(side='left')
        selector.bind('<<ComboboxSelected>>', lambda _event: self.change_smoothing())
        ttk.Label(row, text='关闭可查看原始轨迹；平滑不跨越抬笔或丢包缺口').pack(side='left', padx=8)
        row = ttk.Frame(header); row.pack(fill='x', pady=(8, 0))
        ttk.Label(row, text='画板背景：').pack(side='left')
        ttk.Button(row, text='选择图片', command=self.choose_background).pack(side='left', padx=(4, 0))
        self.clear_background_button = ttk.Button(row, text='清除背景', command=self.clear_background)
        self.clear_background_button.pack(side='left', padx=4)
        self.clear_background_button.state(['disabled'])
        ttk.Label(row, textvariable=self.background_text).pack(side='left', padx=4)
        row = ttk.Frame(header); row.pack(fill='x', pady=(8, 0))
        ttk.Label(row, text='握笔校正：').pack(side='left')
        self.grip_button = ttk.Button(row, text='开始校正', command=self.toggle_grip_calibration)
        self.grip_button.pack(side='left', padx=(4, 0))
        self.clear_grip_button = ttk.Button(row, text='清除校正', command=self.clear_grip)
        self.clear_grip_button.pack(side='left', padx=4)
        self.clear_grip_button.state(['disabled'])
        ttk.Label(row, textvariable=self.grip_text).pack(side='left', padx=4)
        self.canvas = tk.Canvas(self.root, height=1, bg='white', highlightthickness=1, highlightbackground='#dce3eb')
        self.canvas.pack(fill='both', expand=True, padx=18)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        foot = ttk.Frame(self.root, padding=(18, 12)); foot.pack(fill='x')
        ttk.Label(foot, textvariable=self.status_text, wraplength=670).pack(anchor='w')
        ttk.Label(foot, textvariable=self.measure_text, wraplength=670).pack(anchor='w', pady=(5, 0))
        ttk.Label(foot, textvariable=self.rate_text, wraplength=670).pack(anchor='w', pady=(5, 0))

        ph = ttk.Frame(self.pose, padding=(18, 15)); ph.pack(fill='x')
        ttk.Label(ph, text='空间姿态', style='Title.TLabel').pack(anchor='w')
        ttk.Label(ph, text='显示旋转方向，不通过加速度推算三维位置').pack(anchor='w', pady=5)
        controls = ttk.Frame(ph); controls.pack(fill='x')
        ttk.Label(controls, text='笔尖沿模块轴：').pack(side='left')
        ttk.Combobox(controls, textvariable=self.axis, values=['X','-X','Y','-Y','Z','-Z'], state='readonly', width=4).pack(side='left')
        ttk.Button(controls, text='当前姿态归零', command=self.zero_pose).pack(side='left', padx=8)
        ttk.Button(controls, text='恢复参考坐标', command=self.reset_pose).pack(side='left')
        ttk.Label(ph, textvariable=self.pose_mode, wraplength=550).pack(anchor='w', pady=(8,0))
        self.pose_canvas = tk.Canvas(self.pose, height=1, bg='white', highlightthickness=1, highlightbackground='#dce3eb')
        self.pose_canvas.pack(fill='both', expand=True, padx=18)
        pf=ttk.Frame(self.pose, padding=(18,12)); pf.pack(fill='x')
        ttk.Label(pf, textvariable=self.pose_text, wraplength=550).pack(anchor='w')
        ttk.Label(pf, text='模块与笔身轴向需试装确认；航向受磁场与校准影响。', wraplength=550).pack(anchor='w', pady=(5,0))

        hh = ttk.Frame(self.health, padding=18); hh.pack(fill='x')
        ttk.Label(hh, text='电池与皮肤电', style='Title.TLabel').pack(anchor='w')
        ttk.Label(hh, text='电池电压 · 约每秒更新一次').pack(anchor='w', pady=(12,0))
        ttk.Label(hh, textvariable=self.battery_text, style='Value.TLabel').pack(anchor='w')
        ttk.Label(hh, textvariable=self.charge_text, wraplength=535).pack(anchor='w', pady=(3,10))
        ttk.Separator(hh).pack(fill='x')
        ttk.Label(hh, text='电池温度：数值不可读', font=('Helvetica',14,'bold')).pack(anchor='w', pady=(10,3))
        ttk.Label(hh, text='现板 NTC 仅接充电芯片，未接 MCU / ADC。\n充电故障状态不能确定具体温度或故障原因。', wraplength=535).pack(anchor='w')
        ttk.Separator(hh).pack(fill='x', pady=(12,8))
        ttk.Label(hh, textvariable=self.gsr_title).pack(anchor='w')
        ttk.Label(hh, textvariable=self.gsr_text, style='Value.TLabel').pack(anchor='w')
        ttk.Label(hh, textvariable=self.vex_text).pack(anchor='w')
        ttk.Label(hh, textvariable=self.gsr_state_text, wraplength=535).pack(anchor='w', pady=(5,0))
        diagnostic = self.diagnostic_frame = ttk.LabelFrame(hh, text='采集状态', padding=8)
        diagnostic.pack(fill='x', pady=(10,0))
        self.diagnostic_label = ttk.Label(diagnostic, textvariable=self.diagnostic_text, wraplength=550)
        self.diagnostic_label.pack(anchor='w')
        self.copy_button = ttk.Button(diagnostic, textvariable=self.copy_text, command=self.copy_diagnostic)
        self.copy_button.pack(anchor='e', pady=(5,0))
        self.gsr_canvas = tk.Canvas(self.health, height=1, bg='white', highlightthickness=1, highlightbackground='#dce3eb')
        self.gsr_canvas.pack(fill='both', expand=True, padx=18)
        hf = ttk.Frame(self.health, padding=(18,10)); hf.pack(fill='x')
        self.clear_gsr_button = ttk.Button(hf, text='清空电压曲线', command=self.clear_gsr)
        self.clear_gsr_button.pack(anchor='e', pady=(0,5))
        self.gsr_footer_label = ttk.Label(hf, textvariable=self.gsr_footer, wraplength=535)
        self.gsr_footer_label.pack(anchor='w')

    def set_status(self, value):
        if self.status_text.get() != value:
            self.status_text.set(value)

    def copy_diagnostic(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.diagnostics.report(self.state.status))
        self.copy_text.set('已复制')
        self.root.after(2000, lambda: self.copy_text.set('复制诊断'))

    def disconnect(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.events = queue.Queue(maxsize=2000)
        self.state = StrokeState(self.smoothing.get())
        self.diagnostics.reset()
        self.rx_rate = EventRate()
        self.stream_stats = StreamStats()
        self.optical_support = None
        self.optical_error = ''
        self.grip_calibrating = False
        self.trace_view.grip_waiting = False
        self.grip_button.configure(text='开始校正')
        self.demo = False
        self.set_status('已断开，画板已清空。')

    def scan(self):
        self.disconnect()
        self.set_status('正在扫描附近的 SmartPen-R26（约 5 秒）…')
        self.worker = BleWorker(None, self.events, scan_only=True)
        self.worker.start()

    def connect(self):
        self.disconnect()
        selection = self.device_var.get().strip()
        address = self.devices.get(selection, selection) or None
        self.set_status('正在寻找并连接手写笔…')
        self.worker = BleWorker(address, self.events)
        self.worker.start()

    def retry_sensors(self):
        if self.worker:
            self.worker.commands.put(b'i')

    def change_smoothing(self):
        self.state.set_smoothing(self.smoothing.get())
        self.draw_trace()

    def clear_trace(self):
        self.state.clear_trace()
        self.draw_trace()

    def toggle_grip_calibration(self):
        if self.grip_calibrating:
            self.grip_calibrating = False
            self.trace_view.grip_waiting = False
            self.grip_button.configure(text='开始校正')
            self.set_status('已取消握笔校正。')
            self.draw_trace()
            return
        self.grip_calibrating = True
        self.trace_view.grip_waiting = True
        self._grip_seen_serial = self.state.point_serial
        self.grip_button.configure(text='取消校正')
        self.grip_text.set('请从左向右画一条横线')
        self.set_status('握笔校正：按住笔尖，从左向右画一条横线，松开后计算偏移角。')
        self.draw_trace()

    def clear_grip(self):
        self.grip_calibrating = False
        self.grip_set = False
        self.trace_view.grip_waiting = False
        self.trace_view.set_grip_angle(0.0)
        self.grip_button.configure(text='开始校正')
        self.clear_grip_button.state(['disabled'])
        self.grip_text.set('未校正')
        self.set_status('已清除握笔校正。')
        self.draw_trace()

    def _grip_frame_changed(self, *_args):
        if not self.grip_set and not self.grip_calibrating:
            return
        self.grip_calibrating = False
        self.grip_set = False
        self.trace_view.grip_waiting = False
        self.trace_view.set_grip_angle(0.0)
        self.grip_button.configure(text='开始校正')
        self.clear_grip_button.state(['disabled'])
        self.grip_text.set('坐标方向已改变，请重新校正')
        self.set_status('交换或反转坐标后，握笔校正已清除，请重新画一条横线。')

    def _orient_counts(self, point):
        x, y = point
        if self.swap_xy.get():
            x, y = y, x
        if self.flip_x.get():
            x = -x
        if self.flip_y.get():
            y = -y
        return (x, y)

    def _observe_grip(self):
        if not self.grip_calibrating or self.state.active:
            return
        if self.state.point_serial == self._grip_seen_serial:
            return
        stroke, released = last_ink_stroke(self.state.raw_records)
        if not stroke or not released:
            return
        self._grip_seen_serial = self.state.point_serial
        angle = line_angle(self._orient_counts(stroke[0]), self._orient_counts(stroke[-1]))
        if angle is None:
            self.grip_text.set('横线太短，请再画一条')
            self.set_status('这条横线太短。请按住笔尖，从左向右再画一条更长的横线。')
            return
        self.grip_calibrating = False
        self.grip_set = True
        self.trace_view.grip_waiting = False
        self.trace_view.set_grip_angle(angle)
        self.grip_button.configure(text='开始校正')
        self.clear_grip_button.state(['!disabled'])
        self.grip_text.set(f'已校正 {math.degrees(angle):+.1f}°')
        self.set_status(f'握笔校正完成，偏移 {math.degrees(angle):+.1f}°。之后的光标按这个角度旋转。')
        self.draw_trace()

    def choose_background(self):
        path = filedialog.askopenfilename(
            parent=self.root, title='选择画板背景图片',
            filetypes=[('图片', '*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff'),
                       ('所有文件', '*.*')])
        if path:
            self.load_background(path)

    def load_background(self, path):
        try:
            from PIL import Image, ImageOps
            image = ImageOps.exif_transpose(Image.open(path))
            image.load()
            image = image.convert('RGBA')
        except Exception as exc:
            self.set_status(f'背景图片无法打开：{exc}')
            return
        self.set_background_image(image, Path(path).name)

    def set_background_image(self, image, name='背景'):
        if image.width < 1 or image.height < 1:
            self.set_status('背景图片尺寸无效。')
            return
        self._bg_source = image.convert('RGBA') if image.mode != 'RGBA' else image.copy()
        shown = name if len(name) <= 32 else name[:14] + '…' + name[-14:]
        self.background_text.set(shown)
        self._fit_background_window()
        self._render_background()
        if self.auto_fit_check is not None:
            self.auto_fit_check.state(['disabled'])
        self.clear_background_button.state(['!disabled'])
        self.set_status(f'已附加背景 {shown}。光标限制在图片范围内。')

    def clear_background(self):
        if self._bg_source is None and self.trace_view.background_box is None:
            return
        self._bg_source = None
        self._bg_photo = None
        self._bg_canvas_size = None
        self.background_text.set('未设置')
        self.trace_view.set_background(None, None)
        if self.auto_fit_check is not None:
            self.auto_fit_check.state(['!disabled'])
        self.clear_background_button.state(['disabled'])
        self.draw_trace()
        self.set_status('已清除背景。')

    def _fit_background_window(self):
        image = self._bg_source
        if image is None:
            return
        self._bg_layout_lock = True
        try:
            self.root.update_idletasks()
            if self.canvas.winfo_width() < 20 or self.canvas.winfo_height() < 20:
                self.root.update()
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            plan = background_window_plan(
                image.width, image.height,
                self.root.winfo_width() - self.canvas.winfo_width(),
                self.root.winfo_height() - self.canvas.winfo_height(),
                screen_w, screen_h, self.root.winfo_width(), self.root.winfo_height())
            new_w, new_h = plan['window']
            x, y = window_origin(self.root.winfo_x(), self.root.winfo_y(), new_w, new_h, screen_w, screen_h)
            self.root.geometry(f'{int(new_w)}x{int(new_h)}+{int(x)}+{int(y)}')
            self.root.update()
        finally:
            self._bg_layout_lock = False

    def _render_background(self):
        image = self._bg_source
        if image is None or self._bg_layout_lock:
            return
        self._bg_layout_lock = True
        try:
            canvas_w = max(1, self.canvas.winfo_width())
            canvas_h = max(1, self.canvas.winfo_height())
            box, _scale = centered_box(canvas_w, canvas_h, image.width, image.height)
            show_w, show_h = box[2] - box[0], box[3] - box[1]
            shown = image if image.size == (show_w, show_h) else image.resize((show_w, show_h), _pil_resample())
            self._bg_photo = _photo_from_image(self.root, shown)
            self._bg_canvas_size = (canvas_w, canvas_h)
            self.trace_view.set_background(self._bg_photo, box)
            self.draw_trace()
        finally:
            self._bg_layout_lock = False

    def _on_canvas_configure(self, event):
        if self._bg_source is None or self._bg_layout_lock:
            return
        size = (int(event.width), int(event.height))
        if size[0] < 2 or size[1] < 2 or size == self._bg_canvas_size:
            return
        self._render_background()

    def clear_gsr(self):
        self.state.gsr_history.clear()
        self.health_key = None
        self.draw_health()

    def acquisition_status(self):
        if self.state.status.get('v', 2) < 3:
            return '旧版固件：不支持抬笔移动，请烧录本包新版固件。'
        text = ('落笔：正在绘制' if self.state.active else
                '抬笔：只移动光标，已有笔画保留；再次落笔继续写')
        if self.state.status.get('v',2)<4:
            text += '。旧版固件；连续姿态和高速轨迹需烧录本包新版。'
        elif self.optical_error:
            text += '。'+self.optical_error
        elif self.optical_support is False:
            text += '。未找到新版轨迹通道，请重新烧录并重连。'
        elif not self.state.cursor_valid:
            text += '。等待有效轨迹数据。'
        if self.grip_calibrating:
            text = '请从左向右画一条横线，松开笔尖后完成校正。' + text
        elif self.grip_set:
            text += f'。握笔校正 {math.degrees(self.trace_view.grip_angle):+.1f}°'
        return text

    def zero_pose(self):
        if self.state.angles is not None:
            self.reference = transpose(rotation(*self.state.angles))
            self.reference_boot = self.state.boot
            self.pose_mode.set('相对姿态：以刚才的姿态为零；下方仍显示原始角度')

    def reset_pose(self):
        self.reference = None
        self.pose_mode.set('传感器参考坐标')

    def tick(self):
        if not self.running: return
        now = time.monotonic()
        self.ui_rate.add(now)
        if self.demo:
            self.demo_packet(now)
        else:
            deadline = time.perf_counter()+.006
            for _ in range(256):
                if time.perf_counter()>=deadline: break
                try: kind, value = self.events.get_nowait()
                except queue.Empty: break
                if kind == 'packet':
                    arrived = value.get('_rx_at', now)
                    if now-arrived>.8: continue
                    self.stream_stats.bytes(value,arrived)
                    if self.state.accept(value, arrived):
                        self.diagnostics.observe_packet(value)
                        self.rx_rate.add(arrived)
                        self.set_status(self.acquisition_status())
                elif kind == 'optical':
                    arrived=value.get('_rx_at',now)
                    self.stream_stats.optical(value,arrived)
                    if now-arrived>.20:
                        self.stream_stats.host_drops+=len(value['points'])
                        self.state.break_trace()
                        continue
                    self.state.accept_optical(value,arrived)
                    self.set_status(self.acquisition_status())
                elif kind == 'optical_support':
                    self.optical_support=value
                elif kind == 'optical_error':
                    self.optical_error=value
                elif kind == 'connected':
                    self.state = StrokeState(self.smoothing.get())
                    self.diagnostics.reset()
                    self.rx_rate = EventRate()
                    self.stream_stats = StreamStats()
                    self.optical_support = None
                    self.optical_error = ''
                    self.set_status('BLE 已连接，等待固件数据…')
                elif kind == 'diagnostic_support':
                    self.diagnostics.supported = value
                elif kind == 'diagnostic':
                    self.diagnostics.observe_fault(value)
                elif kind == 'diagnostic_error':
                    self.diagnostics.transport_error = value
                elif kind == 'battery_diagnostic_support':
                    self.diagnostics.battery.supported = value
                elif kind == 'battery_diagnostic':
                    self.diagnostics.battery.observe(value)
                elif kind == 'battery_diagnostic_error':
                    self.diagnostics.battery.error = value
                elif kind == 'connecting':
                    self.set_status(f'正在寻找并连接 {value}…')
                elif kind == 'devices':
                    self.devices = {f'{name} · {address}':address for address,name in value}
                    self.device_box.configure(values=list(self.devices))
                    self.device_var.set(next(iter(self.devices), ''))
                    self.set_status(f'找到 {len(value)} 支笔，请选择后连接。' if value else '未找到笔；确认已烧录、电池供电且蓝牙权限已开启。')
                elif kind == 'error':
                    self.state.link_lost()
                    self.rx_rate = EventRate()
                    self.set_status(value)
        self._observe_grip()
        had_data = bool(self.state.status)
        self.state.expire(now)
        if had_data and not self.state.status:
            self.set_status('数据中断，画板已清空；姿态和皮肤电恢复后续显，书写请松开再按下。')
        if self.reference is not None and self.reference_boot != self.state.boot:
            self.reset_pose()
        self.draw_trace()
        self.draw_pose()
        self.show_status()
        self.draw_health()
        if now-self.rate_updated >= .5:
            if self.state.status.get('v',2)>=4:
                acq,received,bandwidth=self.stream_stats.rates(now)
                prefix='模拟 · ' if self.demo else ''
                self.rate_text.set(f'{prefix}光学采集 {acq:.0f} Hz · 到达 {received:.0f} 点/秒 · 界面 {self.ui_rate.hz(now):.1f} 次/秒\n'
                                   f'数据 {bandwidth/1000:.1f} kB/s · 板端丢弃 {self.state.queue_drops} · 电脑过期丢弃 {self.stream_stats.host_drops}')
            else:
                self.rate_text.set(f'接收 {self.rx_rate.hz(now):.1f} 包/秒 · 界面 {self.ui_rate.hz(now):.1f} 次/秒')
            self.rate_updated = now
        # Let Tk paint during its normal idle cycle; forcing update_idletasks here
        # adds a second synchronous native paint and can halve macOS update rate.
        # Absolute deadlines also account for paint time before the next timer fires.
        self.next_frame_at += FRAME_SECONDS
        completed = time.perf_counter()
        if completed-self.next_frame_at > FRAME_SECONDS:
            self.next_frame_at = completed+FRAME_SECONDS
        wait_ms = max(1, round(1000*(self.next_frame_at-completed)))
        self.root.after(wait_ms, self.tick)

    def demo_packet(self, now):
        elapsed = now-self.demo_start
        stroke, phase = int(elapsed//8)+1, elapsed % 8
        t = int(elapsed*1e6)
        self.demo_seq += 1
        active = phase < 5
        a = phase*1.7
        # A continuous position, including a visible pen-up move to the next character.
        base_x = (stroke-1)*220
        if active:
            x,y = base_x+90*math.sin(a),60*math.sin(2*a)
        else:
            u=(phase-5)/3
            x=(1-u)*(base_x+90*math.sin(8.5))+u*(base_x+220)
            y=(1-u)*60*math.sin(17)
        packet = dict(v=4, type='data' if active else 'state', active=active,tip_edge=False,
            boot=123456, stroke=stroke, seq=self.demo_seq, t_us=t, opt_us=t,
            imu_us=t, gsr_us=(t//100000)*100000, opt_ok=True, imu_ok=True,
            opt_errors=0, x=round(x), y=round(y),
            angles=[25*math.sin(a),35*math.cos(a*.6),phase*25], imu_baud=9600,
            battery_ok=True, battery_v=3.94+.005*math.sin(elapsed), usb=False,
            charging_enabled=False, stat1=1,stat2=1, ads_ok=True,ads_error=0,
            excitation=True, gsr_ok=True, raw_off=False, gsr_state=3,
            gsr_mv=120+25*math.sin(elapsed*1.8), vex_mv=523.)
        self.state.accept(packet, now)
        point=dict(seq=self.demo_seq,t_us=t,x=round(x),y=round(y),stroke=stroke,
                   active=active,opt_ok=True,tip_edge=self.state.active!=active)
        batch=dict(boot=123456,acquired=self.demo_seq,dropped=0,points=[point])
        self.state.accept_optical(batch,now)
        self.stream_stats.optical(batch,now)
        self.diagnostics.observe_packet(packet)
        self.rx_rate.add(now)
        self.set_status('模拟数据：落笔 5 秒，抬笔移动 3 秒；笔画保留，移动不连线')

    def draw_trace(self):
        self.trace_view.draw(self.state, self.auto_fit.get(), self.swap_xy.get(),
                             self.flip_x.get(), self.flip_y.get())

    def draw_pose(self):
        c=self.pose_canvas
        w,h=max(c.winfo_width(),1),max(c.winfo_height(),1)
        key=(self.state.angles,self.axis.get(),self.reference,w,h)
        if key==self.pose_key:return
        self.pose_key=key
        c.delete('all')
        if self.state.angles is None:
            text='等待有效 IMU 姿态…'
            c.create_text(w/2,h/2,text=text,fill='#7a8a99',font=('Helvetica',16))
            self.pose_text.set('姿态持续显示；尚无新鲜角度数据，检查 JY901S 串口和输出设置。')
            return
        r=rotation(*self.state.angles)
        if self.reference:r=multiply(self.reference,r)
        size=min(w,h)*.30
        # Orthographic camera: screen right and screen up in a fixed world frame.
        right=(.7071,-.7071,0);up=(.40825,.40825,.8165)
        def project(v):
            return w/2+size*sum(a*b for a,b in zip(right,v)),h/2-size*sum(a*b for a,b in zip(up,v))
        origin=project((0,0,0))
        for axis, color, label in [((1,0,0),'#d06060','X'),((0,1,0),'#4a9f71','Y'),((0,0,1),'#4d83cc','Z')]:
            end=project(tuple(1.25*x for x in axis));c.create_line(*origin,*end,fill='#d8dfe6',dash=(4,4))
            c.create_text(end[0]+8,end[1],text=label,fill=color)
        axis_name=self.axis.get();index='XYZ'.index(axis_name[-1]);sign=-1 if axis_name.startswith('-') else 1
        along=[0.,0.,0.];along[index]=sign
        cross1=[0.,0.,0.];cross1[(index+1)%3]=1
        cross2=[0.,0.,0.];cross2[(index+2)%3]=1
        def local(z,a,b):return tuple(z*along[i]+a*cross1[i]+b*cross2[i] for i in range(3))
        rear=[local(-.85,a*.13,b*.13) for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        front=[local(.70,a*.10,b*.10) for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        tip=project(apply(r,local(1.05,0,0)))
        pr=[project(apply(r,v)) for v in rear];pf=[project(apply(r,v)) for v in front]
        for i in range(4):
            j=(i+1)%4
            c.create_polygon(*(pr[i]+pr[j]+pf[j]+pf[i]),fill=['#bcd0e4','#789cbc','#9fbcd6','#dbe8f3'][i],outline='#355979')
            c.create_polygon(*(pf[i]+pf[j]+tip),fill='#e2a34e',outline='#8f6127')
        tail=project(apply(r,local(-.85,0,0)))
        c.create_text(tip[0]+18,tip[1],text='笔尖',fill='#91601d')
        for v,color,label in [((.5,0,0),'#cb5555','x'),((0,.5,0),'#319260','y'),((0,0,.5),'#427ec5','z')]:
            end=project(apply(r,v));c.create_line(*origin,*end,fill=color,width=2,arrow='last')
            c.create_text(end[0]+7,end[1]-7,text=label,fill=color)
        roll,pitch,yaw=self.state.angles
        self.pose_text.set(f'横滚 Roll {roll:+.1f}°    俯仰 Pitch {pitch:+.1f}°    航向 Yaw {yaw:+.1f}°\n显示笔尖方向：模块 {axis_name} 轴')

    def show_status(self):
        d = self.state.status
        key=(bool(d),d.get('opt_ok'),self.state.active,self.state.angles is not None,
             d.get('imu_baud'),self.state.gaps)
        if key==self.summary_key:return
        self.summary_key=key
        if not d:
            self.measure_text.set('光学：等待　｜　IMU：等待')
            return
        optical = '正常' if d.get('opt_ok') else '未就绪 / 读数异常'
        imu = '正常' if self.state.angles is not None else '搜索中 / 数据过期'
        self.measure_text.set(f"光学：{optical}　｜　IMU：{imu}（{d.get('imu_baud', '—')}）　｜　缺口：{self.state.gaps}")

    def draw_health(self):
        d = self.state.status
        c = self.gsr_canvas
        w, h = max(c.winfo_width(), 1), max(c.winfo_height(), 1)
        fields=('battery_ok','battery_v','usb','charging_enabled','stat1','stat2',
                'gsr_ok','gsr_mv','vex_mv','ads_ok','ads_error','gsr_state','active','raw_off')
        raw = bool(d.get('raw_off'))
        detail = self.diagnostics.text(d)
        if not raw:
            detail += '\n'+self.diagnostics.battery.text(self.diagnostics.last_fault)
        key=(self.state.active,w,h,tuple(d.get(k) for k in fields),
             adc_fresh(d),self.state.gsr_device_us,len(self.state.gsr_history),detail)
        if key==self.health_key:return
        self.health_key=key
        self.diagnostic_text.set(detail)
        self.diagnostic_frame.configure(text='采集状态 · 无激励观察' if raw else '激励诊断 · 不受微动影响')
        self.gsr_title.set(('模拟数据 · ' if self.demo else '')+
                           ('无激励原始输出 · GSR_ADC（未标定）' if raw else '皮肤电输出 · GSR_ADC（未标定）'))
        self.gsr_footer.set('最近约 60 秒，松开笔尖不清空。\n'+
                            ('无激励观察值，不是两指电位差。' if raw else '仅电池供电且蓝牙连接时开启激励；USB 接入时暂停。')+
                            '\n当前为板上输出电压，尚未标定为皮肤电导或压力值。')
        c.delete('all')
        if not d:
            self.battery_text.set('— V')
            self.charge_text.set('等待 BLE 数据')
            self.gsr_text.set('— mV')
            self.vex_text.set('激励监测：—')
            self.gsr_state_text.set('未连接 / 数据中断')
        else:
            self.battery_text.set(f"{d['battery_v']:.3f} V" if d.get('battery_ok') else '— V（读数无效）')
            self.charge_text.set(charger_text(d))
            valid = gsr_display_valid(d)
            self.gsr_text.set(f"{d['gsr_mv']:.3f} mV" if valid else '— mV')
            self.vex_text.set(f"激励监测 VEX：{d['vex_mv']:.3f} mV" if adc_fresh(d) else '激励监测：ADC 无新鲜有效数据')
            labels = {0:'激励关闭，等待连接', 1:'检查关闭时的激励电压…',
                      2:'激励已开启，等待模拟电路稳定…', 3:'持续采集中：激励有效',
                      4:'USB 已接入：激励被硬件禁止', 5:'激励 / ADC 检查失败；排查后点击“重试传感器”',
                      6:'激励命令始终关闭 · 原始电压连续观察'}
            text = labels.get(d.get('gsr_state'), '状态未知')
            if raw and not valid:
                text += '\n等待新鲜 ADC 数据；不以 0 代替缺失读数。'
            if d.get('ads_error'):
                text += '\nADC 当前错误：'+{1:'I²C 通信失败',2:'配置读回不符',3:'转换超时'}.get(d['ads_error'],'未知')
            if d.get('ads_ok') and not valid and not raw:
                text += f"\n未计入曲线的原始输出：{d['gsr_mv']:.3f} mV（不能当作有效皮肤电）"
            if d.get('v',2)<4 and not self.state.active and d.get('active') and not raw:
                text = '当前笔画已因超时结束；请松开再按下'
            self.gsr_state_text.set(text)
        points = list(self.state.gsr_history)
        values = [point for point in points if point is not None]
        if not values:
            text = '等待有效皮肤电数据，无需按笔尖' if d.get('v',2)>=4 else ('等待无激励原始读数，无需按笔尖' if raw else '旧版固件：按住笔尖采集')
            c.create_text(w/2,h/2,text=text,fill='#7a8a99',font=('Helvetica',13))
            return
        t0, t1 = values[0][0], values[-1][0]
        low, high = min(v for t,v in values), max(v for t,v in values)
        margin = max((high-low)*.15, 2)
        low -= margin; high += margin
        coords = []
        def draw_segment():
            if len(coords) >= 4:
                c.create_line(*coords,fill='#309881',width=2,tags='gsr_line')
            elif len(coords) == 2:
                x,y=coords;c.create_oval(x-2,y-2,x+2,y+2,fill='#309881',outline='',tags='gsr_dot')
        for point in points:
            if point is None:
                draw_segment();coords=[];continue
            t,v = point
            coords.extend((45+(w-60)*(t-t0)/max(.1,t1-t0), h-25-(h-45)*(v-low)/(high-low)))
        draw_segment()
        c.create_text(5,5,anchor='nw',text=f'{high:.1f} mV',fill=TEXT)
        c.create_text(5,h-4,anchor='sw',text=f'{low:.1f} mV',fill=TEXT)
        c.create_text(w-5,h-4,anchor='se',text=f'{t1-t0:.1f} s',fill=TEXT)

    def close(self):
        self.running=False
        if self.worker:
            self.worker.stop()
            self.worker.join(timeout=.5)
        self.root.destroy()

def main():
    parser=argparse.ArgumentParser(description='手写笔 BLE 三窗口显示')
    parser.add_argument('--address',help='指定扫描得到的设备地址；macOS 使用系统 UUID')
    parser.add_argument('--demo',action='store_true',help='不用硬件的模拟演示')
    parser.add_argument('--scan',action='store_true',help='只扫描并打印设备列表')
    args=parser.parse_args()
    if args.scan:
        for device,name in asyncio.run(discover_pens()):
            print(name, device.address)
        return
    app=PenApp(args.address,args.demo)
    app.root.mainloop()

if __name__=='__main__':main()
