from pathlib import Path
import json,zipfile
import xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1]
NS={'c':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
PN='http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
def mesh_info(ob):
    mesh=ob.find('c:mesh',NS)
    vertices=[tuple(float(q.attrib[k]) for k in ('x','y','z')) for q in mesh.findall('c:vertices/c:vertex',NS)]
    faces=[tuple(int(q.attrib[k]) for k in ('v1','v2','v3')) for q in mesh.findall('c:triangles/c:triangle',NS)]
    volume=0.0
    for a,b,c in faces:
        a,b,c=vertices[a],vertices[b],vertices[c]
        volume+=a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0])
    return {'faces':len(faces),'volume_mm3':abs(volume)/6,'dimensions_mm':[max(v[i] for v in vertices)-min(v[i] for v in vertices) for i in range(3)]}
slices=[]
for fn,count in [('v05_all_parts_P1S_PLA_prepared.3mf',15)]:
    with zipfile.ZipFile(R/fn) as z:
        settings=json.loads(z.read('Metadata/project_settings.config'))
        xml=ET.fromstring(z.read('Metadata/slice_info.config'))
        plate=xml.findall('plate')
        assert len(plate)==1
        md={m.attrib['key']:m.attrib['value'] for m in plate[0].findall('metadata')}
        objects=[q.attrib for q in plate[0].findall('object')]
        assert len(objects)==count and all(q['skipped']=='false' for q in objects)
        assert settings['printer_model']=='Bambu Lab P1S' and settings['nozzle_diameter']==['0.4']
        assert settings['filament_type']==['PLA'] and md['outside']=='false'
        assert len(z.read('Metadata/plate_1.gcode'))>10000
        assert settings['print_sequence']=='by layer', 'Keep multi-part plate in by-layer mode'
        mesh=ET.fromstring(z.read('Metadata/model_settings.config'))
        repaired=[]
        for obj in mesh.findall('object'):
            for st in obj.findall('./part/mesh_stat'):
                errors={k:int(v) for k,v in st.attrib.items() if k!='face_count' and int(v)!=0}
                if errors: repaired.append(dict(object_id=obj.attrib['id'],repairs=errors))
        assert not repaired
        # Compare embedded model geometry against freshly exported input, not only filenames.
        input_fn=fn.replace('_P1S_PLA_prepared','_geometry_mm')
        with zipfile.ZipFile(R/input_fn) as zin:
            inputs=ET.fromstring(zin.read('3D/3dmodel.model'))
        expected={ob.attrib['name']:mesh_info(ob) for ob in inputs.findall('c:resources/c:object',NS)}
        names={ob.attrib['id']:ob.find("metadata[@key='name']").attrib['value'] for ob in mesh.findall('object')}
        model=ET.fromstring(z.read('3D/3dmodel.model'));matches=[]
        for ob in model.findall('c:resources/c:object',NS):
            name=names[ob.attrib['id']]
            c=ob.find('c:components/c:component',NS)
            child=ET.fromstring(z.read(c.attrib['{'+PN+'}path'].lstrip('/')))
            actual=mesh_info(child.find("c:resources/c:object[@id='"+c.attrib['objectid']+"']",NS))
            ref=expected[name]
            assert actual['faces']==ref['faces'],(name,'stale facet count')
            assert abs(actual['volume_mm3']-ref['volume_mm3'])<.03,(name,'stale volume',actual,ref)
            assert max(abs(a-b) for a,b in zip(actual['dimensions_mm'],ref['dimensions_mm']))<.0001,(name,'wrong scale')
            matches.append({'name':name,**actual})
        name={15:'all_parts'}[count]
        for source,target in [('Metadata/plate_1.png',f'slicer_{name}.png'),('Metadata/top_1.png',f'slicer_{name}_top.png')]:
            (R/'previews'/target).write_bytes(z.read(source))
        slices.append(dict(file=fn,printer=settings['printer_model'],nozzle_mm=.4,material='PLA',plate_count=1,
            print_sequence=settings['print_sequence'],objects=objects,current_geometry_matches=matches,predicted_seconds=int(md['prediction']),predicted_grams=float(md['weight']),
            outside=False,mesh_repairs=repaired,layer_height_mm=float(settings['layer_height']),wall_loops=int(settings['wall_loops']),
            infill=settings['sparse_infill_density'],infill_pattern=settings['sparse_infill_pattern'],
            support_used=md['support_used'],support_build_plate_only=settings['support_on_build_plate_only'],
            brim_mm=float(settings['brim_width']),bed=settings['curr_bed_type'],
            nozzle_temperature=settings['nozzle_temperature'],bed_temperature=settings['textured_plate_temp']))

result={'slicer_results':slices,'scope':'Local slicer validation only; no print was sent or physically tested.'}
(R/'reports/slicing_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
