# Video Dedup

高效、安全的视频文件去重工具

## 功能特性

- ✅ 严格内容比对（基于 SHA-256 哈希）
- ✅ 渐进式哈希优化（大小 → 头部 → 全文）
- ✅ SQLite 缓存支持增量扫描
- ✅ 智能保留规则（保留最早/最短路径文件）
- ✅ 安全删除（移到系统回收站，可恢复）
- ✅ 多目录扫描 + 排除规则
- ✅ Dry-run 预览模式
- ✅ 完整操作日志

## 安装

### 使用虚拟环境（推荐）

```bash
# 克隆项目
git clone <repo-url>
cd video-dedup

# 创建虚拟环境并安装
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"
```

### 系统要求

- Python 3.10+
- macOS（当前版本）

## 使用方法

### 基本用法

```bash
# 扫描单个目录
python -m src.cli ~/Videos

# 扫描多个目录
python -m src.cli ~/Videos ~/Downloads ~/Desktop
```

### 高级选项

```bash
# 排除特定目录
python -m src.cli ~/Videos --exclude "iMovie 项目" "Final Cut"

# 预览模式（不删除）
python -m src.cli ~/Videos --dry-run

# 清空缓存重新扫描
python -m src.cli ~/Videos --clear-cache

# 自定义缓存目录
python -m src.cli ~/Videos --cache-dir ~/my-cache

# 跟随符号链接
python -m src.cli ~/Videos --follow-symlinks

# 包含隐藏文件
python -m src.cli ~/Videos --include-hidden
```

### 典型工作流

```bash
# 1. 首次扫描（预览）
python -m src.cli ~/Videos ~/Downloads --dry-run

# 2. 确认无误后执行删除
python -m src.cli ~/Videos ~/Downloads

# 3. 后续增量扫描（快速）
python -m src.cli ~/Videos ~/Downloads
```

## 工作原理

### 三阶段渐进式哈希

1. **阶段 1**: 按文件大小分组（元数据比对）
2. **阶段 2**: 计算前 64KB 哈希（快速排除）
3. **阶段 3**: 计算完整文件哈希（确认重复）

### 智能保留规则

1. 保留修改时间最早的文件（原始文件）
2. 如果时间相近（< 24 小时），保留路径最短的
3. 如果路径长度相同，保留字典序最小的

### 缓存机制

- 首次扫描：计算所有文件哈希，存入 SQLite 缓存
- 增量扫描：只计算新增/修改的文件，速度提升 90%+
- 缓存键：`(路径, 大小, 修改时间)` 三元组

## 性能

**测试场景**: 3000 个视频文件，总大小 900GB

- 首次扫描: 5-10 分钟
- 增量扫描: < 2 分钟（90% 缓存命中）
- 内存占用: < 200MB

## 安全机制

- ✅ 文件移到系统回收站（可手动恢复）
- ✅ Dry-run 模式预览
- ✅ 完整操作日志（`~/.video-dedup/logs/`）
- ✅ 永不使用 `os.remove()`

## 开发

### 运行测试

```bash
# 所有测试
pytest

# 特定模块
pytest tests/test_scanner.py -v

# 覆盖率报告
pytest --cov=src --cov-report=html
```

## 故障排除

### 缓存损坏

```bash
python -m src.cli ~/Videos --clear-cache
```

### 权限错误

确保对扫描目录有读取权限，对缓存目录有写入权限。

### 符号链接循环

默认不跟随符号链接。使用 `--follow-symlinks` 时注意避免循环。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

