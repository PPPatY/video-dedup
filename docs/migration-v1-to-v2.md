# 从 v1.x 迁移到 v2.0.0

## 概述

video-dedup v2.0.0 引入了子命令架构以支持图片去重。这是一个破坏性变更，需要更新命令行语法。

## 主要变更

### 1. CLI 语法变更（必须）

**v1.x**:
```bash
video-dedup ~/Videos
video-dedup ~/Videos --dry-run
video-dedup ~/Videos --exclude "iMovie 项目"
```

**v2.0.0**:
```bash
video-dedup video ~/Videos
video-dedup video ~/Videos --dry-run
video-dedup video ~/Videos --exclude "iMovie 项目"
```

**快速替换**：在所有脚本中，将 `video-dedup ` 替换为 `video-dedup video `（注意空格）。

### 2. 新增图片支持（可选）

```bash
# 图片去重（新功能）
video-dedup image ~/Photos
video-dedup image ~/Photos --dry-run
```

### 3. 智能保留策略（自动）

- **视频**：默认保留最早的文件（与 v1.x 行为相同）
- **图片**：默认保留最新的文件（新行为）

**手动覆盖**：
```bash
video-dedup video ~/Videos --keep-strategy newest  # 视频也保留最新
video-dedup image ~/Photos --keep-strategy oldest  # 图片也保留最早
```

### 4. 缓存兼容性（无需操作）

- 缓存数据库位置不变（`~/.video-dedup/hashes.db`）
- v2.0.0 可以继续使用现有缓存，无需清空

## 迁移检查清单

- [ ] 更新所有脚本中的 `video-dedup` 命令，添加 `video` 子命令
- [ ] 更新 cron 任务或自动化脚本
- [ ] 测试新语法：`video-dedup video ~/Videos --dry-run`
- [ ] （可选）尝试图片去重：`video-dedup image ~/Photos --dry-run`

## 常见问题

### Q: 为什么要做这个破坏性变更？

A: 子命令架构是支持多种文件类型的标准方式，为未来扩展（如音频去重）奠定基础。

### Q: 如果我不小心使用了旧语法会怎样？

A: 当第一个参数是一个已存在的路径时，v2.0.0 会检测到旧用法并显示提示：
```
错误：video-dedup v2.0 需要指定子命令

旧用法: video-dedup <目录>
新用法: video-dedup video <目录>
       video-dedup image <目录>
```

### Q: v1.x 的缓存还能用吗？

A: 可以。缓存位置和格式未变，v2.0.0 会继续使用现有缓存数据。

### Q: 图片去重的保留策略是什么？

A: 默认保留**最新**修改的文件（编辑后版本通常更好）。可通过 `--keep-strategy oldest` 覆盖。

### Q: 我能回退到 v1.x 吗？

A: 可以。只需：
```bash
git checkout v1.0.0
pip install -e .
```

（前提是仓库中存在 `v1.0.0` 标签；否则请检出 v1.x 对应的提交。）

## 获取帮助

```bash
video-dedup --help       # 查看子命令列表
video-dedup video --help # 查看 video 子命令帮助
video-dedup image --help # 查看 image 子命令帮助
```

## 反馈

遇到问题？请提交 GitHub Issue。
