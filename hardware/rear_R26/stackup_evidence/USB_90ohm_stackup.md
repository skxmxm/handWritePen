# 1.0 mm rear PCB USB controlled-impedance selection

2026-10-07. This is a read-only public manufacturer inquiry and calculation; no account, order, board upload, or production request was created.

## Concrete selection

**Use JLC04101H-3313, 4 layers, nominal finished 1.00 mm ±10%, 1 oz outer / 0.5 oz inner copper. Preserve the current 0.15 mm trace width and 0.15 mm pair edge-gap.** The manufacturer's current coated differential calculator gives **87.785 ohms** for the non-coplanar pair and **85.551–87.837 ohms** when considering same-layer GND from 0.127 to 0.500 mm away. These nominal values are within 90 ohms ±10% (81–99 ohms). Do not select “No requirement” stack: its 7628 dielectric would give **105.583 ohms** for the same non-coplanar pair and miss that target.

The current geometry therefore has a concrete manufacturable stackup basis. There is no need to narrow existing tracks solely to make the nominal answer exactly 90; preserving 0.15 mm copper width keeps the already audited geometry and more process margin than a thinner option.

This is a manufacturer-calculated nominal result, not an impedance test or a statistical production-tolerance proof. The fabrication specification must explicitly identify this stack, USB L1/L2 reference, 90 ohms ±10%, and request impedance control/coupon verification. No order is being placed here.

## Authoritative sources

- [JLCPCB official stackup page](https://jlcpcb.com/impedance)
- [JLCPCB official impedance calculator](https://jlcpcb.com/pcb-impedance-calculator)
- [嘉立创 Chinese official tool](https://tools.jlc.com/jlcTools/#/impedanceCalculate)

The public UI-backed, read-only template lookup also returned the identical Chinese template: **JLC04101H-3313(成品板厚1.00mm±10%)**, template access ID `ec061f4270694a2fb0dbaf1e51681920`, laminated construction code `20211110052902`, `chargeFlag=false`, `laminationBatchCustomMade=0`. Do not interpret these flags as a binding price quotation; they distinguish it from the listed special/custom stackups.

Raw lookup responses, exact requests, frontend references, and SHA256 manifest are archived in this directory. `cn_templates0.json` establishes domestic-tool availability; `overseas-core-platform.json` independently gives the public stack table.

## Stack and calculation parameters

| Item | Official template / current calculator value |
|---|---|
| Nominal finished thickness | 1.00 mm ±10% |
| L1–L2 prepreg | 3313 RC57%, 0.09940 mm, Dk 4.1 |
| L2–L3 core dielectric | 0.700 mm, Dk 4.53 in calculator template |
| L3–L4 prepreg | 3313 RC57%, 0.09940 mm, Dk 4.1 |
| Outer copper stated in stack table | 0.035 mm |
| Inner copper | 0.0152 mm each |
| Calculator effective outer trace T1 | 1.6 mil = 0.04064 mm, from 0.5 oz base / 1 oz system copper configuration |
| Etched trapezoid W1–W2 | 0.5 mil = 0.01270 mm |
| W1 lower / W2 upper | 0.1500 / 0.1373 mm |
| Differential edge gap S1 | 0.1500 mm |
| Solder mask C1 / C2 / C3 | 1.0 / 0.6 / 1.0 mil, from current calculator configuration |
| Solder mask dielectric CEr | 3.8 |

The general stack web page lists 1.2/0.6/1.2 mil mask assumptions; the current calculation frontend queries 1.0/0.6/1.0 for this outer copper. We intentionally used the *current calculator's own parameters*, archived in `coverlay.json` and `copper.json`, rather than silently mixing the older text defaults.

The 1.6 mil calculation copper vs nominal 35 micrometre stack copper is also explicit. Recalculation at 35 micrometres yielded 89.160 ohms non-coplanar and 87.072 ohms with 0.127 mm coplanar GND gap, both still inside 81–99 ohms.

## Official numerical results

All lengths sent to the calculator are in **mil**: mm / 0.0254. Each request uses the public calculator's model, parameter format, and result WebSocket. Each stored response reports `impedance_calc_status=0`, `dResultValid=1`. These are real returned results, not values inferred from a screenshot or a homemade formula.

| Stack / W / S | Model or same-layer GND gap | Official result |
|---|---|---:|
| 3313, 0.15 / 0.15 mm | Coated edge-coupled microstrip | 87.785 Ω |
| 3313, 0.15 / 0.15 mm | Coated coplanar, 0.127 mm GND gap | 85.551 Ω |
| 3313, 0.15 / 0.15 mm | Coated coplanar, 0.150 mm GND gap | 86.304 Ω |
| 3313, 0.15 / 0.15 mm | Coated coplanar, 0.300 mm GND gap | 87.670 Ω |
| 3313, 0.15 / 0.15 mm | Coated coplanar, 0.500 mm GND gap | 87.837 Ω |
| 3313, 0.14 / 0.15 mm | Coated edge-coupled microstrip | 90.385 Ω |
| 3313, 0.14 / 0.15 mm | Coated coplanar, 0.127 mm GND gap | 88.064 Ω |
| 3313, 0.14 / 0.15 mm | Coated coplanar, 0.300 mm GND gap | 90.276 Ω |
| 7628, 0.15 / 0.15 mm | Coated edge-coupled microstrip | 105.583 Ω |

## How it applies to the current PCB

The controlled section is the paired L1 trunk above continuous L2 GND. Short ESD, series-resistor and connector fanouts cannot be represented by one uniform 2D cross-section; the report does not claim every millimetre has exactly the same impedance. Preserve the continuous L2 reference and avoid isolated/necked same-layer islands. Retain the 1 mm board goal and antenna keepouts.

Release specification text:

> 4L FR4, JLC04101H-3313, nominal finished 1.00 mm ±10%; outer copper 1 oz, inner 0.5 oz. USB_D+/D− paired trunk on L1 references L2 GND; design width/gap 0.15/0.15 mm, target 90 Ω ±10%. Use the named stack and controlled-impedance process/coupon. Any CAM width/gap or stack substitution must be reviewed against the final geometry, clearance, and continuity checks before manufacture.

This closes the missing *design stack/calculation basis*. It does not replace final CAM review, manufacturer process confirmation, or USB bring-up measurements.

Domestic calculator cross-check: the same 3313 / 0.15 / 0.15 mm / 0.127 mm coplanar-ground geometry was also submitted directly to `https://tools.jlc.com/api/jlcTools/impedance/calc` with the Chinese tool's `wss://tools.jlc.com/api/jlcTools/webSocket/` result channel. It independently returned the identical **85.5511822378 ohms**, status 0 / result-valid 1. Stored as `calc_CN_3313_150_150_G127_request.json` and `_response.json`.
