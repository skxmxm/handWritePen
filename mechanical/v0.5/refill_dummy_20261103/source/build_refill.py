from pathlib import Path
import json, zipfile, hashlib
import xml.etree.ElementTree as ET
import cadquery as cq
import trimesh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT.parent
def cyl(radius, length, x):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(x,0,0), cq.Vector(1,0,0))

# Identical to the existing v0.5 REF_gel_refill reference envelope.
# X=0 is the front, X=67 is the rear contact with the nominal plunger.
refill = cyl(1.25,7.5,0).fuse(
    cq.Solid.makeCone(1.25,3,3,cq.Vector(7.5,0,0),cq.Vector(1,0,0)),
    cyl(3,56.5,10.5)).clean()
assert refill.isValid() and len(refill.Solids()) == 1
cq.exporters.export(refill, str(ROOT/'笔芯样件_67mm_装配坐标.step'))
# Tail down: x=67 -> z=0, x=0 -> z=67. No supports or glued halves.
printable = refill.rotate((0,0,0),(0,1,0),90).translate((0,0,67))
vertices, faces = printable.tessellate(.015,.05)
m = trimesh.Trimesh([v.toTuple() for v in vertices], faces, process=True)
assert m.is_watertight and m.is_winding_consistent and m.volume > 0
assert len(m.split()) == 1 and np.allclose(m.extents,[6,6,67],atol=.003)
assert abs(m.bounds[0,2]) < .00001
m.export(ROOT/'笔芯样件_67mm_尾端朝下.stl')

names=['01_one_piece_barrel','02_threaded_nose','05_switch_carrier_lower','06_switch_carrier_upper']
fixed={n:cq.importers.importStep(str(SHELL/'cad'/f'{n}.step')).val() for n in names}
checks=[]
for dx in [-.50,0,.20,.30]:
    overlap={n:refill.translate((dx,0,0)).intersect(s).Volume() for n,s in fixed.items()}
    assert max(overlap.values()) < 1e-6, (dx,overlap)
    checks.append({'axial_shift_mm':dx,'overlap_mm3':overlap})
# Verify the front stop using actual exported nose, not just the nominal hole.
nose=fixed['02_threaded_nose']
assert refill.translate((-.60,0,0)).intersect(nose).Volume() > 0.01
plunger=cq.importers.importStep(str(SHELL/'cad/07_refill_plunger.step')).val()
assert abs(plunger.BoundingBox().xmin-67) < 1e-5
assert refill.intersect(plunger).Volume() < 1e-6

NS='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
ET.register_namespace('',NS)
def tag(s): return '{'+NS+'}'+s
model=ET.Element(tag('model'),unit='millimeter')
resources=ET.SubElement(model,tag('resources'))
ob=ET.SubElement(resources,tag('object'),id='1',type='model',name='Refill_67mm_D6_fit_dummy')
me=ET.SubElement(ob,tag('mesh')); vs=ET.SubElement(me,tag('vertices')); fs=ET.SubElement(me,tag('triangles'))
for v in m.vertices: ET.SubElement(vs,tag('vertex'),**{k:f'{val:.7f}' for k,val in zip('xyz',v)})
for f in m.faces: ET.SubElement(fs,tag('triangle'),**{k:str(val) for k,val in zip(['v1','v2','v3'],f)})
build=ET.SubElement(model,tag('build'))
ET.SubElement(build,tag('item'),objectid='1',transform='1 0 0 0 1 0 0 0 1 128 128 0')
with zipfile.ZipFile(ROOT/'refill_geometry_mm.3mf','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    z.writestr('3D/3dmodel.model',ET.tostring(model,encoding='utf-8',xml_declaration=True))

process=json.loads((SHELL/'print_support_fix_20261030/source/process.json').read_text())
process.update({'name':'Refill 67mm upright PLA P1S',
    'enable_support':'0','raft_layers':'0','brim_type':'outer_only','brim_width':'8','brim_object_gap':'0.08',
    'layer_height':'0.16','initial_layer_print_height':'0.2','wall_loops':'4','sparse_infill_density':'25%',
    'sparse_infill_pattern':'gyroid','enable_arc_fitting':'0',
    'initial_layer_speed':['15','15'],'initial_layer_infill_speed':['20','20'],
    'outer_wall_speed':['25','25'],'inner_wall_speed':['30','30'],
    'internal_solid_infill_speed':['30','30'],'sparse_infill_speed':['30','30'],
    'gap_infill_speed':['25','25'],'top_surface_speed':['25','25'],
    'default_acceleration':['500','500'],'outer_wall_acceleration':['400','400'],
    'inner_wall_acceleration':['500','500'],'top_surface_acceleration':['400','400'],
    'initial_layer_acceleration':['300','300'],'initial_layer_travel_acceleration':['500','500'],
    'travel_speed':['120','120'],'travel_acceleration':['1000','1000']})
filament=json.loads((SHELL/'print_support_fix_20261030/source/filament.json').read_text())
filament['name']='PLA refill sample textured PEI'
filament.update({'slow_down_for_layer_cooling':['1'],'slow_down_min_speed':['10'],
    'fan_cooling_layer_time':['30'],'slow_down_layer_time':['10'],
    'additional_cooling_fan_speed':['0']})
(ROOT/'source/process.json').write_text(json.dumps(process,indent=2))
(ROOT/'source/filament.json').write_text(json.dumps(filament,indent=2))
report={'length_mm':67,'body_diameter_mm':6,'body_length_mm':56.5,'transition_length_mm':3,
    'front_guide_diameter_mm':2.5,'front_guide_length_mm':7.5,'matches_v05_reference':True,
    'cad_valid':True,'single_solid':True,'watertight':True,'print_bounds_mm':m.bounds.tolist(),
    'volume_mm3':refill.Volume(),'nominal_plunger_contact_x_mm':67,'shell_checks':checks,
    'forward_stop_between_shift_mm':[-.60,-.50],
    'source_shell_sha256':{n:hashlib.sha256((SHELL/'cad'/f'{n}.step').read_bytes()).hexdigest() for n in names},
    'physical_test':'not performed; refill SKU and real nose dimensions unknown'}
(ROOT/'reports/geometry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'dimensions_mm':m.extents.tolist(),'solid_volume_mm3':refill.Volume(),'checks':'passed'}))
