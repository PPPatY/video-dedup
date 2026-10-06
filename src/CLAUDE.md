# src/ - 核心模块

**[L2 MODULE]**  
**Purpose**: 媒体文件去重工具的核心业务逻辑模块  
**Type**: Python Package  
**Version**: 2.0.0

## Entry Points

### 主入口
- `cli.py:main()` - 命令行应用入口，处理video/image子命令

### 公共API
- `file_types.get_config(file_type: FileType) -> FileTypeConfig` - 获取文件类型配置（扩展名、默认策略、显示名称）
- `scanner.scan_files(root_dirs, extensions, ...) -> Iterator[Path]` - 扫描指定类型的文件
- `hasher.compute_full_hash(file_path: Path) -> str` - 计算文件完整SHA-256哈希
- `grouper.find_duplicates(files, cache) -> list[list[Path]]` - 分组重复文件（三阶段渐进式哈希）
- `selector.select_files_to_keep(groups, strategy) -> dict[Path, list[Path]]` - 应用保留策略选择要删除的文件
- `deleter.delete_files(files, dry_run) -> dict` - 安全删除文件到系统回收站
- `cache.Cache` - SQLite哈希缓存，加速增量扫描

## File Index

### 流程编排层
- **cli.py** `[INPUT: sys.argv] [OUTPUT: exit code] [POS: 用户界面层]`
  - 命令行参数解析（argparse子命令）
  - 主工作流编排（扫描→分组→选择→确认→删除）
  - 进度显示和用户交互（rich库）
  - 旧CLI用法检测和迁移提示

### 配置层
- **file_types.py** `[INPUT: none] [OUTPUT: FileType, FileTypeConfig, get_config] [POS: 配置定义]`
  - `FileType` 枚举（VIDEO, IMAGE）
  - `FileTypeConfig` 数据类（扩展名集合、默认策略、显示名称）
  - `VIDEO_EXTENSIONS` - 20种视频格式（.mp4/.mov/.avi等）
  - `IMAGE_EXTENSIONS` - 15种图片格式（.jpg/.png/.heic/.raw等）
  - `get_config()` - 根据文件类型返回配置

### 文件系统层
- **scanner.py** `[INPUT: directories, extensions] [OUTPUT: Iterator[Path]] [POS: 文件发现层]`
  - 递归目录扫描，按扩展名过滤
  - 符号链接处理（可选跟随，inode去重防止循环）
  - 隐藏文件/目录处理（可选包含）
  - 排除模式支持

### 哈希计算层
- **hasher.py** `[INPUT: file path] [OUTPUT: hash string] [POS: 内容指纹层]`
  - `compute_full_hash()` - 完整文件SHA-256哈希
  - `compute_quick_hash()` - 首尾各1MB快速哈希
  - 大文件分块读取（避免内存溢出）

### 缓存层
- **cache.py** `[INPUT: file metadata] [OUTPUT: cached hash or None] [POS: 性能优化层]`
  - SQLite数据库（~/.video-dedup/hashes.db）
  - 基于(path, size, mtime)的缓存键
  - 自动过期清理（last_seen < 30天）
  - 缓存命中率统计

### 重复检测层
- **grouper.py** `[INPUT: file list, cache] [OUTPUT: duplicate groups] [POS: 去重逻辑核心]`
  - 三阶段渐进式哈希：
    1. 按文件大小分组（快速）
    2. 按部分哈希分组（中等速度）
    3. 按完整哈希分组（慢速但精确）
  - 并行哈希计算支持（multiprocessing）
  - 缓存集成（跳过未变更文件）

### 决策层
- **selector.py** `[INPUT: duplicate groups, strategy] [OUTPUT: keep/delete mapping] [POS: 保留策略层]`
  - 保留策略：
    - `oldest` - 保留最早修改的文件（视频默认）
    - `newest` - 保留最新修改的文件（图片默认）
  - 时间相近规则（24小时内按路径长度决定）
  - 路径长度tie-breaker（更短的路径优先保留）
  - 字典序tie-breaker（相同长度时字典序靠前的保留）

### 删除执行层
- **deleter.py** `[INPUT: file list, dry_run flag] [OUTPUT: deletion result] [POS: 文件操作层]`
  - 系统回收站删除（send2trash，可恢复）
  - Dry-run模式（预览不删除）
  - 操作日志生成（JSON格式，含时间戳和文件列表）
  - 错误处理和统计

### 工具层
- **utils.py** `[INPUT: numeric values] [OUTPUT: formatted strings] [POS: 格式化工具]`
  - `format_size()` - 字节数人类可读化（1.2 GB）
  - `format_duration()` - 秒数时长格式化（5 分 32 秒）

## Architecture

### 数据流
```
CLI解析 → get_config(FileType)
  ↓
scan_files(extensions) → [Path, ...]
  ↓
find_duplicates(files, cache) → [[Path, Path], [Path, Path, Path], ...]
  ↓
select_files_to_keep(groups, strategy) → {keep: [delete, delete]}
  ↓
delete_files(to_delete, dry_run) → {success: [...], failed: [...]}
  ↓
create_deletion_log(result) → log_path
```

### 依赖关系
- **cli.py** 依赖所有其他模块（编排层）
- **grouper.py** 依赖 hasher + cache（组合）
- **其他模块** 相互独立（松耦合）

### 扩展点
- 添加新文件类型：扩展`file_types.py`中的`FileType`枚举和扩展名集合
- 添加新保留策略：扩展`selector.py`中的strategy参数处理
- 添加新哈希算法：扩展`hasher.py`（保持接口一致）

## Testing

### 测试覆盖
- **Total**: 74% (68 tests)
- **Core modules**: 100% (cache, hasher, file_types)
- **Business logic**: 88-94% (scanner, grouper, selector)
- **UI layer**: 42% (cli.py - 交互流程难以自动化测试)

### 测试组织
```
tests/
├── test_cache.py          # 缓存读写、过期清理
├── test_cli.py            # CLI参数解析
├── test_cli_subcommands.py # 子命令功能
├── test_deleter.py        # 删除操作
├── test_file_types.py     # 文件类型配置
├── test_grouper.py        # 重复分组逻辑
├── test_hasher.py         # 哈希计算
├── test_scanner.py        # 文件扫描
├── test_selector_strategies.py # 保留策略
└── test_utils.py          # 工具函数
```

## Protocol

### 文件修改规则
1. **添加新文件类型**：
   - 更新`file_types.py`：添加扩展名常量和配置
   - 更新`tests/test_file_types.py`：添加对应测试
   - 更新`README.md`：文档化支持的格式
   - 无需修改其他模块（参数化设计）

2. **修改保留策略**：
   - 更新`selector.py`：修改策略逻辑
   - 更新`tests/test_selector_strategies.py`：验证新行为
   - 更新`README.md`：文档化策略变更

3. **修改CLI**：
   - 更新`cli.py`：修改参数或流程
   - 更新`tests/test_cli*.py`：覆盖新功能
   - 更新`README.md`：更新使用示例
   - 更新`CHANGELOG.md`：记录API变更

### 模块间协议
- 所有路径使用`pathlib.Path`（绝对路径）
- 哈希值统一为小写十六进制字符串（SHA-256）
- 时间戳使用Unix时间戳（float，从`os.path.getmtime`）
- 文件大小单位为字节（int）
- 扩展名统一小写且带点前缀（`.mp4`而非`mp4`或`.MP4`）

### 错误处理
- 文件访问错误（OSError）在scanner/hasher层捕获并跳过
- 用户中断（KeyboardInterrupt）在CLI层捕获并优雅退出
- 缓存错误不中断主流程（降级为无缓存模式）
- 删除失败记录到result['failed']，不中断批量操作

## See Also
- `/README.md` - 用户文档和使用示例
- `/docs/superpowers/specs/2026-10-06-image-dedup-design.md` - 设计规格
- `/docs/migration-v1-to-v2.md` - v1.x迁移指南
- `/CHANGELOG.md` - 版本变更记录
