# 多模态智能手写笔 · handWritePen

华东师范大学智能系统创新实验室。纸面书写轨迹、笔身姿态与皮肤电同步采集原型，ESP32-S3 通过 BLE 连接 Python 上位机。

**当前整理快照：2026-11-06。硬件仍处于实板调试，冷启动故障未解决；发生火花的板子已断开电池和 USB，暂停上电。**详见[已知问题](docs/KNOWN_ISSUES.md)。这里的设计文件检查通过不等于整机实物验收通过。

| 部分 | 最新版本 | 入口 |
|---|---|---|
| 后板电路与布局布线 | ESP32 V0.3 / R26，2026-10-09 | [原理图＋PCB完整原生工程](hardware/rear_R26/Rear_ESP32S3_R26.epro) · [PCB文件](hardware/rear_R26/Rear_ESP32S3_R26.epcb) |
| 制板 / 自焊 | R26 原始 Gerber，2026-10-12 自焊资料 | [Gerber](hardware/rear_R26/后板_R26_制板文件.zip) · [钢网原始层](hardware/rear_R26/后板_R26_钢网原始层.zip) · [BOM](hardware/rear_R26/BOM_FIT_REVIEW.csv) |
| Arduino 固件 | **v0.61**，2026-11-05 | [Pen_R26_Live.ino](firmware/Pen_R26_Live/Pen_R26_Live.ino) · [固件说明](firmware/Pen_R26_Live/README.md) |
| Python 上位机 | **v0.60 功能代码**，随 v0.61 包交付 | [pen_live.py](software/PenLive/pen_live.py) · [使用说明](software/PenLive/使用说明.md) |
| 外壳参考 | v0.5，2026-10-30 支撑修正版 | [单盘15件3MF](mechanical/v0.5/print_support_fix_20261030/手写笔_v05_完整单盘15件_P1S_PLA_支撑修正版.3mf) · [装配说明](mechanical/v0.5/打印与装配说明.md) |

Python 在 v0.61 中没有功能代码更新；不能把整包版本号当作上位机又更新了一版。配套关系、校验值见 [VERSION.json](VERSION.json) 和 [文件清单](MANIFEST_SHA256.json)。

## 硬件

- ESP32-S3-MINI-1-N4R2，板载天线；后板 70×24×1 mm、四层，含模块的纵向包络约75 mm。
- 光学前端使用采购的 **PAT9125EL-TKIT**，不制造旧自制 Front_Optical 草案。完整 EPRO 为原始工程快照，其中的历史前板不代表当前选型。
- JY901S 裸模块焊装；ADS1115 读取 GSR_ADC / VEX_MON；BQ25185 充电与电源路径、TPS63802 主电源。
- [端口与接线](hardware/接线与外购件说明_R26.md) · [光学板接入](hardware/pcb/front_optical/成品模块接入说明.md) · [硬件文件说明](hardware/rear_R26/README.md)。

## 软件行为

- 皮肤电和姿态持续显示；微动按下画线，松开只移动光标、保留笔画。
- 光学采集目标200 Hz，批量发送目标50次/秒，主遥测目标25 Hz；实际速率以实板测量为准。
- 上位机提供可关闭的轻度/标准轨迹平滑，默认反转Y；丢包时断线，不伪造缺失轨迹。
- GSR 仅在无USB、BLE订阅且检查通过时开启；USB接入/断连/异常时关闭。数值未标定，不能直接当作压力等级或诊断结果。
- v0.61：进入应用后SYS/FAULT常亮，初始化首次处理完成后同步闪烁5秒，再进入正常模式；这不是冷启动硬件故障修复。

## 使用

Arduino IDE 打开整个 `firmware/Pen_R26_Live` 文件夹中的 INO，保留全部头文件。ESP32S3 Dev Module、4MB Flash、QSPI PSRAM、Huge APP、Hardware CDC/JTAG、USB CDC On Boot Enabled。已验证板包3.2.1-cn；更多设置见[使用说明](software/PenLive/使用说明.md)。

电脑使用带Tk的 Python 3.10–3.13（推荐3.12）：

```sh
cd software/PenLive
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python pen_live.py
```

macOS也可运行 `启动上位机.command`，Windows运行 `启动上位机.bat`。无硬件界面演示使用 `python pen_live.py --demo`。历史完整软件包：[v0.61 ZIP](releases/手写笔_R26_BLE_v061_启动灯光版.zip)。ZIP保持原始字节，其中的故障状态记录截至打包当天；当前状态以本仓库为准。

## 验证与维护

- [此次整理验证](docs/VALIDATION.md)；[此前软件验证记录](software/PenLive/验证记录.md)。历史模拟吞吐不代表实物BLE性能。
- `hardware/rear_R26`、`firmware/Pen_R26_Live`、`software/PenLive` 是本仓库的维护入口；旧nRF方案、早期布局候选、重复解压包及本机运行环境未混入。
- 外壳STEP/STL及生成脚本在 `mechanical/v0.5`；CAD/切片脚本含原工作区依赖，跨机器再生成前需调整路径，现成模型可直接打开。光学工作距离、笔芯公差及打印结果仍需验证。
- 本次未添加开源许可证，上传本身不等于授予额外许可。
