# Video Dedup

高效、安全的媒体文件去重工具（支持视频和图片）

## 功能特性

- ✅ 严格内容比对（基于 SHA-256 哈希）
- ✅ 渐进式哈希优化（大小 → 头部 → 全文）
- ✅ SQLite 缓存支持增量扫描
- ✅ 视频与图片去重（`video` / `image` 子命令）
- ✅ 智能保留策略（视频默认保留最早，图片默认保留最新，可手动覆盖）
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
# 视频去重
video-dedup video ~/Videos

# 图片去重
video-dedup image ~/Photos

# 扫描多个目录
video-dedup video ~/Videos ~/Downloads
video-dedup image ~/Photos ~/Desktop
```

未安装为命令时，可用 `python -m src.cli video ~/Videos` 代替。

### 高级选项

```bash
# 排除特定目录
video-dedup video ~/Videos --exclude "iMovie 项目" "Final Cut"
video-dedup image ~/Photos --exclude "Thumbnails"

# 预览模式（不删除）
video-dedup video ~/Videos --dry-run
video-dedup image ~/Photos --dry-run

# 手动指定保留策略
video-dedup video ~/Videos --keep-strategy newest  # 保留最新（非默认）
video-dedup image ~/Photos --keep-strategy oldest  # 保留最早（非默认）

# 清空缓存重新扫描
video-dedup video ~/Videos --clear-cache

# 自定义缓存目录
video-dedup video ~/Videos --cache-dir ~/my-cache

# 跟随符号链接
video-dedup video ~/Videos --follow-symlinks

# 包含隐藏文件
video-dedup video ~/Videos --include-hidden

# 使用 4 个线程并行计算哈希
video-dedup video ~/Videos --threads 4
```

### 保留策略

**智能策略（默认，`--keep-strategy smart`）**：
- 视频文件：保留**最早**修改的文件（原始录制最重要）
- 图片文件：保留**最新**修改的文件（编辑后版本通常更好）

**手动覆盖**：
```bash
video-dedup image ~/Photos --keep-strategy oldest  # 图片也保留最早
```

### 典型工作流

```bash
# 1. 首次扫描（预览）
video-dedup video ~/Videos --dry-run
video-dedup image ~/Photos --dry-run

# 2. 确认无误后执行删除
video-dedup video ~/Videos
video-dedup image ~/Photos

# 3. 后续增量扫描（快速）
video-dedup video ~/Videos  # 缓存加速
```

## 支持的文件格式

**视频**（20 种）：.mp4, .mov, .avi, .mkv, .flv, .wmv, .m4v, .mpg, .mpeg, .3gp, .webm, .ogv, .ts, .mts, .vob, .rm, .rmvb, .asf, .m2ts, .divx

**图片**（15 种）：.jpg, .jpeg, .png, .gif, .bmp, .webp, .raw, .cr2, .nef, .arw, .tiff, .tif, .heic, .heif, .svg

## 从 v1.x 升级

⚠️ **v2.0.0 包含破坏性变更**

**旧版本 (v1.x)**:
```bash
video-dedup ~/Videos
```

**新版本 (v2.0)**:
```bash
video-dedup video ~/Videos
```

详见 [迁移指南](docs/migration-v1-to-v2.md)

## 工作原理

### 三阶段渐进式哈希

1. **阶段 1**: 按文件大小分组（元数据比对）
2. **阶段 2**: 计算前 64KB 哈希（快速排除）
3. **阶段 3**: 计算完整文件哈希（确认重复）

### 智能保留规则

1. 按 `--keep-strategy` 选择：`oldest` 保留修改时间最早的文件，`newest` 保留最新的文件；`smart`（默认）对视频用 `oldest`，对图片用 `newest`
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
video-dedup video ~/Videos --clear-cache
```

### 权限错误

确保对扫描目录有读取权限，对缓存目录有写入权限。

### 符号链接循环

默认不跟随符号链接。使用 `--follow-symlinks` 时注意避免循环。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
