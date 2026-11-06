#!/bin/bash
pen_dir="$(cd "$(dirname "$0")" && pwd)"
exec "$pen_dir/启动上位机.command" --demo
