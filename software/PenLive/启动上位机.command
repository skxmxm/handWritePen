#!/bin/bash
set -e
pen_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$pen_dir"
trap 'echo "启动未完成。请查看上面的错误与使用说明。"; read -r -p "按回车退出…"' ERR
if [ -x "$pen_dir/.venv/bin/python" ] && "$pen_dir/.venv/bin/python" -c 'import tkinter, bleak' >/dev/null 2>&1; then
  exec "$pen_dir/.venv/bin/python" "$pen_dir/pen_live.py" "$@"
fi
pen_python=""
for candidate in python3.12 python3.11 python3 "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3.12"; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys, tkinter; assert (3,10) <= sys.version_info[:2] < (3,14)' >/dev/null 2>&1; then
    pen_python="$candidate"
    break
  fi
done
if [ -z "$pen_python" ]; then
  echo '需要带 Tk 的 Python 3.10–3.13，推荐 python.org 的 Python 3.12 macOS 安装包。'
  read -r -p '按回车退出…'
  exit 1
fi
"$pen_python" -m venv "$pen_dir/.venv"
"$pen_dir/.venv/bin/python" -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r "$pen_dir/requirements.txt"
exec "$pen_dir/.venv/bin/python" "$pen_dir/pen_live.py" "$@"
