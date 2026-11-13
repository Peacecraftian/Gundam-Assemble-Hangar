"""Content hashes with stat-keyed memoization for interactive image loads."""
from functools import lru_cache
from hashlib import file_digest


def source_digest(path):
    try:
        with path.open('rb') as stream:
            return file_digest(stream, 'sha256').hexdigest()
    except OSError:
        return None


@lru_cache(maxsize=512)
def _file_digest(path, size, modified, changed, inode):
    return source_digest(path)


def current_digest(path):
    try:
        stat = path.stat()
        return _file_digest(path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
    except OSError:
        return None
