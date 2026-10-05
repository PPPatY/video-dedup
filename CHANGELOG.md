# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-10-06

### 破坏性变更

- **CLI 语法变更**：必须使用子命令（`video` 或 `image`）
  - 旧: `video-dedup ~/Videos`
  - 新: `video-dedup video ~/Videos`
- 旧用法（直接传入已存在的目录）会显示友好错误提示和新语法示例

### 新功能

- **图片去重支持**：支持 15 种图片格式（.jpg, .png, .heic, .raw 等）
- **智能保留策略**：
  - 视频默认保留最早的文件（`oldest`）
  - 图片默认保留最新的文件（`newest`）
  - 可通过 `--keep-strategy` 手动覆盖
- **子命令架构**：`video-dedup video` 和 `video-dedup image`
- **策略参数**：`--keep-strategy oldest|newest|smart`（默认 `smart`）

### 改进

- 代码架构重构为最小抽象层设计
- 引入 `FileType` 枚举和配置系统（`src/file_types.py`）
- Scanner/Selector 模块参数化，易于扩展
- 测试扩充至 68 个，整体覆盖率 74%（`src/cli.py` 的交互流程覆盖较低）

### 文档

- 新增迁移指南（v1.x → v2.0.0）：`docs/migration-v1-to-v2.md`
- 更新 README 包含图片去重示例
- 完善保留策略说明

### 技术细节

- 无新外部依赖（仅 rich + send2trash）
- 缓存数据库位置与格式不变（`~/.video-dedup/hashes.db`）
- hasher / cache / grouper / deleter 的核心逻辑未改动

---

## [1.0.0] - 2026-10-05

### Added
- Initial release
- Progressive hashing (size → partial → full)
- SQLite cache for incremental scanning
- Smart retention rules
- Safe deletion to system trash
- Multi-directory scanning
- Exclude pattern support
- Dry-run mode
- JSON operation logs
- Rich terminal UI with progress bars
- Symlink loop detection
- Hidden file handling
- Cache hit/miss tracking

### Features
- Video file deduplication by content (SHA-256)
- Support for 20+ video formats
- Configurable thread pool (default 8 threads)
- Cache persistence across runs
- Automatic old entry cleanup (30 days)

### Performance
- First scan: ~5-10 minutes for 3000 files
- Incremental scan: <2 minutes (90% cache hit)
- Memory usage: <200MB

### Security
- Never uses os.remove() - only send2trash
- All deletions recoverable from system trash
- Complete audit log for all operations
