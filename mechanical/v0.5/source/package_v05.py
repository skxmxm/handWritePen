from pathlib import Path
import hashlib,json,re,zipfile
R=Path(__file__).resolve().parents[1]
required=['v05_all_parts_P1S_PLA_prepared.3mf','v05_all_parts_geometry_mm.3mf','v05_shell_geometry_mm.3mf','v05_hardware_dummies_geometry_mm.3mf','打印与装配说明.md','rear_board_mechanical_input.json','rear_board_mechanical_input.md']
files=[R/n for n in required]
for directory in ('cad','stl','source','previews','reference','reports'):
 files += [p for p in (R/directory).rglob('*') if p.is_file() and p.suffix not in ('.pyc','.log') and '__pycache__' not in p.parts]
files=sorted(set(files));assert all(p.exists() for p in files)
# Ensure all local images in the assembly manual exist in the package.
for href in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',(R/'打印与装配说明.md').read_text()):assert (R/href).exists(),href
hashes={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(R/'SHA256SUMS.txt').write_text(''.join(h+'  '+n+'\n' for n,h in hashes.items()))
files.append(R/'SHA256SUMS.txt')
name='手写笔_v0.5_206mm_36x12x6电池_完整打印包.zip'
with zipfile.ZipFile(R/name,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files:z.write(p,Path('手写笔_v0.5')/p.relative_to(R))
with zipfile.ZipFile(R/name) as z:
 assert z.testzip() is None
 for n,h in hashes.items():assert hashlib.sha256(z.read('手写笔_v0.5/'+n)).hexdigest()==h
print(json.dumps({'package':str(R/name),'files':len(files),'size_bytes':(R/name).stat().st_size,'zip_integrity':'passed'},ensure_ascii=False))
