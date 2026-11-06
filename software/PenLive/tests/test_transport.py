import asyncio
import queue
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ble_transport import BleWorker
from pen_protocol import NOTIFY_UUID,CONTROL_UUID
from gsr_diagnostic import DIAGNOSTIC_UUID
from battery_diagnostic import BATTERY_DIAGNOSTIC_UUID, decode_battery_diagnostic
from test_protocol import wire,fragments

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_results(self):
        out=queue.Queue();w=BleWorker(None,out,scan_only=True)
        with patch('ble_transport.discover_pens',AsyncMock(return_value=[(SimpleNamespace(address='A'),'SmartPen-R26')])):
            await w.work()
        self.assertEqual(out.get(),('devices',[('A','SmartPen-R26')]))

    async def test_ambiguous_device_does_not_connect(self):
        out=queue.Queue();w=BleWorker(None,out)
        found=[(SimpleNamespace(address=x),'SmartPen-R26') for x in ('A','B')]
        with patch('ble_transport.discover_pens',AsyncMock(return_value=found)),patch('bleak.BleakClient') as client:
            await w.work()
        self.assertFalse(client.called)
        self.assertEqual(out.get()[0],'connecting')
        self.assertIn('多支',out.get()[1])

    async def test_subscription_packets_and_retry_command(self):
        out=queue.Queue();w=BleWorker('A',out);w.commands.put(b'i')
        writes=[];exited=[]
        class Client:
            is_connected=True
            def __init__(self,device,timeout):self.device=device
            async def __aenter__(self):return self
            async def __aexit__(self,*args):exited.append(True)
            async def start_notify(self,uuid,callback):
                self_uuid=uuid
                assert self_uuid==NOTIFY_UUID
                for f in fragments(wire()):callback(None,f)
            async def write_gatt_char(self,uuid,command,response):
                writes.append((uuid,command,response));w.stopped.set()
        with patch('ble_transport.discover_pens',AsyncMock(return_value=[(SimpleNamespace(address='A'),'SmartPen-R26')])),patch('bleak.BleakClient',Client):
            await asyncio.wait_for(w.work(),2)
        events=[]
        while not out.empty():events.append(out.get())
        self.assertEqual([k for k,v in events],['connecting','connected','packet','optical_support','diagnostic_support','battery_diagnostic_support'])
        self.assertTrue(events[2][1]['active'])
        self.assertEqual(events[-2],('diagnostic_support',False))
        self.assertEqual(events[-1],('battery_diagnostic_support',False))
        self.assertEqual(writes,[(CONTROL_UUID,b'i',True)])
        self.assertTrue(exited)

    async def test_optional_diagnostic_notification_and_read(self):
        out=queue.Queue();w=BleWorker('A',out)
        fixture=bytes.fromhex((Path(__file__).parents[1]/'reports/cpp_diagnostic.hex').read_text())
        class Client:
            services=SimpleNamespace(get_characteristic=lambda uuid: object() if uuid==DIAGNOSTIC_UUID else None)
            async def start_notify(self,uuid,callback):
                assert uuid==DIAGNOSTIC_UUID
                callback(None,fixture)
            async def read_gatt_char(self,uuid):
                assert uuid==DIAGNOSTIC_UUID
                return fixture
        await w.subscribe_diagnostics(Client())
        self.assertEqual(out.get(),('diagnostic_support',True))
        for _ in range(2):
            kind,p=out.get();self.assertEqual(kind,'diagnostic')
            self.assertEqual((p['reason'],p['phase'],p['vex_mv']),(8,2,1.0))

    async def test_diagnostic_failure_keeps_main_stream_and_command_alive(self):
        for failure in ('subscription','read'):
            with self.subTest(failure=failure):
                out=queue.Queue();w=BleWorker('A',out);w.commands.put(b'i')
                writes=[]
                class Client:
                    is_connected=True
                    services=SimpleNamespace(get_characteristic=lambda uuid: object())
                    def __init__(self,*args,**kw):pass
                    async def __aenter__(self):return self
                    async def __aexit__(self,*args):pass
                    async def start_notify(self,uuid,callback):
                        if uuid==NOTIFY_UUID:
                            for f in fragments(wire()):callback(None,f)
                        elif failure=='subscription':
                            raise RuntimeError('test subscription failure')
                    async def read_gatt_char(self,uuid):raise RuntimeError('test read failure')
                    async def write_gatt_char(self,uuid,command,response):
                        writes.append(command);w.stopped.set()
                with patch('ble_transport.discover_pens',AsyncMock(return_value=[(SimpleNamespace(address='A'),'SmartPen-R26')])),patch('bleak.BleakClient',Client):
                    await asyncio.wait_for(w.work(),2)
                events=list(out.queue)
                self.assertIn('packet',[k for k,v in events])
                self.assertIn('diagnostic_error',[k for k,v in events])
                self.assertNotIn('error',[k for k,v in events])
                self.assertEqual(writes,[b'i'])

    async def test_optional_battery_characteristic(self):
        out=queue.Queue();w=BleWorker('A',out)
        fixture=bytes.fromhex((Path(__file__).parents[1]/'reports/cpp_battery.hex').read_text())
        class Client:
            services=SimpleNamespace(get_characteristic=lambda uuid: object() if uuid==BATTERY_DIAGNOSTIC_UUID else None)
            async def start_notify(self,uuid,callback):
                assert uuid==BATTERY_DIAGNOSTIC_UUID;callback(None,fixture)
            async def read_gatt_char(self,uuid):return fixture
        await w.subscribe_diagnostics(Client(),BATTERY_DIAGNOSTIC_UUID,decode_battery_diagnostic,'battery_diagnostic')
        self.assertEqual(out.get(),('battery_diagnostic_support',True))
        for _ in range(2):
            kind,p=out.get();self.assertEqual(kind,'battery_diagnostic')
            self.assertEqual(p['minimum_v'],3.740)

    async def test_optical_subscribe_decode_and_byte_counter(self):
        from test_continuous import batch, point, optical_wire, optical_fragments
        from optical_protocol import OPTICAL_UUID
        out=queue.Queue();w=BleWorker('A',out)
        data=optical_fragments(optical_wire(batch(point(1),point(2,10))),14)
        class Client:
            services=SimpleNamespace(get_characteristic=lambda uuid: object() if uuid==OPTICAL_UUID else None)
            async def start_notify(self,uuid,callback):
                assert uuid==OPTICAL_UUID
                for f in data:callback(None,f)
        await w.subscribe_optical(Client())
        kind,p=out.get();self.assertEqual(kind,'optical')
        self.assertEqual(len(p['points']),2)
        self.assertEqual(p['_wire_bytes_total'],sum(map(len,data)))
        self.assertGreater(p['_rx_at'],0)
        self.assertEqual(out.get(),('optical_support',True))

    async def test_optical_failure_visible_and_full_queue_stops_stream(self):
        out=queue.Queue();w=BleWorker('A',out)
        class Client:
            services=SimpleNamespace(get_characteristic=lambda uuid: object())
            async def start_notify(self,*args):raise RuntimeError('no subscription')
        await w.subscribe_optical(Client())
        self.assertEqual(out.get()[0],'optical_error')
        out=queue.Queue(maxsize=1);w=BleWorker('A',out)
        w.emit(('packet',{}));w.emit(('packet',{}))
        self.assertTrue(w.stopped.is_set());self.assertEqual(out.get()[0],'error')

if __name__=='__main__':unittest.main()
