from pathlib import Path
import json,zipfile,re
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
N={'c':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
with zipfile.ZipFile(ROOT/'笔芯样件_67mm_P1S_PLA.3mf') as z:
    assert z.testzip() is None
    s=json.loads(z.read('Metadata/project_settings.config'))
    required={'printer_model':'Bambu Lab P1S','curr_bed_type':'Textured PEI Plate',
        'nozzle_diameter':['0.4'],'layer_height':'0.16','brim_width':'8','brim_type':'outer_only',
        'enable_support':'0','raft_layers':'0','wall_loops':'4',
        'textured_plate_temp_initial_layer':['65'],'textured_plate_temp':['60'],
        'additional_cooling_fan_speed':['0']}
    for k,v in required.items(): assert s[k]==v,(k,s[k])
    root=ET.fromstring(z.read('3D/Objects/object_1.model'))
    me=root.find('c:resources/c:object/c:mesh',N)
    vertices=[[float(v.get(k)) for k in ['x','y','z']] for v in me.findall('c:vertices/c:vertex',N)]
    faces=[[int(v.get(k)) for k in ['v1','v2','v3']] for v in me.findall('c:triangles/c:triangle',N)]
    actual=trimesh.Trimesh(vertices,faces,process=False)
    expected=trimesh.load(ROOT/'笔芯样件_67mm_尾端朝下.stl',force='mesh')
    assert np.max(np.abs(actual.extents-expected.extents)) < .0001
    assert abs(actual.volume-expected.volume)<.01
    model=ET.fromstring(z.read('3D/3dmodel.model'))
    item=model.find('c:build/c:item',N)
    t=np.array([float(v) for v in item.get('transform').split()]).reshape(4,3)
    transformed=actual.vertices @ t[:3,:] + t[3,:]
    assert abs(transformed[:,2].min())<.0001
    assert abs(transformed[:,2].max()-67)<.0001
    assert np.allclose(np.ptp(transformed,axis=0),[6,6,67],atol=.003)
    meta=ET.fromstring(z.read('Metadata/model_settings.config'))
    for st in meta.findall('.//mesh_stat'):
        assert all(int(v)==0 for k,v in st.attrib.items() if k!='face_count')
    plates=ET.fromstring(z.read('Metadata/slice_info.config')).findall('plate')
    assert len(plates)==1 and len(plates[0].findall('object'))==1
    md={q.get('key'):q.get('value') for q in plates[0].findall('metadata')}
    assert md['outside']=='false' and md['support_used']=='false'
    assert plates[0].find('object').get('skipped')=='false'
    g=z.read('Metadata/plate_1.gcode').decode()

assert 'M83' in g and 'M190 S65' in g
x=y=0.;layer=0;feature='';first=[];layerz=[]
for line in g.splitlines():
    if line=='; CHANGE_LAYER':layer+=1
    if line.startswith('; Z_HEIGHT:'):layerz.append(float(line.split(':')[1]))
    if line.startswith('; FEATURE:'):feature=line.split(':',1)[1].strip()
    if layer and line.startswith('M106 P2 S'): assert line.split(';')[0].strip()=='M106 P2 S0'
    if not re.match(r'^G[01] ',line):continue
    vals={k:float(v) for k,v in re.findall(r'([XYE])(-?(?:\d+(?:\.\d*)?|\.\d+))',line.split(';')[0])}
    nx,ny=vals.get('X',x),vals.get('Y',y)
    if layer==1 and vals.get('E',0)>0 and abs(nx-x)+abs(ny-y)>1e-7:
        first.append((feature,[(x,y),(nx,ny)]))
    x,y=nx,ny
features=set(f for f,p in first)
assert 'Brim' in features and 'Outer wall' in features and 'Bottom surface' in features
assert 'Support' not in features
assert abs(layerz[0]-.2)<.001 and abs(layerz[-1]-67)<.17
# P1S profile uses a (0,2) nozzle offset: G-code XY is carriage coordinates.
offset=np.array([float(q) for q in s['extruder_offset'][0].split('x')])
center=np.mean(transformed[:,:2],axis=0)-offset
for f,points in first:
    for xy in points:
        assert all(1 < q < 255 for q in xy)
        if f!='Brim': assert np.linalg.norm(np.array(xy)-center)<3.5
report={'passed':True,'single_object':True,'geometry_matches_stl':True,'no_mesh_repairs':True,
        'height_mm':67,'bed_contact':'6mm diameter rear end; model minimum Z=0',
        'first_layer_features':sorted(features),'first_layer_segments':len(first),
        'first_layer_z_mm':layerz[0],'last_layer_z_mm':layerz[-1],
        'estimated_seconds':int(md['prediction']),'estimated_grams':float(md['weight']),
        'settings_checked':required,'physical_print':'not performed'}
(ROOT/'reports/print_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))

font=FontProperties(fname='/System/Library/Fonts/STHeiti Light.ttc')
plt.rcParams['axes.unicode_minus']=False
fig,(ax,bx)=plt.subplots(2,1,figsize=(10,6),gridspec_kw={'height_ratios':[1.25,1]})
outline=[(0,-1.25),(7.5,-1.25),(10.5,-3),(67,-3),(67,3),(10.5,3),(7.5,1.25),(0,1.25)]
ax.add_patch(Polygon(outline,facecolor='#dbe9f2',edgecolor='#264b65',linewidth=1.4))
ax.plot([0,67],[0,0],color='#aab8c4',lw=.7,ls='--')
ax.annotate('',xy=(0,6),xytext=(67,6),arrowprops={'arrowstyle':'<->','lw':1.2})
ax.text(33.5,6.6,'总长 67 mm（含前端）',ha='center',fontproperties=font,fontsize=13)
for xx in [0,67]:ax.plot([xx,xx],[3.5,6.5],color='#718492',lw=.8)
ax.text(39,0,'管身 Ø6 × 56.5 mm',ha='center',va='center',fontproperties=font,fontsize=12)
ax.annotate('前导向段 Ø2.5 × 7.5 mm',xy=(3,0),xytext=(-1,-8),fontproperties=font,fontsize=10,arrowprops={'arrowstyle':'-','color':'#526573'})
ax.annotate('过渡段 3 mm',xy=(9,2),xytext=(20,-8),fontproperties=font,fontsize=10,arrowprops={'arrowstyle':'-','color':'#526573'})
ax.annotate('尾端接标准顶杆',xy=(67,0),xytext=(51,-8),fontproperties=font,fontsize=10,arrowprops={'arrowstyle':'-','color':'#526573'})
ax.set_xlim(-3,71);ax.set_ylim(-10,10);ax.set_aspect('equal');ax.axis('off')
ax.set_title('v0.5 外壳笔芯试装样件 · 不能出墨书写',fontproperties=font,fontsize=16,pad=15)
colors={'Brim':'#c28b30','Outer wall':'#264b65','Inner wall':'#527e99','Bottom surface':'#527e99'}
for f in features:
    lines=[np.array(p)-center for ff,p in first if ff==f]
    bx.add_collection(LineCollection(lines,colors=colors.get(f,'#527e99'),linewidths=.7))
bx.set_xlim(-14,40);bx.set_ylim(-14,14);bx.set_aspect('equal');bx.axis('off')
bx.text(14,5,'实际首层路径：粗尾端朝下',fontproperties=font,fontsize=12)
bx.text(14,0,'蓝色：笔芯底面\n金色：8 mm 可拆裙边',fontproperties=font,fontsize=11,linespacing=1.7)
bx.text(14,-7,'P1S / PLA / 0.4 mm · 100% 比例',fontproperties=font,fontsize=10)
fig.tight_layout()
fig.savefig(ROOT/'笔芯尺寸与首层.png',dpi=180,bbox_inches='tight')
print(json.dumps(report,ensure_ascii=False,indent=2))
