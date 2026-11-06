"""Real Tk UI with decoded OFF-only packets; no BLE device or upload."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pen_live import PenApp
from test_raw_off import sample
from pen_protocol import RAW_OFF, ADS, BAT, USB

app=PenApp(demo=False)
for timer in app.root.tk.call('after','info'): app.root.after_cancel(timer)
app.root.update()

def send(p):
    assert app.state.accept(p, 1+p['seq']*.1)
    app.diagnostics.observe_packet(p)
    app.draw_health();app.root.update_idletasks()

send(sample(1));send(sample(2,gsr=1234))
assert app.gsr_text.get()=='154.250 mV'
assert not app.state.active
assert len(app.gsr_canvas.find_withtag('gsr_line'))==1
assert '无激励原始输出' in app.gsr_title.get()
send(sample(3,True,1));send(sample(4,False,1))
assert len(app.state.gsr_history)==4
send(sample(5,stroke=1,flags=RAW_OFF|BAT,ae=1))
assert app.gsr_text.get()=='— mV'
assert 'ADC 异常' in app.diagnostic_text.get()
send(sample(6,stroke=1));send(sample(7,stroke=1))
assert len(app.gsr_canvas.find_withtag('gsr_line'))==2
send(sample(8,stroke=1,gsr_us=100000))
assert app.gsr_text.get()=='— mV'
send(sample(9,stroke=1,flags=RAW_OFF|ADS|BAT|USB,vex=800))
assert '超过 ±50 mV' in app.diagnostic_text.get()
assert '取下指套' in app.diagnostic_text.get()
app.copy_button.invoke()
assert 'R26 无激励原始电压观察' in app.root.clipboard_get()
assert 'excitation_command=0' in app.root.clipboard_get()
app.clear_gsr_button.invoke();assert not app.state.gsr_history
send(sample(10,stroke=1));assert len(app.state.gsr_history)==1
assert app.gsr_canvas.find_withtag('gsr_dot')
for widget in (app.diagnostic_label,app.copy_button,app.clear_gsr_button,app.gsr_canvas,app.gsr_footer_label):
    assert widget.winfo_ismapped()
    assert widget.winfo_rooty()+widget.winfo_height() <= app.health.winfo_rooty()+app.health.winfo_height()
assert app.gsr_canvas.winfo_height()>=50
app.state.link_lost();app.draw_health()
assert app.gsr_text.get()=='— mV'
assert not app.gsr_canvas.find_withtag('gsr_line')
app.close()
print('PASS: native Tk OFF raw values without tip press, persistent curve, gaps, ADC errors/staleness, VEX warning, clipboard, clear and disconnect.')
