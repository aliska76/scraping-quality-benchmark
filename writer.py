"""
Writes scrape results to JSONL format.
One JSON object per line.
"""

import json
from pathlib import Path
from typing import List


class JSONLWriter:
    """Writes results to JSONL file."""
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._count = 0
    
    def open(self):
        if self._file is None:
            self._file = open(self.filepath, 'w', encoding='utf-8')
        return self
    
    def close(self):
        if self._file:
            self._file.close()
            self._file = None
    
    def write(self, data: dict) -> bool:
        if self._file is None:
            self.open()
        
        try:
            line = json.dumps(data, ensure_ascii=False)
            self._file.write(line + '\n')
            self._file.flush()
            self._count += 1
            return True
        except Exception as e:
            print(f"[ERROR] Failed to write: {e}")
            return False
    
    def write_result(self, result) -> bool:
        data = {
            'id': result.id,
            'url': result.url,
            'content': result.content,
            'status_code': result.status_code,
            'latency': result.latency,
        }
        return self.write(data)
    
    def write_batch(self, results: List) -> int:
        success = 0
        for r in results:
            if self.write_result(r):
                success += 1
        return success
    
    @property
    def count(self) -> int:
        return self._count
    
    def __enter__(self):
        return self.open()
    
    def __exit__(self, *args):
        self.close()