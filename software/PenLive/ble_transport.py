"""BLE I/O on an asyncio worker. All Tk operations stay on the main thread."""
import asyncio
import queue
import threading
import time
from pen_protocol import BleDecoder, SERVICE_UUID, NOTIFY_UUID, CONTROL_UUID
from optical_protocol import OPTICAL_UUID, OpticalDecoder
from gsr_diagnostic import DIAGNOSTIC_UUID, decode_diagnostic
from battery_diagnostic import BATTERY_DIAGNOSTIC_UUID, decode_battery_diagnostic

async def discover_pens():
    from bleak import BleakScanner
    found = await BleakScanner.discover(timeout=5, return_adv=True)
    pens = []
    for device, adv in found.values():
        name = adv.local_name or device.name or ''
        if name == 'SmartPen-R26' or SERVICE_UUID in [s.lower() for s in adv.service_uuids]:
            pens.append((device, name or 'SmartPen-R26'))
    return pens

class BleWorker(threading.Thread):
    def __init__(self, address, out, scan_only=False):
        super().__init__(daemon=True)
        self.address, self.out, self.scan_only = address, out, scan_only
        self.stopped = threading.Event()
        self.commands = queue.Queue()
        self.loop = self.task = None
        self.wire_bytes = 0

    def emit(self, item):
        try:
            self.out.put_nowait(item)
        except queue.Full:
            self.stop()
            while not self.out.empty():
                try: self.out.get_nowait()
                except queue.Empty: break
            self.out.put_nowait(('error', '接收缓冲已满，已断开以避免显示积压轨迹；请重新连接。'))

    def stop(self):
        self.stopped.set()
        loop, task = self.loop, self.task
        if loop and task and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass

    async def subscribe_diagnostics(self, client, uuid=DIAGNOSTIC_UUID,
                                    decode=decode_diagnostic, event='diagnostic'):
        # Optional service extension: never disconnect a working main data stream.
        try:
            services = getattr(client, 'services', None)
            present = services is not None and services.get_characteristic(uuid) is not None
            self.emit((event+'_support', present))
            if not present:
                return
            def received(_characteristic, data):
                packet = decode(data)
                if packet is not None:
                    self.emit((event, packet))
                else:
                    self.emit((event+'_error', '诊断快照校验失败，等待下一份数据。'))
            await asyncio.wait_for(client.start_notify(uuid, received), 5)
            # Obtain an already latched fault without waiting for another press.
            received(None, await asyncio.wait_for(client.read_gatt_char(uuid), 5))
        except Exception as exc:
            self.emit((event+'_error', f'诊断读取或订阅异常：{exc}；主数据采集继续。'))

    async def subscribe_optical(self, client):
        services = getattr(client, 'services', None)
        present = services is not None and services.get_characteristic(OPTICAL_UUID) is not None
        if not present:
            self.emit(('optical_support', False))
            return
        decoder = OpticalDecoder()
        def received(_characteristic, data):
            self.wire_bytes += len(data)
            packet = decoder.feed(data)
            if packet is not None:
                packet['_rx_at'] = time.monotonic()
                packet['_wire_bytes_total'] = self.wire_bytes
                self.emit(('optical', packet))
        try:
            await asyncio.wait_for(client.start_notify(OPTICAL_UUID, received), 5)
            self.emit(('optical_support', True))
        except Exception as exc:
            self.emit(('optical_error', f'轨迹通道订阅失败：{exc}；请断开后重连。'))

    async def work(self):
        from bleak import BleakClient
        if self.scan_only:
            pens = await discover_pens()
            self.emit(('devices', [(d.address, name) for d, name in pens]))
            return
        while not self.stopped.is_set():
            try:
                self.emit(('connecting', self.address or 'SmartPen-R26'))
                pens = await discover_pens()
                matches = [d for d, name in pens if not self.address or d.address.lower() == self.address.lower()]
                if len(matches) > 1:
                    self.emit(('error', '发现多支笔，请先扫描并选择具体设备。'))
                    return
                if not matches:
                    raise RuntimeError('未找到目标笔，请确认已烧录、电池供电且没有连接其他程序')
                self.address = matches[0].address  # Reconnect only to the selected pen.
                decoder = BleDecoder()
                self.wire_bytes = 0
                async with BleakClient(matches[0], timeout=12) as client:
                    self.emit(('connected', matches[0].address))
                    def received(_characteristic, data):
                        self.wire_bytes += len(data)
                        packet = decoder.feed(data)
                        if packet is not None:
                            packet['_rx_at'] = time.monotonic()
                            packet['_wire_bytes_total'] = self.wire_bytes
                            self.emit(('packet', packet))
                    await client.start_notify(NOTIFY_UUID, received)
                    await self.subscribe_optical(client)
                    await self.subscribe_diagnostics(client)
                    await self.subscribe_diagnostics(client, BATTERY_DIAGNOSTIC_UUID,
                                                     decode_battery_diagnostic, 'battery_diagnostic')
                    while client.is_connected and not self.stopped.is_set():
                        try:
                            command = self.commands.get_nowait()
                        except queue.Empty:
                            command = None
                        if command:
                            await client.write_gatt_char(CONTROL_UUID, command, response=True)
                        await asyncio.sleep(.02)
                    if not self.stopped.is_set():
                        self.emit(('error', 'BLE 已断开，正在重连…'))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not self.stopped.is_set():
                    self.emit(('error', f'蓝牙连接失败：{exc}；3 秒后重试'))
            if not self.stopped.is_set():
                await asyncio.sleep(3)

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            if self.stopped.is_set():
                return
            self.task = self.loop.create_task(self.work())
            self.loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not self.stopped.is_set():
                self.emit(('error', f'蓝牙不可用：{exc}。检查依赖、蓝牙开关和系统蓝牙权限。'))
        finally:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
