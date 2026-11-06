#!/bin/zsh
set -eu
pen_root="$(cd "$(dirname "$0")/.." && pwd)"
pen_studio="${BAMBU_STUDIO_BIN:-/Applications/BambuStudio.app/Contents/MacOS/BambuStudio}"
pen_slice_data="${PEN_SLICER_DATA:-${TMPDIR:-/tmp}/smart-pen-v05-slicer}"
"$pen_studio" --datadir "$pen_slice_data" --debug 2 \
  --load-settings "$pen_root/source/slicer/P1S_0p4.json;$pen_root/source/slicer/pen_PLA_0p16.json" \
  --load-filaments "$pen_root/source/slicer/Generic_PLA.json" \
  --arrange 1 --orient 0 --ensure-on-bed --slice 0 \
  --export-3mf v05_all_parts_P1S_PLA_prepared.3mf --outputdir "$pen_root" \
  "$pen_root/v05_all_parts_geometry_mm.3mf" > "$pen_root/reports/slicer_all_parts.log" 2>&1
