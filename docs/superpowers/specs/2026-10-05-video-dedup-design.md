# Video Dedup - 视频文件去重工具设计文档

**创建日期**: 2026-10-05  
**目标平台**: macOS  
**状态**: 设计阶段

---

## 1. 项目概述

### 1.1 目标

构建一个高效、安全的视频文件去重工具，用于：
- 清理历史积累的重复视频（一次性大扫除）
- 日常维护，防止新下载重复（定期运行）
- 释放存储空间

### 1.2 核心特性

- ✅ 严格内容比对（逐字节相同，基于哈希）
- ✅ 多目录扫描 + 排除规则
- ✅ 渐进式哈希（性能优化）
- ✅ SQLite 缓存（增量扫描，第二次运行快 10 倍以上）
- ✅ 智能保留规则（自动推荐保留哪个文件）
- ✅ 安全删除（移到系统回收站，可恢复）
- ✅ 命令行界面 + 美观进度显示
- ✅ Dry-run 模式 + 操作日志

### 1.3 使用场景

**规模：**
- 文件数量：500 - 5000 个视频
- 文件大小：混合（几 MB 到几 GB）
- 预计性能：首次扫描 5-15 分钟，增量扫描 < 2 分钟

**典型工作流：**
```bash
# 扫描多个目录，排除特定文件夹
video-dedup scan ~/Videos ~/Downloads --exclude "iMovie 项目" "Final Cut"

# 输出：
# ✓ 扫描完成
# 发现 43 组重复文件，共 127 个文件，可释放 87.3 GB
# 确认删除 84 个重复文件？[y/N]
```

---

## 2. 技术架构

### 2.1 技术栈

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| **语言** | Python 3.10+ | 标准库强大，开发速度快，易维护 |
| **包管理** | uv | 比 pip 快 10-100 倍，单文件安装 |
| **终端 UI** | rich | 专业级进度条、表格、颜色输出 |
| **删除机制** | send2trash | 安全移到回收站（系统 API） |
| **缓存** | SQLite | 轻量、内置、无需额外服务 |
| **并发** | ThreadPoolExecutor | IO 密集型任务适合线程池 |
| **哈希算法** | SHA-256 | 平衡速度和碰撞概率 |
| **测试** | pytest | Python 标准测试框架 |

### 2.2 模块结构

```
video-dedup/
├── src/
│   ├── scanner.py      # 文件扫描（递归遍历、扩展名过滤、排除规则）
│   ├── hasher.py       # 哈希计算（渐进式、并发、进度显示）
│   ├── cache.py        # SQLite 缓存（路径→哈希映射、增量检测）
│   ├── grouper.py      # 重复分组（按哈希聚合、统计大小）
│   ├── selector.py     # 智能保留规则（选择每组保留哪个文件）
│   ├── deleter.py      # 安全删除（移到回收站、操作日志）
│   ├── cli.py          # 命令行入口（参数解析、流程编排）
│   └── utils.py        # 工具函数（格式化、日志、常量）
├── tests/              # 单元测试 + 集成测试
│   ├── test_scanner.py
│   ├── test_hasher.py
│   ├── test_cache.py
│   ├── test_grouper.py
│   ├── test_selector.py
│   └── fixtures/       # 测试数据（模拟视频文件树）
├── docs/               # 文档
│   └── superpowers/specs/
│       └── 2026-10-05-video-dedup-design.md
├── pyproject.toml      # 项目配置（依赖、元数据）
├── README.md           # 使用说明
└── .gitignore
```

### 2.3 数据流

```
命令行参数
    ↓
scanner.py: 扫描文件系统 → 文件路径列表
    ↓
cache.py: 检查缓存 → 分离已缓存/需计算的文件
    ↓
hasher.py: 并发计算哈希 → (路径, 哈希) 映射
    ↓
cache.py: 更新缓存
    ↓
grouper.py: 按哈希分组 → 重复组列表
    ↓
selector.py: 应用保留规则 → (保留文件, 删除列表)
    ↓
显示汇总 → 用户确认
    ↓
deleter.py: 移到回收站 + 记录日志
```

---

## 3. 核心算法设计

### 3.1 渐进式哈希策略

**目标：** 避免对所有文件进行全文哈希（耗时），通过多阶段快速排除不重复文件。

**三阶段比对：**

```python
# 阶段 1: 按文件大小分组
size_groups = defaultdict(list)
for file_path in all_files:
    size = os.path.getsize(file_path)
    size_groups[size].append(file_path)

# 只处理大小相同的文件组（size >= 2 个文件）
candidates = [files for files in size_groups.values() if len(files) > 1]

# 阶段 2: 哈希前 64KB（快速排除）
partial_hash_groups = defaultdict(list)
for file_path in candidates:
    partial_hash = hash_first_n_bytes(file_path, 64 * 1024)
    partial_hash_groups[partial_hash].append(file_path)

# 只对头部哈希相同的文件组进行全文哈希
candidates = [files for files in partial_hash_groups.values() if len(files) > 1]

# 阶段 3: 全文哈希（确认重复）
full_hash_groups = defaultdict(list)
for file_path in candidates:
    full_hash = hash_full_file(file_path)
    full_hash_groups[full_hash].append(file_path)

# 哈希相同 = 重复文件
duplicates = [files for files in full_hash_groups.values() if len(files) > 1]
```

**性能分析：**
- 假设 3000 个文件，50 组真重复（150 个文件）
- 阶段 1：瞬间完成（只读元数据）
- 阶段 2：150 个文件 × 64KB = 9.6MB（< 1 秒）
- 阶段 3：50 组 × 平均 500MB = 25GB（5-10 分钟，取决于磁盘速度）

**对比：** 如果直接全文哈希所有文件 = 3000 × 平均 300MB = 900GB 读取（不可接受）

### 3.2 缓存机制（增量扫描）

**SQLite 表结构：**

```sql
CREATE TABLE file_hashes (
    path TEXT PRIMARY KEY,          -- 文件绝对路径
    size INTEGER NOT NULL,          -- 文件大小（字节）
    mtime REAL NOT NULL,            -- 修改时间戳（Unix time）
    full_hash TEXT NOT NULL,        -- SHA-256 完整哈希（64 字符）
    partial_hash TEXT,              -- 前 64KB 哈希（可选优化）
    last_seen REAL NOT NULL,        -- 最后扫描时间戳
    created_at REAL NOT NULL        -- 首次记录时间
);

CREATE INDEX idx_full_hash ON file_hashes(full_hash);
CREATE INDEX idx_last_seen ON file_hashes(last_seen);
```

**缓存命中逻辑：**

```python
def get_hash_from_cache_or_compute(file_path):
    stat = os.stat(file_path)
    size = stat.st_size
    mtime = stat.st_mtime
    
    # 查询缓存
    cached = db.query("SELECT full_hash FROM file_hashes WHERE path=? AND size=? AND mtime=?",
                      (file_path, size, mtime))
    
    if cached:
        # 缓存命中：文件未修改
        db.update_last_seen(file_path)
        return cached['full_hash']
    else:
        # 缓存失效：重新计算
        full_hash = compute_sha256(file_path)
        db.upsert(path=file_path, size=size, mtime=mtime, full_hash=full_hash)
        return full_hash
```

**缓存清理策略：**
- 每次扫描结束后，删除 `last_seen` > 30 天的记录（文件已删除/移动）
- 提供 `--clear-cache` 选项手动清理

**预期效果：**
- 首次扫描：0% 缓存命中，全量计算
- 第二次扫描（假设 10% 文件变化）：90% 缓存命中，时间缩短 90%

### 3.3 智能保留规则

**默认规则（按优先级应用）：**

```python
def select_file_to_keep(duplicate_group):
    """
    从重复文件组中选择要保留的文件
    返回：(保留的文件路径, 要删除的文件路径列表)
    """
    # 按修改时间排序（最早的在前）
    sorted_files = sorted(duplicate_group, key=lambda f: os.path.getmtime(f))
    
    # 规则 1: 保留修改时间最早的文件（原始文件）
    oldest_file = sorted_files[0]
    
    # 规则 2: 如果多个文件时间相近（< 24 小时），保留路径最短的
    oldest_time = os.path.getmtime(oldest_file)
    similar_time_files = [f for f in sorted_files 
                          if abs(os.path.getmtime(f) - oldest_time) < 86400]
    
    if len(similar_time_files) > 1:
        # 路径最短的通常在主目录（更重要）
        oldest_file = min(similar_time_files, key=lambda f: len(f))
    
    # 规则 3: 路径长度相同，选择字典序最小的（稳定排序）
    if len([f for f in similar_time_files if len(f) == len(oldest_file)]) > 1:
        oldest_file = min(similar_time_files, key=lambda f: f)
    
    to_delete = [f for f in duplicate_group if f != oldest_file]
    return oldest_file, to_delete
```

**示例：**

```
重复组 A (3 个文件):
  /Users/pat/Videos/movie.mp4              (2024-01-15, 1.2GB) ← 保留（最早）
  /Users/pat/Downloads/movie.mp4           (2024-03-20, 1.2GB) → 删除
  /Users/pat/Desktop/备份/movie.mp4        (2024-03-21, 1.2GB) → 删除

重复组 B (2 个文件，时间相同):
  /Users/pat/Videos/clip.mov               (2024-05-01, 50MB)  ← 保留（路径短）
  /Users/pat/Downloads/temp/backup/clip.mov (2024-05-01, 50MB)  → 删除
```

### 3.4 视频文件识别

**扩展名列表（默认）：**

```python
VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.webm', '.ogv', '.ts', '.mts',
    '.vob', '.rm', '.rmvb', '.asf', '.m2ts', '.divx'
}

def is_video_file(file_path):
    """按扩展名判断是否为视频文件（不区分大小写）"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in VIDEO_EXTENSIONS
```

**深度扫描模式（可选 `--deep-scan`）：**

```python
import magic  # python-magic 库

def is_video_file_deep(file_path):
    """读取文件头判断 MIME 类型"""
    try:
        mime = magic.from_file(file_path, mime=True)
        return mime.startswith('video/')
    except Exception:
        # 降级到扩展名判断
        return is_video_file(file_path)
```

**权衡：**
- 默认模式：快速，适合 99% 场景
- 深度扫描：准确，但每个文件需要读取文件头（稍慢）

---

## 4. 用户交互设计

### 4.1 命令行接口

```bash
video-dedup scan [目录...] [选项]

位置参数:
  目录                    要扫描的目录路径（支持多个）

选项:
  --exclude PATTERN      排除匹配的目录（支持多个，如 --exclude "iMovie*" "*.photoslibrary"）
  --deep-scan            使用文件头验证类型（不只看扩展名）
  --dry-run              预览模式，不实际删除文件
  --cache-dir PATH       指定缓存目录（默认 ~/.video-dedup）
  --clear-cache          清空缓存后再扫描
  --threads N            并发线程数（默认 8）
  --follow-symlinks      跟随符号链接（默认跳过）
  --include-hidden       包含隐藏文件（默认跳过）
  --log-level LEVEL      日志级别：debug/info/warning/error（默认 info）
  -h, --help             显示帮助信息
  -v, --version          显示版本号
```

**示例：**

```bash
# 基本用法
video-dedup scan ~/Videos

# 扫描多个目录，排除特定文件夹
video-dedup scan ~/Videos ~/Downloads ~/Desktop --exclude "iMovie 项目" "Final Cut"

# 预览模式（不删除）
video-dedup scan ~/Videos --dry-run

# 清空缓存重新扫描
video-dedup scan ~/Videos --clear-cache

# 深度扫描 + 调试日志
video-dedup scan ~/Videos --deep-scan --log-level debug
```

### 4.2 输出界面

**扫描阶段：**

```
🔍 扫描视频文件...

扫描目录:
  • ~/Videos
  • ~/Downloads
排除规则:
  • iMovie 项目
  • Final Cut

[████████████████████░░░░] 89% (2,547/2,847 文件)
  正在处理: ~/Videos/2023/vacation.mp4
  
  已发现 15 组重复...
```

**结果汇总：**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ 扫描完成（用时 8 分 32 秒）

📊 统计:
  • 总文件数: 2,847 个视频
  • 总大小: 1.2 TB
  • 发现重复: 43 组（127 个文件，其中 84 个可删除）
  • 可释放空间: 87.3 GB
  • 缓存命中率: 78%

🗑️  删除策略:
  • 保留最早修改的文件
  • 时间相近时保留路径最短的

确认删除 84 个重复文件？[y/N]
```

**删除阶段：**

```
删除中... [████████████████████] 100% (84/84)

✓ 操作完成
  • 已删除: 84 个文件
  • 已释放: 87.3 GB
  • 文件已移至回收站（可在"废纸篓"中恢复）
  • 操作日志: ~/.video-dedup/logs/2026-10-05_143022.log
```

**Dry-run 模式输出：**

```
⚠️  预览模式（--dry-run）：不会实际删除文件

将要删除的文件 (84 个):
  [1] /Users/pat/Downloads/movie.mp4 (1.2 GB)
      保留: /Users/pat/Videos/movie.mp4
  [2] /Users/pat/Desktop/clip.mov (50 MB)
      保留: /Users/pat/Videos/clip.mov
  ...

删除计划已保存到: deletion-plan.json
要执行删除，请重新运行并去掉 --dry-run 选项
```

### 4.3 操作日志格式

**日志文件位置：** `~/.video-dedup/logs/YYYY-MM-DD_HHmmss.log`

**内容示例：**

```json
{
  "timestamp": "2026-10-05T14:30:22+08:00",
  "version": "1.0.0",
  "command": "video-dedup scan ~/Videos ~/Downloads --exclude 'iMovie 项目'",
  "scan_summary": {
    "total_files": 2847,
    "total_size_bytes": 1288490188800,
    "duplicate_groups": 43,
    "duplicate_files": 127,
    "files_to_delete": 84,
    "space_to_free_bytes": 93758414848,
    "scan_duration_seconds": 512,
    "cache_hit_rate": 0.78
  },
  "duplicate_groups": [
    {
      "hash": "a3f5b8c9d2e1...",
      "file_size": 1258291200,
      "files": [
        {
          "path": "/Users/pat/Videos/movie.mp4",
          "mtime": "2024-01-15T10:23:45+08:00",
          "action": "keep",
          "reason": "oldest_file"
        },
        {
          "path": "/Users/pat/Downloads/movie.mp4",
          "mtime": "2024-03-20T15:12:33+08:00",
          "action": "delete",
          "reason": "duplicate"
        }
      ]
    }
  ],
  "deleted_files": [
    {
      "path": "/Users/pat/Downloads/movie.mp4",
      "size": 1258291200,
      "deleted_at": "2026-10-05T14:35:10+08:00",
      "status": "success"
    }
  ],
  "errors": []
}
```

---

## 5. 错误处理和安全机制

### 5.1 安全保障

**1. 回收站机制**
- 使用 `send2trash` 库调用系统 API
- 文件移到 macOS "废纸篓"，可手动恢复
- **永不使用** `os.remove()` 或 `os.unlink()`

```python
from send2trash import send2trash

def safe_delete(file_path):
    """安全删除文件（移到回收站）"""
    try:
        send2trash(file_path)
        return True, None
    except Exception as e:
        return False, str(e)
```

**2. Dry-run 模式**
- `--dry-run` 完整扫描 + 显示结果，但不删除
- 输出删除计划到 JSON 文件供审查

**3. 操作日志**
- 每次运行记录完整操作日志
- 包含：删除的文件、保留的文件、时间戳、错误信息
- 日志永久保存（不自动清理）

**4. 中断恢复**
- 删除操作支持 Ctrl+C 中断
- 已删除的文件记录在日志中
- 可从回收站恢复

### 5.2 错误处理策略

| 错误类型 | 处理方式 | 用户提示 |
|---------|---------|---------|
| **无权限读取文件** | 记录警告，跳过，继续扫描 | "跳过 N 个无权限访问的文件" |
| **无权限删除文件** | 跳过删除，记录到报告 | "N 个文件因权限问题未删除（详见日志）" |
| **文件被占用** | 跳过删除，标记为"使用中" | "N 个文件正在使用，已跳过" |
| **缓存损坏** | 自动删除缓存，重新扫描 | "缓存损坏已重建，继续扫描..." |
| **磁盘空间不足（缓存）** | 降级为无缓存模式 | "缓存空间不足，本次扫描不使用缓存" |
| **符号链接循环** | 检测并跳过 | "检测到符号链接循环，已跳过" |

### 5.3 边界情况处理

**符号链接（Symlinks）：**
- 默认不跟随（避免误删链接目标）
- `--follow-symlinks` 启用跟随
- 检测循环引用（防止无限递归）

```python
def should_follow_symlink(path, visited_inodes, follow_symlinks_flag):
    if not follow_symlinks_flag:
        return False
    
    stat = os.stat(path)
    inode = (stat.st_dev, stat.st_ino)
    
    if inode in visited_inodes:
        # 检测到循环
        return False
    
    visited_inodes.add(inode)
    return True
```

**硬链接（Hard Links）：**
- 检测硬链接（多个路径指向同一 inode）
- 不将硬链接算作"重复"
- 统计时只计算一次

```python
def is_hard_link(file_paths):
    """检查是否为硬链接（指向同一 inode）"""
    inodes = set()
    for path in file_paths:
        stat = os.stat(path)
        inodes.add((stat.st_dev, stat.st_ino))
    return len(inodes) == 1  # 所有路径指向同一 inode
```

**隐藏文件：**
- 默认跳过（`.` 开头的文件/文件夹）
- `--include-hidden` 启用扫描

**大文件处理：**
- 分块读取（64KB 块），避免内存溢出
- 显示进度（大文件哈希时间长）

```python
def hash_file_with_progress(file_path, block_size=65536):
    hasher = hashlib.sha256()
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'rb') as f:
        with progress_bar(total=file_size) as bar:
            while chunk := f.read(block_size):
                hasher.update(chunk)
                bar.update(len(chunk))
    
    return hasher.hexdigest()
```

---

## 6. 性能优化

### 6.1 并发策略

**线程池配置：**
```python
from concurrent.futures import ThreadPoolExecutor

# 默认 8 线程（可通过 --threads 调整）
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(compute_hash, file) for file in files]
    results = [f.result() for f in futures]
```

**为什么用线程而非进程：**
- 哈希计算是 IO 密集型（读磁盘瓶颈）
- 线程切换开销小，适合大量小任务
- Python GIL 在 IO 操作时释放，不影响并发

### 6.2 内存优化

**流式处理：**
- 不将所有文件路径加载到内存
- 使用生成器（generator）逐批处理

```python
def scan_files(root_dirs, exclude_patterns):
    """生成器：逐个 yield 文件路径"""
    for root_dir in root_dirs:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # 应用排除规则
            dirnames[:] = [d for d in dirnames if not matches_exclude(d, exclude_patterns)]
            
            for filename in filenames:
                if is_video_file(filename):
                    yield os.path.join(dirpath, filename)
```

**缓存分页：**
- SQLite 查询使用分页（LIMIT/OFFSET）
- 避免一次性加载所有缓存记录

### 6.3 性能预估

**测试场景：** 3000 个视频文件，总大小 900GB，50 组重复（150 个文件）

| 阶段 | 操作 | 预估时间 |
|------|------|---------|
| 文件扫描 | 递归遍历目录树 | < 10 秒 |
| 缓存查询 | SQLite 查询（首次 0 条） | < 1 秒 |
| 阶段 1（大小分组） | 读取元数据 | < 5 秒 |
| 阶段 2（头部哈希） | 150 文件 × 64KB | < 10 秒 |
| 阶段 3（全文哈希） | 25GB 读取（磁盘速度 ~100MB/s） | 4-5 分钟 |
| 分组 + 选择 | 内存操作 | < 1 秒 |
| 删除 84 个文件 | 移到回收站 | < 5 秒 |
| **总计（首次）** | | **5-10 分钟** |
| **总计（增量，10% 变化）** | 缓存命中 90% | **< 2 分钟** |

**优化效果：**
- 渐进式哈希：减少 97% 的数据读取（900GB → 25GB）
- 缓存机制：第二次运行快 90%
- 并发计算：8 线程 → 理论加速 5-6 倍（实际受磁盘 IO 限制）

---

## 7. 测试策略

### 7.1 单元测试

**覆盖模块：**

```python
# tests/test_hasher.py
def test_hash_identical_files():
    """测试相同内容的文件生成相同哈希"""
    file1 = create_test_file("test1.mp4", b"content")
    file2 = create_test_file("test2.mp4", b"content")
    assert compute_hash(file1) == compute_hash(file2)

def test_hash_different_files():
    """测试不同内容的文件生成不同哈希"""
    file1 = create_test_file("test1.mp4", b"content1")
    file2 = create_test_file("test2.mp4", b"content2")
    assert compute_hash(file1) != compute_hash(file2)

# tests/test_cache.py
def test_cache_hit():
    """测试缓存命中逻辑"""
    cache = Cache(":memory:")
    file_path = create_test_file("test.mp4", b"content")
    
    # 首次计算
    hash1 = get_hash_with_cache(file_path, cache)
    
    # 第二次应命中缓存（文件未修改）
    hash2 = get_hash_with_cache(file_path, cache)
    
    assert hash1 == hash2
    assert cache.hit_count == 1

def test_cache_miss_on_modification():
    """测试文件修改后缓存失效"""
    cache = Cache(":memory:")
    file_path = create_test_file("test.mp4", b"content1")
    
    hash1 = get_hash_with_cache(file_path, cache)
    
    # 修改文件
    modify_file(file_path, b"content2")
    
    hash2 = get_hash_with_cache(file_path, cache)
    
    assert hash1 != hash2
    assert cache.miss_count == 2

# tests/test_selector.py
def test_select_oldest_file():
    """测试保留最早文件的规则"""
    files = [
        ("/path/file1.mp4", 1705300000),  # 2024-01-15
        ("/path/file2.mp4", 1710900000),  # 2024-03-20
    ]
    keep, delete = select_file_to_keep(files)
    assert keep == "/path/file1.mp4"
    assert delete == ["/path/file2.mp4"]

def test_select_shortest_path_on_similar_time():
    """测试时间相近时保留路径最短的"""
    files = [
        ("/Users/pat/Videos/movie.mp4", 1705300000),
        ("/Users/pat/Desktop/backup/temp/movie.mp4", 1705301000),  # 1000 秒差异 < 24 小时
    ]
    keep, delete = select_file_to_keep(files)
    assert keep == "/Users/pat/Videos/movie.mp4"
```

### 7.2 集成测试

**测试场景：**

```python
# tests/test_integration.py
def test_full_workflow():
    """测试完整扫描 → 删除流程"""
    # 1. 创建测试文件树
    test_dir = create_test_tree({
        "unique1.mp4": b"unique content 1",
        "unique2.mp4": b"unique content 2",
        "dup1_a.mp4": b"duplicate content",
        "subdir/dup1_b.mp4": b"duplicate content",
        "subdir/dup1_c.mp4": b"duplicate content",
    })
    
    # 2. 运行扫描
    result = run_scan([test_dir], dry_run=True)
    
    # 3. 验证结果
    assert result['total_files'] == 5
    assert result['duplicate_groups'] == 1
    assert result['files_to_delete'] == 2
    
    # 4. 执行删除
    run_delete(result['deletion_plan'])
    
    # 5. 验证文件状态
    assert os.path.exists(test_dir / "dup1_a.mp4")  # 保留最早的
    assert not os.path.exists(test_dir / "subdir/dup1_b.mp4")
    assert not os.path.exists(test_dir / "subdir/dup1_c.mp4")

def test_incremental_scan():
    """测试增量扫描（缓存机制）"""
    test_dir = create_test_tree({
        "file1.mp4": b"content1",
        "file2.mp4": b"content2",
    })
    
    # 首次扫描
    result1 = run_scan([test_dir])
    assert result1['cache_hit_rate'] == 0.0
    
    # 第二次扫描（无文件变化）
    result2 = run_scan([test_dir])
    assert result2['cache_hit_rate'] == 1.0
    
    # 添加新文件后扫描
    create_file(test_dir / "file3.mp4", b"content3")
    result3 = run_scan([test_dir])
    assert result3['cache_hit_rate'] == 0.67  # 2/3
```

### 7.3 性能测试

```python
# tests/test_performance.py
def test_large_scale_scan():
    """测试大规模扫描性能"""
    # 生成 3000 个测试文件（混合大小）
    test_dir = generate_test_files(
        count=3000,
        size_range=(1_000_000, 100_000_000),  # 1MB - 100MB
        duplicate_groups=50  # 50 组重复
    )
    
    start = time.time()
    result = run_scan([test_dir])
    duration = time.time() - start
    
    # 性能断言
    assert duration < 600  # < 10 分钟
    assert result['total_files'] == 3000
    assert result['duplicate_groups'] == 50
    
    # 内存使用检查
    import psutil
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    assert memory_mb < 500  # < 500MB
```

### 7.4 测试数据生成

```python
# tests/fixtures.py
def create_test_tree(file_specs):
    """
    创建测试文件树
    
    file_specs: {相对路径: 内容}
    """
    test_dir = tempfile.mkdtemp()
    for rel_path, content in file_specs.items():
        full_path = os.path.join(test_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(content)
    return test_dir

def generate_random_video_content(size_bytes):
    """生成指定大小的随机内容（模拟视频）"""
    return os.urandom(size_bytes)
```

---

## 8. 依赖管理

### 8.1 pyproject.toml

```toml
[project]
name = "video-dedup"
version = "1.0.0"
description = "高效、安全的视频文件去重工具"
authors = [{name = "Your Name", email = "your.email@example.com"}]
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}

dependencies = [
    "rich>=13.0.0",           # 终端 UI
    "send2trash>=1.8.0",      # 回收站删除
    "click>=8.0.0",           # 命令行解析（可选，或用 argparse）
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",          # 代码格式化
    "ruff>=0.1.0",            # 代码检查
]
deep-scan = [
    "python-magic>=0.4.27",   # 文件类型检测（仅 --deep-scan 需要）
]

[project.scripts]
video-dedup = "src.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]

[tool.black]
line-length = 100
target-version = ["py310"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]  # 行长度由 black 处理
```

### 8.2 安装步骤

```bash
# 1. 安装 uv（包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆项目
git clone <repo-url>
cd video-dedup

# 3. 创建虚拟环境 + 安装依赖
uv venv
source .venv/bin/activate  # macOS/Linux
uv pip install -e ".[dev]"

# 4. 运行测试
pytest

# 5. 运行工具
video-dedup scan ~/Videos
```

---

## 9. 部署和分发

### 9.1 打包为可执行文件

使用 **PyInstaller** 打包为单文件可执行程序：

```bash
# 安装 PyInstaller
uv pip install pyinstaller

# 打包
pyinstaller --onefile --name video-dedup src/cli.py

# 生成的文件: dist/video-dedup（单个二进制文件）
```

**分发：**
```bash
# 复制到系统路径
sudo cp dist/video-dedup /usr/local/bin/

# 现在可以全局使用
video-dedup scan ~/Videos
```

### 9.2 Homebrew 安装（未来）

```ruby
# video-dedup.rb（Homebrew formula）
class VideoDedup < Formula
  desc "高效、安全的视频文件去重工具"
  homepage "https://github.com/your-username/video-dedup"
  url "https://github.com/your-username/video-dedup/archive/v1.0.0.tar.gz"
  sha256 "..."

  depends_on "python@3.10"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/video-dedup", "--version"
  end
end
```

**安装：**
```bash
brew install video-dedup
```

---

## 10. 未来扩展

### 10.1 短期功能（v1.x）

- [ ] **导出报告**：生成 HTML/PDF 报告（重复文件详情、统计图表）
- [ ] **交互式确认**：每组重复单独确认删除
- [ ] **规则自定义**：允许用户自定义保留规则（如"保留最新的"）
- [ ] **定时任务集成**：生成 launchd plist（macOS 定时任务）

### 10.2 长期功能（v2.x）

- [ ] **视觉相似检测**：使用感知哈希（perceptual hashing）检测不同分辨率/码率的相同视频
- [ ] **GUI 版本**：macOS 原生应用（SwiftUI）
- [ ] **云存储支持**：扫描 iCloud Drive、Google Drive
- [ ] **视频预览**：在确认前预览视频缩略图

### 10.3 跨平台支持（v2.x）

- [ ] Windows 支持（回收站 API 差异）
- [ ] Linux 支持（Trash 规范）

---

## 11. 风险和限制

### 11.1 已知限制

| 限制 | 影响 | 缓解方案 |
|------|------|---------|
| **哈希碰撞** | SHA-256 理论上可能碰撞（概率极低） | 可接受风险（2^256 分之一） |
| **不检测相似视频** | 不同编码/分辨率的同一视频不算重复 | v2.0 加入感知哈希 |
| **大文件慢** | 100GB+ 文件哈希时间长 | 渐进式哈希已优化，无法完全避免 |
| **网络存储慢** | NFS/SMB 挂载的目录读取慢 | 建议先同步到本地扫描 |
| **符号链接复杂** | 复杂的链接结构可能误判 | 默认不跟随，需手动检查 |

### 11.2 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| **误删重要文件** | 低 | 高 | • 回收站机制（可恢复）<br>• Dry-run 预览<br>• 操作日志 |
| **缓存损坏导致误判** | 低 | 中 | • 自动检测损坏并重建<br>• 基于 (路径, 大小, mtime) 三元组校验 |
| **大规模删除后性能下降** | 中 | 低 | • 垃圾回收机制清理缓存<br>• VACUUM SQLite |
| **并发哈希占用资源** | 中 | 低 | • 限制线程数（默认 8）<br>• 可通过 --threads 调整 |

---

## 12. 总结

### 12.1 核心价值

- **高效**：渐进式哈希 + 缓存机制，第二次运行快 10 倍
- **安全**：回收站删除 + Dry-run + 日志，零风险
- **智能**：自动推荐保留规则，减少手动决策
- **易用**：命令行 + 美观输出，学习成本低

### 12.2 技术亮点

- 渐进式哈希：大小 → 头部 → 全文，减少 97% 数据读取
- SQLite 缓存：增量扫描，支持日常维护场景
- 并发处理：8 线程并行计算，充分利用多核
- 智能保留：时间 + 路径综合判断，符合直觉

### 12.3 下一步

1. **用户审查设计文档** ← 当前阶段
2. **创建实现计划**（调用 writing-plans 技能）
3. **实现核心模块**（TDD 开发）
4. **集成测试 + 性能调优**
5. **打包发布**

---

**文档版本**: 1.0  
**最后更新**: 2026-10-05
