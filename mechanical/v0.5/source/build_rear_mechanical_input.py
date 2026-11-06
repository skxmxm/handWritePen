from pathlib import Path
import json, math, re, zipfile
ROOT=Path(__file__).resolve().parents[3]
SRC=ROOT/'hardware/pcb/rear_mainboard/restore_esp32/layout_r26'
OUT=ROOT/'mechanical/v0.5'
entries=[{'component':c} for c in json.loads((SRC/'final_pcb.json').read_text())['components']]
z=zipfile.ZipFile(SRC/'Rear_ESP32S3_R26.epro')
mm=.0254

def trans(x,y,c):
    if c['layer']==2:y=-y
    a=math.radians(c['rotation']);return [(c['x']+x*math.cos(a)-y*math.sin(a))*mm,(c['y']+x*math.sin(a)+y*math.cos(a))*mm]
def coordpoly(path):
    pts=[];i=0
    if path and path[0]=='CIRCLE':
        x,y,r=path[1:4];return [(x-r,y-r),(x+r,y+r)]
    while i<len(path):
        if isinstance(path[i],str):
            if path[i]=='ARC':i+=2
            else:i+=1
        elif i+1<len(path) and isinstance(path[i+1],(int,float)):
            pts.append(path[i:i+2]);i+=2
        else:i+=1
    return pts

def bbox(points):return [min(x[0] for x in points),min(x[1] for x in points),max(x[0] for x in points),max(x[1] for x in points)]
components=[]
for item in entries:
    c=item['component'];des=c['designator'];o=c.get('otherProperty',{});fit=o.get('Assembly','FIT');name=c.get('model3D',{}).get('name','')
    raw=[];body_source='';conf='library nominal'
    try:
        data=[json.loads(l) for l in z.read('FOOTPRINT/'+c['footprint']['uuid']+'.efoo').decode().splitlines()]
        for d in data:
            if d[0]=='POLY' and d[4]==48:raw+=coordpoly(d[6])
        if raw:body_source='library component outline layer 48 (not pad extents)'
    except (KeyError,ValueError):pass
    if raw:bb=bbox([trans(x,y,c) for x,y in raw])
    else:
        m=re.search(r'_L([\d.]+)-W([\d.]+)',name)
        if m:
            L,W=map(float,m.groups()); bb=bbox([trans(x/mm,y/mm,c) for x in [-L/2,L/2] for y in [-W/2,W/2]])
            body_source='model title nominal L/W; lead span excluded'
        else:bb=None;body_source='no physical solid; test pad or unresolved body'
    hm=re.search(r'-H([\d.]+)',name)
    if hm:h=float(hm.group(1));h_source='model title nominal H'
    elif des.startswith('R'):h=.55;h_source='conservative passive body estimate'
    elif des.startswith('C'):h=1.3;h_source='conservative capacitor body estimate'
    elif des.startswith('D'):h=.8;h_source='conservative LED/diode estimate'
    elif des.startswith('Q'):h=1.2;h_source='conservative SOT-23 estimate'
    else:h=1.2;h_source='conservative IC estimate'
    if des in ['J102','J103','J402','J401']:h=2.9;h_source='JST SH datasheet / library nominal'
    if des=='J101':bb=[43.53,-12.20,52.47,-4.20];h=3.4;h_source='conservative USB height allowance; nominal shell height not independently verified';body_source='silkscreen shell front and width plus conservative 8.0mm depth allowance';conf='estimated conservative envelope'
    if des=='J301':h=5.;h_source='library manufacturer body height';body_source='10.8x5mm footprint physical outline; front barrel part of bounds'
    if des=='U401':bb=[2.38,-7.62,17.62,7.62];h=2.8;h_source='WitMotion JY901S official nominal';body_source='official 15.24x15.24mm nominal, centered on current component origin'
    if des=='U201':h=2.4;h_source='ESP32-S3-MINI-1 datasheet nominal 2.4mm';body_source='official module envelope matched to library layer48; includes antenna overhang'
    if des=='L101':h=1.5;h_source='conservative estimate for power inductor'
    if fit=='PCB_ONLY':bb=None;h=0.;h_source='copper only; no fitted solid'
    side='top' if c['layer']==1 else 'bottom'
    zrange=[1.,1.+h] if side=='top' else [-h,0.]
    e={'designator':des,'mpn':c.get('manufacturerId',''),'fit':fit,'side':side,'eda_origin_mm':[round(c['x']*mm,4),round(c['y']*mm,4)],'rotation_deg':c['rotation'],'body_bbox_xy_mm':[round(v,4) for v in bb] if bb else None,'body_z_range_mm':zrange,'body_height_mm':h,'body_xy_source':body_source,'height_source':h_source,'confidence':conf,'model_title':name}
    components.append(e)
ports=[
 {'designator':'J101','function':'USB-C charging / firmware','side':'top','axis':[0,-1,0],'face_center_mm':[48,-12.20,2.7],'suggested_shell_cutout_mm':{'width_x':11,'height_z':5,'center_z':2.7},'known':'PCB XY/orientation and front mouth X/Y; height center estimated','note':'Cut through whole side wall. Recess around plug if its molded boot is larger than port; no connector retention on solder joints.'},
 {'designator':'J301','function':'2.5mm electrode finger sleeves','side':'top','axis':[0,1,0],'face_center_mm':[27,12.35,3.5],'suggested_shell_cutout_mm':{'diameter':5.5,'center_z':3.5},'known':'XY from physical footprint, body nominal H5; hole center height assumed half H','note':'Actual plug shaft is2.5mm; shell clearance is for jack nose/plug reach, not2.5mm tiny hole. Use 6.5x6.2 development opening if plug boot obstructs.'},
 {'designator':'SW201','function':'BOOT / USER','side':'top','axis':[0,0,1],'actuator_center_mm':[41,6.3,3.5],'suggested_shell_cutout_mm':{'diameter':3.2},'known':'PCB XY and nominal switch H2.5','note':'Access hole for finger tool; if plunger added leave0.3mm neutral clearance.'},
 {'designator':'SW202','function':'RESET','side':'top','axis':[0,0,1],'actuator_center_mm':[49.4,6.3,3.5],'suggested_shell_cutout_mm':{'diameter':3.2},'known':'PCB XY and nominal switch H2.5','note':'Access hole or separate plunger.'},
 *[{'designator':d,'function':f,'side':'top','axis':[0,0,1],'center_xy_mm':[x,10],'suggested_shell_cutout_mm':{'diameter':2.4},'known':'PCB XY; LED nominal0.8mm high estimate'} for d,x,f in [('D501',35,'CHG'),('D502',38.5,'SYS'),('D503',42,'FAULT')]],
]
connectors=[
 {'designator':'J401','function':'PAT9125EL-TKIT optical module','pins':5,'pin_order':['VDD/VOPT','SCL','SDA','MOT','GND'],'insertion_opening_direction':[-1,0,0],'face_center_mm':[1.36,.5,-1.45],'mated_plug_additional_projection_mm':2.0,'suggested_wire_keepout_bbox_mm':[-5,-3.8,-3.6,1.36,4.8,.1],'note':'Five-wire lead exits toward front; JST at rear, module side solder holes.'},
 {'designator':'J102','function':'battery','pins':2,'insertion_opening_direction':[-1,0,0],'face_center_mm':[.887,8.8,-1.45],'mated_plug_additional_projection_mm':2.0,'suggested_wire_keepout_bbox_mm':[-5,5.8,-3.6,.887,11.8,.1]},
 {'designator':'J103','function':'battery NTC','pins':2,'insertion_opening_direction':[-1,0,0],'face_center_mm':[.887,-8,-1.45],'mated_plug_additional_projection_mm':2.0,'suggested_wire_keepout_bbox_mm':[-5,-11,-3.6,.887,-5,.1]},
 {'designator':'J402','function':'refill microswitch','pins':2,'pin_order':['TIP_RAW','GND'],'insertion_opening_direction':[0,-1,0],'face_center_mm':[14,-11.412,-1.45],'mated_plug_additional_projection_mm':2.0,'suggested_wire_keepout_bbox_mm':[9.5,-16.5,-3.6,18.5,-11.412,.1],'note':'Critical side-facing plug. Plug alone projects approx2mm outside socket; allow wire bend toY=-16.5 or provide open lower-side channel. Straight inner wall atY=-12.5 blocks plug.'}]
result={'version':'mechanical-v0.5-R26-rear-input','date':'2026-10-29','units':'mm','source':str(SRC),'coordinate_system':{'x':'PCB front0 to tail70; ESP extends to75','y':'same EasyEDA global Y, substrate-12..+12; USB negativeY, GSR positiveY','z':'PCB bottom0/top1; positive toward top-layer components','handedness':'right handed; bottom components already mirrored in coordinates; do not mirror again'},'substrate':{'bbox_mm':[0,-12,0,70,12,1],'size_mm':[70,24,1],'thickness_status':'current intended1.0mm, no bare board measurement','mounting_holes':[]},'assembled_envelope':{'bbox_mm':[0,-12.2,-2.9,75,12.35,6.0],'includes':'nominal bare PCB and fitted bodies; excludes cable plugs/wire-bend space and soldering tolerances','min_inner_height_recommended_mm':10,'top_clearance_mm':.5,'bottom_clearance_mm':.5},'rf_keepout':{'antenna_bbox_xy_mm':[69.95,-7.7,75,7.7],'no_metal_battery_wire_tail_from_x_mm':69.95,'note':'Plastic may enclose antenna with clearance; keep battery/copper/wires away. Nominal radiating end not contact stop.'},'ports_and_controls':ports,'internal_harness':connectors,'support_recommendations':{'rail_clearance_xy_mm':.3,'do_not_clamp_components':True,'suggestion':'Use edge supports and removable stops at noncomponent regions. Allow top-in placement; avoid long slid-in rails colliding with through-hole pins. No screw holes exist in board.'},'components':components,'uncertainties':['USB shell height/port-axis Z conservatively approximated, verify real connector before final cosmetic hole freeze.','J301 axis height assumed2.5mm above PCB top; use generous development access hole.','JST mated axial projection2.0mm derived from6.25mm mated overall vs4.25mm socket depth, wire bend3mm is design allowance.','PCB thickness1.0mm and module solder standoff not measured; add0.1~0.2mm module assembly clearance.','Small passive solids are nominal/conservative simplified blocks, not manufacturer exact3D.','J301 through-hole solder tails may protrude underside; avoid clamping under socket pads.']}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'rear_board_mechanical_input.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
rows=[]
for c in components:
 if c['designator'] in ['J101','J301','J401','J402','J102','J103','U201','U401','SW201','SW202','D501','D502','D503']:
  rows.append(f"| {c['designator']} | {c['side']} | {c['body_bbox_xy_mm']} | {c['body_height_mm']} | {c['height_source']} |")
md='''# V0.5后板机械输入

只读核对2026-10-29的 `Rear_ESP32S3_R26`；没有改动PCB或在线工程。供打印占位与开发外壳使用，不把外壳适配视为PCB最终制造放行。

## 坐标与包络

单位mm。X从后板前端0到板尾70；Y=-12～+12，与EDA一致；USB朝-Y，指套口朝+Y。Z=0为主板下表面，Z=1为上表面。底面器件坐标已经包含镜像，CAD不要再次镜像。

- PCB本体70×24×1.0；1.0mm是当前拟定板厚。
- ESP32-S3-MINI-1尾端伸到X≈75.0，天线从X≈69.95开始，不能按70mm做尾挡。模块本体20.5×15.4×2.4（沿X/Y/Z）。
- 名义装配包络X=0～75，Y=-12.2～+12.35，Z=-2.9～6.0。线束/插头另计。最高顶面器件是指套座，高5mm；底面JST高2.9mm。建议内部至少10mm净高。
- JY901S按官方15.24×15.24×2.8，占位中心(10,0)，不能将17.8mm焊盘包络当模块外壳。

## 端口、按钮与指示灯

- USB-C J101：X=48，朝-Y，口前端Y≈-12.20；建议11mm宽×5mm高开发孔，端口Z中心暂取2.7。允许USB插头外塑壳伸入，不宜只切金属舌口大小。
- 2.5mm指套插口J301：轴X=27，朝+Y，鼻端Y≈12.35；轴心Z暂取3.5。可用Ø5.5或6.5×6.2开发开口，避免2.5mm小孔阻止插头插到底。
- SW201 BOOT/USER：(41,6.3)，SW202 RESET：(49.4,6.3)，均顶面，按钮顶Z=3.5。按压孔推荐Ø3.2；打印推杆需留0.3mm静止间隙，不持续压键。
- D501 CHG、D502 SYS、D503 FAULT：(35,10)、(38.5,10)、(42,10)，顶面。各Ø2.4观察孔即可。

## 特别注意J402线束

J401五针光学座、J102电池、J103 NTC均在底面，朝-X，前方需留线束过渡舱。

**J402微动座在底面(14,-8.8)，朝-Y。** 本体朝外面到Y=-11.41。JST资料侧插连接器插接总深6.25mm，相比4.25mm座体需额外约2mm，插好后达到Y≈-13.41；再留约3mm线尾转弯，建议局部净空到Y=-16.5。Y=-12.5的紧贴直壁会挡住插头，必须局部拓宽底侧线束通道，或允许线从开口折回前端。不要为此静默修改PCB朝向。

J401线序1VDD、2SCL、3SDA、4MOT、5GND，后板JST插接，前板按孔丝印同序焊接。

## 主要器件简化实体

下面XY包络为物理轮廓或标注的保守实体，不是焊盘bbox。高度从安装面起算，主板厚度另计。

| 位号 | 面 | XY范围[xmin,ymin,xmax,ymax] | 高 | 高度依据 |
|---|---|---|---:|---|
'''+ '\n'.join(rows)+'''

`rear_board_mechanical_input.json`含全部123组件、FIT/DNP状态、接口方向、建议孔位、线束避空与来源。仅FIT实体用于打印占位。PCB_ONLY是测试焊盘，不增加实体；DNP不装实体。小阻容的立体高度是保守简化值，用于碰撞检查而非复刻封装。

## 需要保持标注的近似项

USB高度和轴心、J301轴心高度、插头线弯半径尚无实物量测，按开发装配孔与保守留空处理。J301穿板焊脚还会伸到主板背面，避免在其焊盘下压住PCB；背面现有2.9mm的JST包络已大于通常焊脚余长。模块底部焊接间隙再留0.1～0.2mm。

依据：当前工程最终器件坐标/原生封装层48轮廓、JST SH官方与立创资料、项目JY901S官方尺寸记录、ESP32-S3-MINI-1规格书。USB没有将现有焊盘宽度误当插座塑壳尺寸。
'''
(OUT/'rear_board_mechanical_input.md').write_text(md)
print('wrote',OUT/'rear_board_mechanical_input.json','components',len(components))
for c in components:
 if c['designator'] in ['J101','J301','J401','J402','J102','J103','U201','U401']:print(c['designator'],c['body_bbox_xy_mm'],c['body_z_range_mm'])
