from pathlib import Path
import math,json
import numpy as np
import trimesh
import vtk
from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
from PIL import Image,ImageDraw,ImageFont
import cadquery as cq

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'previews'
P=json.loads((ROOT/'source/parameters.json').read_text())
fontpath='/System/Library/Fonts/STHeiti Medium.ttc'
def font(n):return ImageFont.truetype(fontpath,n)
def meshstep(path):
 s=cq.importers.importStep(str(path)).val()
 v,f=s.tessellate(.06,.12)
 return trimesh.Trimesh([q.toTuple() for q in v],f,process=True)
meshes={p.stem:meshstep(p) for p in (ROOT/'cad').glob('[0-9]*.step')}
scene=trimesh.load(ROOT/'cad/smart_pen_v05_preview.glb',force='scene')
for k in scene.graph.nodes_geometry:
 transform,geom=scene.graph[k]
 if k.startswith('REF_'):
  meshes[k]=scene.geometry[geom].copy();meshes[k].apply_transform(transform);meshes[k].apply_scale(1000)
wire_ref=ROOT/'cad/reference_wire_route_NOT_FOR_PRINT.step'
if wire_ref.exists():meshes['REF_wire_route']=meshstep(wire_ref)
def color(k):
 if k.startswith('CUT_'):k=k[4:]
 if 'battery' in k:return (.72,.76,.81)
 if k=='REF_wire_route':return (.9,.57,.12)
 if 'REF_gel' in k:return (.73,.76,.78)
 if k.startswith(('21','22')):return (.17,.43,.30)
 if k.startswith('REF'):return (.70,.73,.77)
 if k.startswith(('02','07','08','09')):return (.85,.40,.14)
 return (.26,.32,.39)
def render(filename,selected,offsets=None,camera=(60,170,90),focus=(75,4,0),scale=50,size=(1800,800),paper_rotation=False):
 ren=vtk.vtkRenderer();ren.SetBackground(.963,.969,.976)
 offsets=offsets or {}
 for k in selected:
  m=meshes[k].copy();m.apply_translation(offsets.get(k,(0,0,0)))
  if paper_rotation:m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(-55),(0,1,0)))
  pd=vtk.vtkPolyData();pts=vtk.vtkPoints();pts.SetData(numpy_to_vtk(m.vertices.astype(np.float64),deep=True));pd.SetPoints(pts)
  cells=vtk.vtkCellArray();arr=np.c_[np.full(len(m.faces),3),m.faces].astype(np.int64).ravel()
  cells.SetCells(len(m.faces),numpy_to_vtkIdTypeArray(arr,deep=True));pd.SetPolys(cells)
  norm=vtk.vtkPolyDataNormals();norm.SetInputData(pd);norm.SetFeatureAngle(35);norm.SplittingOn();norm.ConsistencyOn();norm.Update()
  mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(norm.GetOutputPort())
  ac=vtk.vtkActor();ac.SetMapper(mapper);ac.GetProperty().SetColor(*color(k));ac.GetProperty().SetAmbient(.18);ac.GetProperty().SetDiffuse(.8);ac.GetProperty().SetSpecular(.25);ac.GetProperty().SetSpecularPower(35)
  ren.AddActor(ac)
 light=vtk.vtkLightKit();light.SetKeyLightIntensity(.85);light.AddLightsToRenderer(ren)
 cam=ren.GetActiveCamera();cam.SetPosition(*camera);cam.SetFocalPoint(*focus);cam.SetViewUp(0,0,1);cam.ParallelProjectionOn();cam.SetParallelScale(scale)
 win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.AddRenderer(ren);win.SetSize(*size);win.SetMultiSamples(8);ren.ResetCameraClippingRange();win.Render()
 snap=vtk.vtkWindowToImageFilter();snap.SetInput(win);snap.SetInputBufferTypeToRGB();snap.ReadFrontBufferOff();snap.Update()
 writer=vtk.vtkPNGWriter();writer.SetFileName(str(OUT/filename));writer.SetInputConnection(snap.GetOutputPort());writer.Write();win.Finalize()



parts=[n for n in meshes if not n.startswith(('REF','10_','11_'))];shell=[n for n in parts if not n.startswith('2')];dummies=[n for n in parts if n.startswith('2')];refs=[n for n in meshes if n.startswith('REF')]
render('assembly.png',parts+refs,camera=(35,-185,105),focus=(102,5,0),scale=54,size=(1800,850))
render('open_case.png',[n for n in parts+refs if n!='04_press_release_cover'],camera=(45,-180,125),focus=(105,3,0),scale=54,size=(1800,850))
off={'04_press_release_cover':(0,0,36),'22_rear_board_dummy_75x24':(0,0,17),'20_battery_dummy_36x12x6':(0,0,10),'09_optical_lid':(0,0,14),'21_PAT9125_dummy_14x15':(0,0,7),'02_threaded_nose':(-8,0,0)}
render('exploded.png',parts+refs,off,camera=(25,-195,135),focus=(102,5,15),scale=62,size=(1800,1000))
# Hardware reference view in a common plane, independent of assembled positions.
for n in dummies:
 m=meshes[n]
 if n.startswith('21'):m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(-55),(0,1,0)))
 m.apply_translation(-m.bounds[0])
render('hardware.png',dummies,{'20_battery_dummy_36x12x6':(0,0,0),'21_PAT9125_dummy_14x15':(44,0,0),'22_rear_board_dummy_75x24':(68,0,0),'23_EVQQ2B03W_dummy':(153,0,0)},camera=(45,-175,140),focus=(82,8,0),scale=41,size=(1800,800))
# Annotated printable-file overview.
canvas=Image.new('RGB',(1800,2140),'#f6f7f9');d=ImageDraw.Draw(canvas)
d.text((60,30),'手写笔 v0.5 · 适配现后板与成品光学模块',font=font(38),fill='#203143')
d.text((60,88),'电池在前、后板在后 · 总长 206 mm · 后仓主体 28.4 × 14 mm · J402 线槽处宽 34.7 mm',font=font(25),fill='#607084')
canvas.paste(Image.open(OUT/'assembly.png'),(0,140))
d.text((60,915),'一体前筒与旋拧笔头；光学线与笔芯分隔；后盖卡扣。',font=font(27),fill='#203143')
canvas.paste(Image.open(OUT/'exploded.png'),(0,970))
d.text((60,1980),'后板 70 × 24 mm，含 ESP 天线总长 75 mm；电池 36 × 12 × 6 mm。',font=font(25),fill='#203143')
d.text((60,2040),'适配 EVQQ2B03W；光学板厚度 / 针脚高度及工作距仍待实物验证。',font=font(25),fill='#9b5e28')
canvas.save(OUT/'01_v05_overview.png')
canvas=Image.new('RGB',(1800,1040),'#f6f7f9');d=ImageDraw.Draw(canvas)
d.text((60,35),'四个独立可打印占位件 · 保持 100% 比例',font=font(38),fill='#203143')
canvas.paste(Image.open(OUT/'hardware.png'),(0,110))
d.text((60,880),'20 电池：36×12×6    21 光学板：14×15    22 R26后板：含器件    23 微动：EVQQ2B03W',font=font(25),fill='#203143')
d.text((60,943),'芯片以简化实体表达尺寸；占位件用于空间 / 插座位置参考，不用于检验真实插头配合。',font=font(23),fill='#9b5e28')
canvas.save(OUT/'02_hardware_dummies.png')
# Detail views use assembled coordinates before hardware normalization.
meshes={p.stem:meshstep(p) for p in (ROOT/'cad').glob('[0-9]*.step')}
render('03_switch_exploded.png',['05_switch_carrier_lower','06_switch_carrier_upper','07_refill_plunger','23_EVQQ2B03W_dummy'],
       {'06_switch_carrier_upper':(0,0,10),'07_refill_plunger':(-6,0,3),'23_EVQQ2B03W_dummy':(0,0,3)},
       camera=(40,-45,33),focus=(68,0,5),scale=15,size=(1400,1000))
s=cq.importers.importStep(str(ROOT/'cad/01_one_piece_barrel.step')).val()
cut=cq.Solid.makeBox(2,30,30,cq.Vector(45,-15,-15))
v,f=s.intersect(cut).tessellate(.04,.09)
meshes['CUT_barrel']=trimesh.Trimesh([p.toTuple() for p in v],f,process=True)
render('04_wire_duct_section.png',['CUT_barrel'],camera=(70,0,0),focus=(46,0,0),scale=8,size=(1000,1000))
render('05_optical_exploded.png',['08_optical_cassette','09_optical_lid','21_PAT9125_dummy_14x15'],
       {'09_optical_lid':(9,0,6),'21_PAT9125_dummy_14x15':(4,0,2.5)},
       camera=(50,-65,80),focus=(15,18,10),scale=22,size=(1400,1000))
print('Rendered v0.5 previews')

# Identify every printed part using its actual printing mesh, not a stock icon.
labels={'01':'一体前筒 + 光学支架','02':'旋拧笔头','03':'后仓底壳','04':'卡扣上盖',
        '05':'微动下托','06':'微动上托','07':'标准顶杆 3.4 mm','08':'光学模块框',
        '09':'光学模块盖','10':'备用短顶杆 3.2 mm','11':'备用长顶杆 3.6 mm',
        '20':'电池尺寸替身','21':'光学板尺寸替身','22':'R26后板尺寸替身','23':'微动尺寸替身'}
cards=Image.new('RGB',(1800,2290),'#f6f7f9');draw=ImageDraw.Draw(cards)
draw.text((35,22),'单盘共15件 · 07 / 10 / 11 顶杆三选一 · 20～23仅用于空壳试配',font=font(30),fill='#203143')
for idx,path in enumerate(sorted((ROOT/'stl').glob('*.stl'))):
 key=path.stem;m=trimesh.load_mesh(path);meshes[key]=m
 c=m.bounds.mean(axis=0);extent=max(m.extents);cam=c+np.array([.35,-1.8,1.35])*extent
 render('part_'+key+'.png',[key],camera=cam,focus=c,scale=extent*.65,size=(600,380))
 x=(idx%3)*600;y=80+(idx//3)*440
 cards.paste(Image.open(OUT/('part_'+key+'.png')),(x,y))
 draw.text((x+20,y+377),key[:2]+' '+labels[key[:2]],font=font(25),fill='#203143')
cards.save(OUT/'06_all_15_parts.png')
