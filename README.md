# Video Dedup

高效、安全的视频文件去重工具

## 功能特性

- 严格内容比对（基于 SHA-256 哈希）
- 渐进式哈希优化性能
- SQLite 缓存支持增量扫描
- 智能保留规则
- 安全删除（移到回收站）

## 安装

```bash
# 使用 uv 安装
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## 使用

```bash
video-dedup scan ~/Videos ~/Downloads
```

## 开发

```bash
# 运行测试
pytest

# 运行特定测试
pytest tests/test_utils.py -v
```
