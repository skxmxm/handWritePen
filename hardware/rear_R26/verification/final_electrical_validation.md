# R26 最终电气与 CAM 独立复核

结论：**全部通过**。仅适用于本报告记录 SHA-256 的 R26 文件。

| 检查 | 结果 |
|---|---|
| authorized_move_list_exactly_11_components_and_1_via | 通过 |
| candidate_bound_to_baseline | 通过 |
| one_explicit_authorized_ground_via_added | 通过 |
| primitive_identity_sets_match_baseline_plus_one_authorized_via | 通过 |
| all_unapproved_fields_unchanged | 通过 |
| all_authorized_placements_and_pad_rigid_transforms_match | 通过 |
| candidate_trace_copper_matches_with_2nm_tolerance_no_exceptions | 通过 |
| native_rules_layers_and_board_outline_unchanged | 通过 |
| native_DRC_empty | 通过 |
| actual_CAM_no_short | 通过 |
| actual_CAM_all77_named_nets_single_group | 通过 |
| all_pad_via_centres_present | 通过 |
| actual_CAM_no_floating_copper | 通过 |
| all418_pad_copper_mask_paste | 通过 |
| USB_all_top_no_signal_vias | 通过 |
| USB_fullwidth_L2_GND | 通过 |
| all9_keepouts_clear | 通过 |
| free_sharp_angles_including90 | 通过 |
| C302_GND_connected_in_actual_CAM_to_U301_and_single_GND_group | 通过 |
| USB_report_current_snapshot | 通过 |

## 修改边界与实铜结果

授权范围为 11 个元件刚性变换、1 个 BAT_DIV 过孔移位，以及为连接实际 CAM 已确认的 GND 铜岛新增 1 个双面盖油通孔（7734bc0f3cf670f5，盘径 0.45212 mm / 孔径 0.20828 mm）。过孔总数 231；未授权字段差异 0 项。
实际 Gerber：77 个命名网络，短路 0、缺失中心 0、浮铜组 0；418 个焊盘执行铜/阻焊/适用锡膏检查。
C302.2 (d57e16) 与 U301.4 (d49e34) 的实际铜组分别为 [88]、[88]，GND 总组数 1。
USB 位于顶层、信号过孔 0；L2 参考地缺失中心线 0 mm，缺失全宽面积 0 mm²。9 个实际磁/RF 禁布区独立核验。
源生规则/层/板框记录比对 94 项；差异 0 项。自由锐角/直角 0 处。

## 误差与适用范围

- Independent computational checks of the specific exported source/CAM; not a physical bring-up guarantee or IPC/USB certification.
- Gerber arcs approximated to 1 um; center attachment tolerance 1.5 um. All-pad aperture core inset 3 um compensates API 0.1 mil rounding.
- Moved pad API centers allow at most 0.1 mil (2.54 um) per axis relative to the candidate derived from a previously rounded API snapshot. Only rigidly moved pads are eligible. Net, pad number, shape, layers, mask/paste and other metadata stay exact. Rotation is compared modulo 360 degrees.
- Authorized moved component/via centers match the precise target or its exact native four-decimal-mil rounded value (at most 1.27 nm per axis), as observed after native reopen. Unmoved primitives remain exact. The added GND via is checked against its fixed ID and full specified attributes.
- All per-net/per-layer trace unions use a separate 2 nm mutual buffer and area cutoff 1e-8 mm2, with no carried native-merge exception.
- Parent release checks separately cover native source/EPRO geometry roundtrip, unchanged libraries and schematics, silk, body clearance, assembly BOM/CPL, actual via-in-pad inventory, package integrity, and manufacturing process notes.
- Manufacturing requires JLC04101H-3313 4-layer 1.00 mm stack, outer 1 oz/inner 0.5 oz, specified impedance and filled/capped vias, correct SMT/post-assembly process, and first-article measurements. No order is placed.

## 源文件绑定

| 文件 | SHA-256 |
|---|---|
| before_pcb.json | `2dbf074013debb0a0c4e68ba804aee01d823710963692186b34edba4df8706f8` |
| combined_candidate.json | `eae0018c7d89063fd82ac844013f126a7dbb9a98f12cda09ed4ffb810e169ced` |
| combined_pcb.json | `03ec8dc5ffe8da1826865723bf46eb0ab52047e4c48e1e8a6b224c361bb8d426` |
| ground_repair_candidate.json | `52669c2525a991f3d7fc4d072da32b7de99422fd85d97d62789d967c19d7870e` |
| ground_repair_applied.json | `cb5b598307519e2c2742f2dc1adc46021b651ef700ba1d44113868669a72698c` |
| native_merge_cleanup_candidate.json | `e38dad455efe6b51d69683c37b9f8c52edd1450b873a6a80dc1be4c03844df35` |
| native_merge_cleanup_validation.json | `61ff549391f8c2285b1d8b64bd4f2de7da6e4a51a2a36c9c2f45cacb9076696c` |
| final_pcb.json | `9f1e877030447fde3a9d45c8e63cae7cf1cb643a3251bc521f28f9020e10c48f` |
| before.epcb | `73fc62c73e56c1e16e86e71287f5cf5f77beb525821c82b0784ed47703cf869b` |
| final.epcb | `2084b7d1679660983e0aba47732dc202a9a4d21de6be4fd8f3032b068aedf13d` |
| Rear_ESP32S3_R26.epro | `94c581d00881a50d9d480f48da7cbc3cddc21054f8db267162a087efbe41d56c` |
| final_native.zip | `cb2dc0239f3795e9e0eb28c82b485480c3a45c57e0289df6f4cfc57a33633a77` |
| final_DRC.json | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| final_independent_copper.json | `844c13cdc19f533967ceb3f80e4914e0954802d312e39d3bf3ca884cf93422e2` |
| final_all_pad_CAM_validation.json | `54b3d4cd1c673bc89abff870872d9ee9c44a14d8aea99f3cc049d0a10bc23a48` |
| final_critical_paths_usb.json | `953df96a8ddc61e985a6a1fd00ac02117cf463f9eeb4da4b38de32568d4e8770` |
| final_pcb_sharp.json | `f5f87b8a6656fbf3eeaabfbe0421b22da7e88406492d2e1116215e440cdff245` |
