"""Mechanical v0.5, mm: 36x12x6 battery, R26 rear PCB, EVQQ2B03W switch,
and separated five-wire duct. Exact refill and optical stack remain unmeasured.
Run with Python 3.12, CadQuery 2.8, trimesh 5.1, numpy.
"""
from pathlib import Path
import math,json,itertools,zipfile
import xml.etree.ElementTree as ET
import cadquery as cq
import numpy as np
import trimesh

R=Path(__file__).resolve().parents[1]
for d in ('cad','stl','reports','previews'): (R/d).mkdir(exist_ok=True)
P={'version':'v0.5','units':'mm','length':206,'grip_diameter':11,
   'rear_width':28.4,'rear_height':14,'refill_body_diameter_assumed':6.0,
   'refill_length_assumed':67,'body_bore_diameter':8,'front_guide_diameter':6.6,'tip_exit_diameter':3.2,
   'mid_wall_nominal':1.5,'wire_groove_min_wall':1.2,'nose_max_diameter':13,
   'rear_seat_outer_diameter':13,'male_thread_part':'01_one_piece_barrel',
   'female_thread_part':'02_threaded_nose','male_root_wall':1.2,
   'thread_type':'custom right-handed trapezoidal; not ISO metric',
   'thread_pitch':1.6,'thread_major_diameter':10,'thread_root_diameter':9,
   'thread_radial_clearance':.25,'thread_axial_flank_allowance':.20,
   'nose_socket_min_wall':1.25,'snap_beam_length':14,'snap_beam_thickness':.9,
   'snap_required_deflection_nominal':.65,'snap_effective_free_length':12.8,'snap_strain_beam_estimate':1.5*.9*.65/(12.8**2),
   'window_opening':[9.8,7.0],'window_gap':4.1,'optical_Z0':None,
   'optical_center_uv':[3,11.7],'optical_axis_pen_angle':35,
   'refill_note':'User: ordinary M&G black gel refill; exact SKU and mechanical dimensions unknown.'}
(R/'source/parameters.json').write_text(json.dumps(P,ensure_ascii=False,indent=2))
def box(a,b,c,d,e,f): return cq.Solid.makeBox(b-a,d-c,f-e,cq.Vector(a,c,e))
def cyl(r,h,p,axis=(1,0,0)): return cq.Solid.makeCylinder(r,h,cq.Vector(*p),cq.Vector(*axis))
def union(*s):return s[0].fuse(*s[1:]).clean() if len(s)>1 else s[0]
def cut(s,*t):return s.cut(*t).clean()
def rr(a,b,w,h,r):return cq.Workplane('YZ').rect(w,h).extrude(b-a).edges('|X').fillet(r).val().translate((a,0,0))
def pp(s):return s.rotate((0,0,0),(0,1,0),55)
def reflect(s):return s.mirror('XZ')
def yzprism(x0,x1,pts):
 wire=cq.Wire.makePolygon([cq.Vector(x0,y,z) for y,z in pts]+[cq.Vector(x0,*pts[0])])
 return cq.Solid.extrudeLinear(wire,[],cq.Vector(x1-x0,0,0))
def thread_profile(female=False):
 # A true helical swept trapezoid, with the same phase for both mating parts.
 pts=[(4.45,-.65),(5.0,-.10),(5.0,.10),(4.45,.65)]
 if female:pts=[(4.70,-.78),(5.25,-.30),(5.25,.30),(4.70,.78)]
 h=cq.Wire.makeHelix(1.6,9.6,4.5)
 shape=cq.Workplane('XZ').polyline(pts).close().sweep(cq.Workplane(obj=h),isFrenet=True).val()
 return shape.translate((0,0,13.05)).rotate((0,0,0),(0,1,0),90)

print('Building mating helical threads...',flush=True)
male_thread=thread_profile().intersect(box(14,22,-8,8,-8,8)).translate((.5,0,0))
female_cut=thread_profile(True).translate((.5,0,0)).intersect(box(13.9,22.7,-8,8,-8,8))
# Female cap surrounds the male barrel neck, as on a conventional gel pen.
nose=union(cq.Solid.makeCone(2.8,6.5,9.5,cq.Vector(4.5,0,0),cq.Vector(1,0,0)),cyl(6.5,8.5,(14,0,0)))
nose_tools=[cyl(1.6,3.2,(4.4,0,0)),
         cq.Solid.makeCone(1.6,3.3,3,cq.Vector(7.5,0,0),cq.Vector(1,0,0)),cyl(3.3,12.1,(10.5,0,0)),
         cyl(4.75,8.7,(13.9,0,0)),female_cut,
         cq.Solid.makeCone(4.75,5.3,.8,cq.Vector(21.71,0,0),cq.Vector(1,0,0))]
for tool in nose_tools:nose=cut(nose,tool)

# Male neck guides the refill radially; it must not clamp its axial motion.
neck=union(cyl(4.5,8,(14.5,0,0)),male_thread)
# The female mouth provides the entry chamfer; keep the swept male crest
# intact to avoid sliver faces at its first turn.
assert len(neck.Solids())==1 and neck.Volume()>math.pi*4.5**2*8+30,'Male thread lost or disconnected'
# Only the thread shoulder and switch seat are locally enlarged.
barrel=union(neck,cyl(6.5,1.2,(22.5,0,0)),
             cq.Solid.makeCone(6.5,5.5,4.3,cq.Vector(23.7,0,0),cq.Vector(1,0,0)),
             cyl(5.5,32,(28,0,0)),
             cq.Solid.makeCone(5.5,6.5,4,cq.Vector(60,0,0),cq.Vector(1,0,0)),
             cyl(6.5,5,(64,0,0)),cyl(6.2,7,(69,0,0)),rr(72,74,14.0,13.6,.7))
barrel=cut(barrel,cyl(3.3,62,(14.4,0,0)),
           cq.Solid.makeCone(3.3,4,3,cq.Vector(23,0,0),cq.Vector(1,0,0)),
           cyl(4,38.1,(26,0,0)),cyl(5.4,12.2,(64,0,0)))
# A local raised rib provides a CLOSED duct separated from the refill by
# 0.8mm of PLA. Five <=1.0mm OD wires fit side-by-side, not as a round bundle.
rib=rr(28,76,3.3,7.9,.7).translate((0,5.1,0))
barrel=union(barrel,rib)
wire_duct=box(29.5,76.2,4.25,5.55,-2.75,2.75)
wire_inlet=box(28.9,36.0,4.25,7.5,-2.75,2.75)
barrel=cut(barrel,wire_duct,wire_inlet,
           cq.Solid.makeCone(3.55,3.3,.5,cq.Vector(14.49,0,0),cq.Vector(1,0,0)))

# Purchased optical module. Only its 14 x 15 outline is vendor-confirmed.
cu,cv,g=3.,17.5,6.5
ou,ov=15.6,14.6
u0,u1=cu-ou/2-1.6,cu+ou/2+1.6
v0,v1=cv-ov/2-1.6,cv+ov/2+1.6
seat=g+2.0; pcb_t=1.6; lid_z=g+6.3
pod=cut(box(u0,u1,v0,v1,g,lid_z),box(cu-ou/2,cu+ou/2,cv-ov/2,cv+ov/2,g-.1,lid_z+.1))
for u in (cu-ou/2,cu+ou/2-1.0):
 for v in (cv-ov/2,cv+ov/2-1.0):pod=union(pod,box(u,u+1.0,v,v+1.0,g+1.0,seat))
pivot=g+7.8;ears=(u0-2.7,u1+2.7)
for u in ears:
 pod=union(pod,box(u-2.7,u+2.7,v1-2.6,v1,g+3.0,pivot+2.7))
 pod=cut(pod,cyl(1.1,3,(u,v1-2.7,pivot),(0,1,0)))
 # M2 hex nut clearance, across flats 4.3, depth1.8, open from inner side.
 hv=[(u+2.48*math.cos(k*math.pi/3),pivot+2.48*math.sin(k*math.pi/3)) for k in range(6)]
 wire=cq.Wire.makePolygon([cq.Vector(x,v1-2.7,z) for x,z in hv]+[cq.Vector(hv[0][0],v1-2.7,hv[0][1])])
 pod=cut(pod,cq.Solid.extrudeLinear(wire,[],cq.Vector(0,1.8,0)))
lugs=(u0-1.8,u1+1.8)
for u in lugs:
 pod=union(pod,box(u-1.8,u+1.8,cv-1.8,cv+1.8,g+3,lid_z))
 pod=cut(pod,cyl(.65,3.2,(u,cv,lid_z-2.8),(0,0,1)))
# Wires leave the header end (-u); broad open channel allows flat five-core lead.
pod=cut(pod,box(u0-.1,cu-ou/2+.1,cv-6.8,cv+6.8,seat+.2,lid_z-1.3))
oplid=box(u0,u1,v0,v1,lid_z,lid_z+1.4)
for u in lugs:
 oplid=union(oplid,box(u-1.8,u+1.8,cv-1.8,cv+1.8,lid_z,lid_z+1.4))
 oplid=cut(oplid,cyl(.95,1.7,(u,cv,lid_z-.1),(0,0,1)))
# Back-face edge pressers leave .25 nominal gap for thin compliant tape.
for u in (cu-6.6,cu+5.4):
 for v in (cv-5.9,cv+4.7):oplid=union(oplid,box(u,u+1.2,v,v+1.2,seat+pcb_t+.25,lid_z+.1))
by0,by1=v1+.3,v1+2.7
def slot_y(u,w0,w1,r,a,b):return union(box(u-r,u+r,a,b,w0,w1),cyl(r,b-a,(u,a,w0),(0,1,0)),cyl(r,b-a,(u,a,w1),(0,1,0)))
br=[]
for u in ears:br.append(cut(box(u-2.7,u+2.7,by0,by1,pivot-5.1,pivot+6),slot_y(u,pivot-2.6,pivot+2.6,1.3,by0-.1,by1+.1)))
# Bridge enters tube beyond the screw-off nose at x~32mm.
br.extend([box(ears[0]-2.7,26,by0,by1,pivot+6,pivot+8.4),box(16,21,3.8,by1,pivot+6,pivot+8.4)])
bracket=cut(pp(union(*br)),cyl(5.2,80,(0,0,0)))
barrel=union(barrel,bracket)
barrel=cut(barrel,wire_duct,wire_inlet)
pod,oplid=pp(pod),pp(oplid)

# Serial layout selected by user: battery forward, board aft, no stacking.
BX=128.;TAIL=206.;W=28.4
BAT_X=84.;BAT_L=36.;BAT_Z=-3.9;FLOOR=-4.4;ROOF=8.0
# A short tapered neck captures the original antirotation barrel collar.
def cross_wire(x,w,h,cz,r):return rr(x,x+.1,w,h,r).translate((0,0,cz)).Faces()[0]
# Rear neck sampled wall minimum is checked independently on exported STEP.
# The rear body stays 14mm high; the local neck reaches Z=-8.2..+8.2.
sections=[rr(69,69.1,16.4,16.4,1.8),
          rr(71.5,71.6,18.8,16.4,1.8),
          rr(76.2,76.3,25.5,16.4,1.8),
          rr(78,78.1,W,14,1.8).translate((0,0,1))]
wires=[min(s.Faces(),key=lambda f:f.Center().x).outerWire() for s in sections]
outer=union(cq.Solid.makeLoft(wires,True),rr(78,TAIL,W,14,1.8).translate((0,0,1)))
inner=union(rr(78,TAIL-1.6,25.2,10.8,.6).translate((0,0,1)),cyl(6.4,7.2,(68.9,0,0)),rr(71.8,74.2,14.4,14.0,.8),cyl(3.5,4.2,(75.9,0,0)))
# Fan-out relief connects the barrel wire slot to the battery-side corridor.
housing=cut(outer,inner,box(68.9,76.2,3.25,7.0,-4.2,4.2),
            box(75.9,79.6,4.15,5.7,-2.85,2.85),
            box(76.2,81.9,4.15,11.6,-2.85,2.85))
lo=housing.intersect(box(68,TAIL+1,-30,30,-13,0)).clean();hi=housing.intersect(box(68,TAIL+1,-30,30,0,10)).clean()
# Battery cradle: .8mm each end / .5mm each side, .5mm soft pad below.
# The battery is ahead of the PCB, with free wire corridors on both sides.
for x in (BAT_X-1.9,BAT_X+BAT_L+.8):lo=union(lo,box(x,x+1.1,-7.7,7.7,FLOOR-.1,1.5))
for ya,yb in ((-7.7,-6.5),(6.5,7.7)):lo=union(lo,box(BAT_X-.8,BAT_X+BAT_L+.8,ya,yb,FLOOR-.1,1.5))
for x in (BAT_X+3.5,BAT_X+BAT_L-5.5):
 for ya,yb in ((-8.8,-7.6),(7.6,8.8)):lo=cut(lo,box(x,x+2,ya,yb,-6.1,BAT_Z))
# Underside edge supports; narrow PCB edge contact, no contact with device bodies.
for x in (BX+20,BX+65):
 for ya,yb in ((-12.6,-11.1),(11.1,12.6)):lo=union(lo,box(x,x+2.6,ya,yb,FLOOR-.1,-.5))
# PCB fore/aft edge stops, above connector level and below top devices.
for ya,yb in ((-4.9,-4.2),(5.0,5.7)):lo=union(lo,box(BX-1.5,BX-.3,ya,yb,FLOOR-.1,.0))
# Rear restraint touches only PCB cut edge, not extending antenna module.
for ya,yb in ((-11.8,-9.5),(9.5,11.8)):lo=union(lo,box(BX+70.25,BX+71.4,ya,yb,FLOOR-.1,.0))
# Existing micro-switch carrier is supported at rear by the new shoulder.
carrier_stop=cut(cyl(6.3,1,(76,0,0)),cyl(3.5,1.2,(75.9,0,0)),box(75.9,77.1,-2.6,2.6,2.5,6.5),box(75.9,77.1,3.25,7.0,-4.2,4.2))
lo=union(lo,carrier_stop.intersect(box(75,78,-7,7,-7,0)));hi=union(hi,carrier_stop.intersect(box(75,78,-7,7,0,7)))
# Side pocket gives J402 plug and 2-core turn enough room beyond the FR4 edge.
pocket_outer=box(BX+7.6,BX+21,-20.5,-12.3,-6,1.6)
pocket_inner=box(BX+9.2,BX+19.4,-18.9,-11.5,-4.4,.1)
lo=union(lo,pocket_outer.intersect(box(0,TAIL,-30,30,-20,0)))
hi=union(hi,pocket_outer.intersect(box(0,TAIL,-30,30,0,20)))
lo=cut(lo,pocket_inner);hi=cut(hi,pocket_inner)
# An inner route joins pocket to main cavity; no wire must cross the snap hook.
lo=cut(lo,box(BX+9.2,BX+19.4,-14.3,-11.5,-4.4,.1))
# USB-C body/socket and plug-mould clearance at -Y; GSR plug opening at +Y.
for tool in [box(BX+41,BX+55,-15,-11.6,-1.3,5.7),box(BX+23,BX+31,11.6,15,-1,7)]:
 lo=cut(lo,tool);hi=cut(hi,tool)
# Expose real board pushbuttons and LEDs for the development prototype.
for x in (41,49.4):hi=cut(hi,cyl(1.7,10,(BX+x,6.3,1),(0,0,1)))
hi=cut(hi,box(BX+33.4,BX+43.6,9.0,11.4,1,10))
# Four press-release beams at clear positions, on the side walls.
for start in (79,BX+57):
 end=start+14
 for side in (1,-1):
  def mir(s):return s if side==1 else reflect(s)
  hi=cut(hi,mir(box(start+1.2,end+1.4,11.65,14.4,0,6.65)))
  beam=box(start,end,11.7,12.6,4.3,6.1)
  root=box(start-1.2,start+1.2,11.7,13.8,4.3,7.9)
  hook=yzprism(end-1.8,end,[(12.5,4.25),(13.25,5.1),(13.25,5.65),(12.5,5.65)])
  hi=union(hi,mir(beam),mir(root),mir(hook))
  receiver=box(end-2.8,end+1.2,12.6,14.2,0,6.45)
  window=box(end-2.05,end+.3,12.5,14.3,4.05,5.9)
  lo=union(lo,mir(cut(receiver,window)))
# Alignment keys avoid connector/window regions.
for xa,xb in ((BX+33,BX+37),(BX+56,BX+60)):
 for side in (1,-1):
  rail=box(xa,xb,12.15,12.65,-.2,1.1);recess=box(xa-.25,xb+.25,11.95,12.85,-.1,1.4)
  if side<0:rail,recess=reflect(rail),reflect(recess)
  lo=union(lo,rail);hi=cut(hi,recess)
# Roof edge retainers leave .3mm over the FR4 and keep off all fitted bodies.
for x in (BX+20,BX+65):
 for ya,yb in ((-12.5,-11.0),(11.0,12.5)):hi=union(hi,box(x+.2,x+2.4,ya,yb,.8,6.5))
# Engraved labels are shallow and kept outside the beam roots/roof apertures.
def roof_text(s,t,x,y,size=2.1):
 letters=cq.Workplane('XY').text(t,size,.45,combine=True,font='Arial',halign='center',valign='center').val().translate((x,y,ROOF-.4))
 return cut(s,letters)
for t,x,y in [('BOOT',BX+41,1.2),('RST',BX+49.4,1.2),('LED',BX+30.5,9.9),('GSR',BX+27,5.7),('USB',BX+48,-8.5)]:hi=roof_text(hi,t,x,y)
# EVQQ2B03W: 6.0mm across Y, 6.5mm across Z, 1.8mm body plus
# actuator to H=3.1mm. J-bent terminals extend to 6.6mm across Z.
# The back is mechanically supported at X=73.5; solder joints carry no force.
car=cyl(5.2,12,(64,0,0))
car=cut(car,cyl(3.4,3.2,(63.9,0,0)),cyl(3.5,1.35,(66.75,0,0)),
        cyl(2.2,3.6,(67.9,0,0)),box(71.5,73.5,-3.25,3.25,-3.5,3.5),
        box(73.3,76.1,-2.5,2.5,2.0,5.3),
        box(73.3,76.1,-2.5,2.5,-5.3,-2.0),
        box(71.5,76.1,-2.6,2.6,3.1,4.4),
        box(71.5,76.1,-2.6,2.6,-4.4,-3.1),
        box(63.9,76.1,3.4,5.3,-4.0,4.0))
carlo=car.intersect(box(63,77,-6,6,-6,0)).clean()
carhi=car.intersect(box(63,77,-6,6,0,6)).clean()
def make_plunger(length):return union(cyl(3.2,.8,(67,0,0)),cyl(2.,length,(67,0,0)))
plunger=make_plunger(3.4)
parts={'01_one_piece_barrel':barrel,'02_threaded_nose':nose,'03_rear_base':lo,'04_press_release_cover':hi,
 '05_switch_carrier_lower':carlo,'06_switch_carrier_upper':carhi,'07_refill_plunger':plunger,
 '08_optical_cassette':pod,'09_optical_lid':oplid}
# Actual-format solids, separately printable, no artificially thickened bare boards.
parts['20_battery_dummy_36x12x6']=box(BAT_X,BAT_X+BAT_L,-6,6,BAT_Z,BAT_Z+6)
opt_board=box(cu-7.5,cu+7.5,cv-7,cv+7,seat,seat+1.6)
# Approximate sensor and component heights, conservatively bounded; keep corners bare.
opt_sensor=box(cu-1.75,cu+1.75,cv-1.6,cv+1.6,seat-1.0,seat+.05)
opt_components=[box(cu-5.8,cu-3.8,cv-4.5,cv+4.5,seat-1.4,seat+.05),box(cu+3.8,cu+5.8,cv-4.5,cv+4.5,seat-1.4,seat+.05)]
parts['21_PAT9125_dummy_14x15']=pp(union(opt_board,opt_sensor,*opt_components))
# Simplified fitted-body solids from the actual latest PCB coordinates, not old envelopes.
data=json.loads((R/'rear_board_mechanical_input.json').read_text())
rear=box(BX,BX+70,-12,12,-.5,.5)
body_solids=[]
for c in data['components']:
 if c['fit']!='FIT':continue
 x0,y0,x1,y1=c['body_bbox_xy_mm'];z0,z1=c['body_z_range_mm']
 z0-=.5;z1-=.5
 # Intersect the substrate by .01mm to robustly unify the printed dummy.
 if c['side']=='top':z0-=.01
 else:z1+=.01
 body_solids.append(box(BX+x0,BX+x1,y0,y1,z0,z1))
rear=union(rear,*body_solids)
parts['22_rear_board_dummy_75x24']=rear
switch_body=box(71.7,73.5,-3,3,-3.25,3.25)
switch_body=union(switch_body,cyl(1.5,1.3,(70.4,0,0)))
for y in (-2.,2.):
 for side in (-1,1):
  switch_body=union(switch_body,box(73.1,73.5,y-.4,y+.4,min(side*3.1,side*3.3),max(side*3.1,side*3.3)))
parts['23_EVQQ2B03W_dummy']=switch_body
shell_names=[n for n in parts if not n.startswith('2')]
dummy_names=[n for n in parts if n.startswith('2')]
refs={'REF_gel_refill':union(cyl(1.25,7.5,(0,0,0)),cq.Solid.makeCone(1.25,3,3,cq.Vector(7.5,0,0),cq.Vector(1,0,0)),cyl(3,56.5,(10.5,0,0))),
 'REF_NTC_keepout':box(BAT_X+12,BAT_X+17,-1.5,1.5,BAT_Z+6.25,BAT_Z+9.25)}
P.update({'length':TAIL,'rear_width':W,'rear_height':14,'rear_side_pocket_width_total':34.7,'pcb_origin_x':BX,'pcb_FR4':[70,24,1],
 'pcb_assembled_length':75,'battery':[36,12,6],'battery_placement':'serial: battery ahead of rear board, no overlap in X',
 'battery_origin_x':BAT_X,'battery_bottom_z':BAT_Z,'rear_body_z_range':[-6,8],
 'rear_transition_z_range':[-8.2,8.2], 'rear_inner_height':10.8,'optical_board':[14,15,1.6],
 'optical_board_thickness_status':'assumed, not vendor-confirmed','optical_components_status':'approximate XY/heights, not vendor drawing',
 'window_opening':[ou,ov],'window_gap':g,'optical_PCB_paper_facing_surface':seat,'sensor_front_paper_gap_assumed':seat-1,
 'optical_center_uv':[cu,cv],'optical_Z0':None,'rear_pcb_thickness_status':'design target 1.0 mm',
 'wire_bundle_max_mm':[1.0,5.0],'wire_duct_clear_mm':[1.3,5.5],
 'wire_duct_refill_separator_mm':.8,'wire_duct_outer_wall_mm':1.2,
 'wire_single_insulation_OD_max_mm':1.0,'grip_local_width_with_rib_mm':12.25,
 'battery_cradle_clear_mm':[37.6,13.0],'battery_bottom_pad_mm':.5,
 'battery_size_source':'user seller photo, 2026-10-29, includes protection assumed; not caliper measurement',
 'switch_model':'EVQQ2B03W','switch_body_mm':[6.5,6.0,1.8],
 'switch_total_height_mm':3.1,'switch_height_tolerance_mm':.2,
 'switch_cavity_yz_mm':[6.5,7.0],'switch_cavity_axial_mm':2.0,
 'plunger_nominal_length_mm':3.4,'plunger_optional_lengths_mm':[3.2,3.6],
 'plunger_hard_stop_travel_mm':.30,'switch_operating_travel_nominal_mm':.2,
 'fasteners':'pod M1.6x3 x2; bracket M2x6 x2 + M2 nuts x2; rear shell snap-fit'})
(R/'source/parameters.json').write_text(json.dumps(P,ensure_ascii=False,indent=2))

def getmesh(s):
 v,f=s.tessellate(.04,.09);return trimesh.Trimesh([p.toTuple() for p in v],f,process=True)
def printing(n,s):
 if n in ('01_one_piece_barrel','02_threaded_nose') or n.startswith('23'):s=s.rotate((0,0,0),(0,1,0),90)
 elif 'plunger' in n:s=s.rotate((0,0,0),(0,1,0),-90)
 elif n in ('04_press_release_cover','06_switch_carrier_upper'):s=s.rotate((0,0,0),(1,0,0),180)
 elif n in ('08_optical_cassette','09_optical_lid','21_PAT9125_dummy_14x15'):
  s=s.rotate((0,0,0),(0,1,0),-55)
  if n in ('09_optical_lid','21_PAT9125_dummy_14x15'):s=s.rotate((0,0,0),(1,0,0),180)
 elif n=='22_rear_board_dummy_75x24':s=s.rotate((0,0,0),(1,0,0),180)
 return s
optional_parts={'10_plunger_short_3p2':make_plunger(3.2),'11_plunger_long_3p6':make_plunger(3.6)}
meshparts={};assemblymeshes={};manifest=[]
for n,s in {**parts,**optional_parts}.items():
 assert s.isValid() and len(s.Solids())==1,(n,'invalid',len(s.Solids()))
 cq.exporters.export(s,str(R/'cad'/f'{n}.step'))
 m=getmesh(printing(n,s));m.apply_translation(-m.bounds[0]);assert m.is_watertight and m.is_winding_consistent and m.volume>0,(n,'mesh invalid')
 assert len(m.split())==1,(n,'mesh components')
 m.export(R/'stl'/f'{n}.stl');meshparts[n]=m;assemblymeshes[n]=getmesh(s)
 manifest.append({'name':n,'dimensions_mm':np.round(m.extents,3).tolist(),'volume_mm3':round(s.Volume(),3),'valid_brep':True,'single_solid':True,'watertight':True});print(n,manifest[-1]['dimensions_mm'],flush=True)
assembly=cq.Assembly(name='SMART_PEN_V05_SERIAL');scene=trimesh.Scene()
for n,s in {**parts,**refs}.items():
 c='#3E8B65' if n.startswith(('21','22')) else '#AEB8C4' if n.startswith(('20','REF')) else '#DC8948' if n.startswith(('02','07','08','09')) else '#526C84'
 assembly.add(s,name=n,color=cq.Color(c));m=getmesh(s);m.visual.vertex_colors=trimesh.visual.color.hex_to_rgba(c);scene.add_geometry(m,node_name=n)
assembly.export(str(R/'cad/smart_pen_v05_assembly_mm.step'));scene.apply_scale(.001);(R/'cad/smart_pen_v05_preview.glb').write_bytes(scene.export(file_type='glb'))
def write3mf(name,names):
 ns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02';ET.register_namespace('',ns);model=ET.Element(f'{{{ns}}}model',unit='millimeter');resources=ET.SubElement(model,'resources');build=ET.SubElement(model,'build');x,y,h=10.,30.,0.
 for i,n in enumerate(names,1):
  m=meshparts[n];sx,sy,sz=m.extents
  if x+sx>243:x=10;y+=h+12;h=0
  assert y+sy<243,(name,n,y+sy)
  ob=ET.SubElement(resources,'object',id=str(i),name=n,type='model');me=ET.SubElement(ob,'mesh');vs=ET.SubElement(me,'vertices');ts=ET.SubElement(me,'triangles')
  for v in m.vertices:ET.SubElement(vs,'vertex',x=f'{v[0]:.6f}',y=f'{v[1]:.6f}',z=f'{v[2]:.6f}')
  for f in m.faces:ET.SubElement(ts,'triangle',v1=str(f[0]),v2=str(f[1]),v3=str(f[2]))
  ET.SubElement(build,'item',objectid=str(i),transform=f'1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} 0');x+=sx+12;h=max(h,sy)
 with zipfile.ZipFile(R/name,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
  z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
  z.writestr('3D/3dmodel.model',ET.tostring(model,encoding='utf-8',xml_declaration=True))
write3mf('v05_shell_geometry_mm.3mf',shell_names+list(optional_parts));write3mf('v05_hardware_dummies_geometry_mm.3mf',dummy_names)
write3mf('v05_all_parts_geometry_mm.3mf',shell_names+list(optional_parts)+dummy_names)
# No collision assumptions silently filtered; only touching surfaces are allowed.
collisions=[]
for a,b in itertools.combinations(parts,2):
 v=parts[a].intersect(parts[b]).Volume()
 if v>.002:collisions.append({'a':a,'b':b,'overlap_mm3':round(v,5)})
ref_hits=[]
for a in shell_names:
 for b,s in refs.items():
  v=parts[a].intersect(s).Volume()
  if v>.002:ref_hits.append({'a':a,'b':b,'overlap_mm3':round(v,5)})
clearance=[]
for angle in (45,50,55,60,65):
 for roll in (-10,0,10):
  ar,rrr=math.radians(angle),math.radians(roll);mins=[]
  for n,m in assemblymeshes.items():
   v=m.vertices;z=(v[:,0]-.25)*math.sin(ar)+(v[:,1]*math.sin(rrr)+v[:,2]*math.cos(rrr))*math.cos(ar);mins.append((float(z.min()),n))
  gap,n=min(mins);clearance.append({'pitch_deg':angle,'roll_deg':roll,'minimum_gap_mm':round(gap,4),'part':n})
report={'parameters':P,'parts':manifest,'collisions':collisions,'reference_collisions':ref_hits,'paper_clearance':clearance,'scope':'Dimension/assembly prototype; optical Z0 and actual manufactured module heights not validated.'}
(R/'reports/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('COLLISIONS',collisions,ref_hits,'minpaper',min(c['minimum_gap_mm'] for c in clearance),flush=True)
assert not(collisions or ref_hits),'Fix assembly interference'
