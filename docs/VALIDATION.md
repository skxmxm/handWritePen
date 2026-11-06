# 2026-11-06 仓库整理验证

此次整理不修改当前整笔固件、Python功能代码或R26电气/布线设计。

- Python：从本次待上传目录运行 `python -m unittest discover -s software/PenLive/tests -p 'test_*.py'`，80项通过。
- C++：本次编译运行启动灯、GSR门控、坐标累积、电池窗口、JY901S解析、ADS1115六组测试，全通过；见 `native_tests_20261106.json`。
- 原生EPRO及ZIP/3MF：逐文件检查压缩包CRC，无损坏；EPRO内包含5页后板原理图与后板PCB，并保留历史前板。
- 主固件、Python程序/测试及原生工程/PCB/网表/Gerber与维护目录逐字节一致，见 `SOURCE_IDENTITY.json`。说明文档仅作入口修正和当前状态整理。
- 所有纳入的Python源码语法检查通过；本次文档本地文件链接检查通过（只验证文件存在，不验证远端网址或Markdown锚点）。
- 上传前扫描未发现常见API密钥、GitHub令牌或私钥格式；不纳入本机虚拟环境、缓存、认证配置或重复解压目录。
- `MANIFEST_SHA256.json`列出全部交付文件的SHA256（排除清单自身、Git内部文件和运行缓存）。

Arduino本次未重编译：源码与此前已编译v0.61一致。历史编译为ESP32板包3.2.1-cn，程序970,946字节、静态RAM49,292字节；日志位于 `software/PenLive/reports/arduino_compile_v061.log`。此前GUI及合成吞吐结果保留为历史证据，本轮未重复实物/GUI/射频测试。

这些检查不能证明电池冷启动故障已经解决，也不能确认火花事件后的板子状态。当前实物状态见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)。
