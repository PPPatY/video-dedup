# video-dedup

**[L1 PROJECT]**  
**Purpose**: 高效、安全的媒体文件去重工具  
**Type**: Python CLI Application  
**Version**: 2.0.0  
**Status**: Production Ready

## Overview

video-dedup 是一个基于内容哈希的媒体文件去重工具，支持视频和图片。通过渐进式哈希策略和智能缓存机制，能够快速找出重复文件并安全删除（移到系统回收站）。

**核心特性**：
- 精确内容比对（SHA-256）
- 智能保留策略（视频保留最早，图片保留最新）
- 增量扫描（SQLite缓存）
- 子命令架构（video/image）
- 安全删除（可恢复）

## Quick Start

```bash
# 安装
pip install -e ".[dev]"

# 视频去重（预览）
video-dedup video ~/Videos --dry-run

# 图片去重（实际删除）
video-dedup image ~/Photos

# 手动指定策略
video-dedup video ~/Videos --keep-strategy newest
```

## Architecture

### 分层设计
```
CLI Layer (cli.py)
    ↓
Configuration Layer (file_types.py)
    ↓
Workflow Orchestration
    ├─ Scanner (scanner.py) - 文件发现
    ├─ Hasher (hasher.py) - 内容指纹
    ├─ Cache (cache.py) - 增量优化
    ├─ Grouper (grouper.py) - 重复检测
    ├─ Selector (selector.py) - 保留决策
    └─ Deleter (deleter.py) - 安全删除
```

### 核心算法

**三阶段渐进式哈希**：
1. **Size grouping** - 按文件大小分组（O(n)，快速）
2. **Quick hash** - 首尾1MB哈希（O(candidates)，中速）
3. **Full hash** - 完整SHA-256（O(duplicates)，慢速但精确）

**保留策略**：
- Primary rule: mtime排序（oldest/newest可配置）
- Tie-breaker 1: 24小时内按路径长度
- Tie-breaker 2: 相同长度按字典序

### 文件类型系统

通过`FileType`枚举和`FileTypeConfig`数据类实现最小抽象：
- **VIDEO**: 20种格式，默认策略oldest
- **IMAGE**: 15种格式，默认策略newest
- 扩展新类型只需修改`file_types.py`

## Project Structure

```
video-dedup/
├── src/                    # 核心模块 [L2: src/CLAUDE.md]
│   ├── cli.py             # CLI入口和流程编排
│   ├── file_types.py      # 文件类型配置
│   ├── scanner.py         # 文件系统扫描
│   ├── hasher.py          # 哈希计算
│   ├── cache.py           # SQLite缓存
│   ├── grouper.py         # 重复分组
│   ├── selector.py        # 保留策略
│   ├── deleter.py         # 安全删除
│   └── utils.py           # 工具函数
├── tests/                 # 测试套件（68个测试）
├── docs/                  # 文档目录
│   ├── migration-v1-to-v2.md
│   └── superpowers/       # 设计文档和实现计划
├── README.md              # 用户文档
├── CHANGELOG.md           # 版本变更记录
└── pyproject.toml         # 项目配置

运行时目录：
~/.video-dedup/
├── hashes.db              # 哈希缓存数据库
└── logs/                  # 删除操作日志（JSON）
```

## Documentation Map

### 用户文档
- **README.md** - 快速入门和使用指南
- **docs/migration-v1-to-v2.md** - v1.x升级指南
- **CHANGELOG.md** - 版本历史

### 开发文档
- **CLAUDE.md** (本文件) - 项目概览 [L1]
- **src/CLAUDE.md** - 模块架构和API [L2]
- 每个源文件的docstring - 文件职责 [L3]

### 设计文档
- **docs/superpowers/specs/** - 需求规格
- **docs/superpowers/plans/** - 实现计划

## Development

### 环境设置
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 运行测试
```bash
# 全部测试
pytest

# 带覆盖率
pytest --cov=src --cov-report=term-missing

# 特定模块
pytest tests/test_scanner.py -v
```

### 测试覆盖
- **Total**: 74% (68 tests)
- **Core modules**: 100% (cache, hasher, file_types)
- **Business logic**: 88-94% (scanner, grouper, selector)
- **UI layer**: 42% (cli.py - 交互流程)

### 代码风格
- Python 3.10+ (union types, match/case)
- Type hints everywhere
- Docstrings in Chinese
- No external dependencies beyond stdlib + rich + send2trash

## Release Process

### 版本号规则
- **Major**: 破坏性API变更（v1.x → v2.0.0）
- **Minor**: 新功能，向后兼容
- **Patch**: Bug修复

### 发布检查清单
1. 所有测试通过（`pytest`）
2. 更新CHANGELOG.md
3. 更新pyproject.toml版本号
4. 更新README.md（如有新功能）
5. 创建git标签（`git tag -a vX.Y.Z`）
6. 推送标签（`git push origin --tags`）

## Protocol

### 添加新文件类型
1. 编辑`src/file_types.py`：
   - 添加`FileType`枚举值
   - 添加扩展名常量（例如`AUDIO_EXTENSIONS`）
   - 更新`FILE_TYPE_CONFIGS`字典
2. 编辑`src/cli.py`：
   - 添加新子命令（例如`audio`）
3. 添加测试：
   - `tests/test_file_types.py` - 配置测试
   - `tests/test_cli_subcommands.py` - CLI测试
4. 更新文档：
   - README.md - 使用示例
   - CHANGELOG.md - 记录新功能

### 修改保留策略
1. 编辑`src/selector.py`：
   - 修改`select_files_to_keep()`逻辑
   - 更新docstring说明
2. 添加/更新测试：
   - `tests/test_selector_strategies.py`
3. 更新文档：
   - README.md - 策略说明
   - src/CLAUDE.md - 算法描述

### 修改CLI接口
1. 编辑`src/cli.py`
2. 更新测试：`tests/test_cli*.py`
3. 更新文档：
   - README.md - 使用示例
   - CHANGELOG.md - 破坏性变更警告（如适用）
   - docs/migration-*.md - 迁移指南（如适用）

## Performance Characteristics

### 典型场景
- **首次扫描** (1TB, 5000 videos): ~5-10分钟
- **增量扫描** (90% cache hit): <2分钟
- **内存占用**: <200MB

### 瓶颈与优化
- **IO-bound**: 哈希计算受磁盘速度限制
- **优化手段**:
  - 渐进式哈希（避免不必要的全文读取）
  - SQLite缓存（避免重复计算）
  - 并行哈希（`--threads`参数）

## Known Limitations

1. **仅精确匹配** - 不支持感知哈希（相似但不完全相同的文件）
2. **单机工具** - 不支持分布式扫描
3. **macOS优先** - Windows/Linux支持待完善（send2trash跨平台）
4. **无EXIF处理** - 仅基于文件内容，不解析元数据

## Security Considerations

### 安全删除
- 使用`send2trash`库移到系统回收站
- 永不使用`os.remove()`直接删除
- 提供dry-run模式预览

### 数据完整性
- 使用SHA-256（256位强哈希）
- 冲突概率：~2^-256（实际不可能）

### 权限最小化
- 仅需读取权限扫描文件
- 仅需写入权限到缓存目录（`~/.video-dedup/`）
- 删除文件需用户确认（非dry-run模式）

## Troubleshooting

### 常见问题

**Q: 缓存损坏导致扫描异常**  
A: `video-dedup video ~/Videos --clear-cache`

**Q: 符号链接导致循环**  
A: 默认不跟随符号链接。使用`--follow-symlinks`时确保无循环

**Q: 权限错误**  
A: 确保对扫描目录有读权限，对`~/.video-dedup/`有写权限

**Q: 意外删除文件**  
A: 从系统回收站恢复，或查看`~/.video-dedup/logs/`中的删除记录

## Contributing

欢迎贡献！提交前请：
1. 运行测试套件（`pytest`）
2. 保持测试覆盖率不下降
3. 遵循现有代码风格
4. 更新相关文档

## License

MIT License - 详见LICENSE文件

## Maintainers

- Primary: PatY
- AI Pair Programmer: Claude Opus 5.5

## Changelog

详见 [CHANGELOG.md](./CHANGELOG.md)

最新版本：v2.0.0 (2026-10-06)
- 新增图片去重支持
- 子命令架构（video/image）
- 智能保留策略
- 破坏性变更：CLI语法更新
