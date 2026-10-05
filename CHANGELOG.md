# Changelog

All notable changes to this project will be documented in this file.

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
