from pathlib import Path
import json,math
import cadquery as cq
R=Path(__file__).resolve().parents[1]
parts={p.stem:cq.importers.importStep(str(p)).val() for p in (R/'cad').glob('[0-9]*.step') if not p.stem.startswith(('10_','11_'))}
P=json.loads((R/'source/parameters.json').read_text())
def box(a,b,c,d,e,f):return cq.Solid.makeBox(b-a,d-c,f-e,cq.Vector(a,c,e))
def pp(s):return s.rotate((0,0,0),(0,1,0),55)
def pt(u,v,w):a=math.radians(55);return (u*math.cos(a)+w*math.sin(a),v,-u*math.sin(a)+w*math.cos(a))
out={};hits=[]
# Soldered-in electronics proxies can be lowered into the opened base.
for dz in (0,1,3,6,12,20):
 for n in ('20_battery_dummy_36x12x6','22_rear_board_dummy_75x24'):
  v=parts[n].translate((0,0,dz)).intersect(parts['03_rear_base']).Volume()
  if v>.002:hits.append({'part':n,'vertical_insertion_height':dz,'overlap':v})
out['vertical_insertion_collisions']=hits
# Nominal straight five-wire internal bundle; routed external portion remains flexible.
wire=box(31.5,79.5,4.4,5.4,-2.5,2.5);hits=[]
for n in ('01_one_piece_barrel','05_switch_carrier_lower','06_switch_carrier_upper'):
 v=wire.intersect(parts[n]).Volume()
 if v>.002:hits.append({'part':n,'overlap':v})
out['barrel_wire_channel_collisions']=hits;out['wire_bundle_section_mm']=[1.0,5.0]
# Keep the actual mated-plug and bend-space volumes free of printed shells.
data=json.loads((R/'rear_board_mechanical_input.json').read_text());hits=[]
for h in data['internal_harness']:
 a=h['suggested_wire_keepout_bbox_mm'];s=box(a[0]+P['pcb_origin_x'],a[3]+P['pcb_origin_x'],a[1],a[4],a[2]-.5,a[5]-.5)
 for n in ('03_rear_base','04_press_release_cover'):
  v=parts[n].intersect(s).Volume()
  if v>.002:hits.append({'connector':h['designator'],'part':n,'overlap':v})
out['rear_wire_keepout_collisions']=hits
# Serial battery layout: representative optical harness travels beside battery.
# These overlapping boxes describe a routing corridor, not a manufactured cable.
route=[]
def v(x,y,z):return cq.Vector(x,y,z)
q=3/math.sqrt(2)
for z in (-2.,-1.,0.,1.,2.):
 edges=[cq.Edge.makeLine(v(36,4.9,z),v(75.5,4.9,z)),
        cq.Edge.makeThreePointArc(v(75.5,4.9,z),v(75.5+q,7.9-q,z),v(78.5,7.9,z)),
        cq.Edge.makeThreePointArc(v(78.5,7.9,z),v(81.5-q,7.9+q,z),v(81.5,10.9,z)),
        cq.Edge.makeLine(v(81.5,10.9,z),v(119.5,10.9,z)),
        cq.Edge.makeThreePointArc(v(119.5,10.9,z),v(119.5+q,7.9+q,z),v(122.5,7.9,z)),
        cq.Edge.makeLine(v(122.5,7.9,z),v(122.5,3.5,z)),
        cq.Edge.makeThreePointArc(v(122.5,3.5,z),v(125.5-q,3.5-q,z),v(125.5,.5,z)),
        cq.Edge.makeLine(v(125.5,.5,z),v(127,.5,z))]
 wire=cq.Wire.assembleEdges(edges)
 route.append(cq.Workplane('YZ',origin=(36,4.9,z)).circle(.5).sweep(cq.Workplane(obj=wire),isFrenet=True).val())
hits=[]
for i,seg in enumerate(route):
 for n in ('01_one_piece_barrel','05_switch_carrier_lower','06_switch_carrier_upper','03_rear_base','04_press_release_cover','20_battery_dummy_36x12x6','22_rear_board_dummy_75x24'):
  v=parts[n].intersect(seg).Volume()
  if v>.002:hits.append({'segment':i,'part':n,'overlap':v})
out['serial_harness_route_collisions']=hits
out['serial_harness_route_note']='Five actual 1.0mm OD swept wire solids; 3mm centerline bend radius, beside battery to the board front. Final JST fan-out not modeled; cable manufacturer bend limit unknown.'
out['wire_centerline_bend_radius_mm']=3.0
cq.exporters.export(cq.Compound.makeCompound(route),str(R/'cad/reference_wire_route_NOT_FOR_PRINT.step'))
# Read-out geometry: screw-out and refill pressure travel use existing thread phase.
hits=[]
for deg in (0,45,90,180,360,720,1440,1800):
 s=parts['02_threaded_nose'].rotate((0,0,0),(1,0,0),-deg).translate((-1.6*deg/360,0,0))
 for n in ('01_one_piece_barrel','08_optical_cassette','09_optical_lid'):
  v=s.intersect(parts[n]).Volume()
  if v>.002:hits.append({'deg':deg,'part':n,'overlap':v})
out['thread_removal_collisions']=hits
hits=[]
for dx in (0,.15,.30):
 s=parts['07_refill_plunger'].translate((dx,0,0))
 for n in ('01_one_piece_barrel','05_switch_carrier_lower','06_switch_carrier_upper'):
  v=s.intersect(parts[n]).Volume()
  if v>.002:hits.append({'dx':dx,'part':n,'overlap':v})
out['plunger_motion_collisions']=hits
# Hard stop should engage just beyond 0.30mm, before force can pass through
# further geometric travel. This is not a guarantee of real switch overtravel.
overlap=sum(parts['07_refill_plunger'].translate((.31,0,0)).intersect(parts[n]).Volume() for n in ('05_switch_carrier_lower','06_switch_carrier_upper'))
assert overlap>.01, ('missing plunger hard stop',overlap)
out['plunger_hard_stop_overlap_at_0p31_mm3']=overlap
# All three plungers preserve the same disk/stop, only tip length differs.
out['plunger_options_mm']=[3.2,3.4,3.6]
pivot=pt(3,17.5,6.5+7.8);end=(pivot[0],pivot[1]+1,pivot[2]);hits=[]
for a in (-7,0,7):
 for h in (-1,0,1):
  for n in ('08_optical_cassette','09_optical_lid'):
   s=parts[n].rotate(pivot,end,a).translate((h*math.sin(math.radians(55)),0,h*math.cos(math.radians(55))))
   for fixed in ('01_one_piece_barrel','02_threaded_nose'):
    v=s.intersect(parts[fixed]).Volume()
    if v>.002:hits.append({'moving':n,'fixed':fixed,'angle':a,'height':h,'overlap':v})
out['optical_adjustment_collisions']=hits
# The shell window remains open along the central sight line, no added glazing.
ray=pp(box(1.25,4.75,15.9,19.1,0,7.49));hits=[]
for n,s in parts.items():
 if n.startswith('2'):continue
 v=s.intersect(ray).Volume()
 if v>.002:hits.append({'part':n,'overlap':v})
out['central_optical_path_collisions']=hits
out['scope']='CAD ideal solids only; no physical printing/electronics/optical tracking validation'
(R/'reports/interface_validation.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps(out,indent=2,ensure_ascii=False));assert not any(v for k,v in out.items() if k.endswith('_collisions'))
