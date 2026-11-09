import urllib.request
import struct
import io
import zipfile

import urllib.request
import struct
import io
import time
import zipfile

class RemoteZipFile(io.RawIOBase):
    def __init__(self, url, buffer_size=2 * 1024 * 1024):
        self.url = url
        self.buffer_size = buffer_size
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    cr = resp.headers.get("Content-Range")
                    self.size = int(cr.split("/")[-1])
                    break
            except Exception as e:
                if attempt == 4:
                    raise
                time.sleep(2.0 * (attempt + 1))
        self.pos = 0
        self.buf = b""
        self.buf_start = 0

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        return self.pos

    def tell(self):
        return self.pos

    def _fetch_range(self, start, end, retries=3):
        for attempt in range(retries):
            try:
                req = urllib.request.Request(self.url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Range": f"bytes={start}-{end}"
                })
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read()
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(1.0 * (attempt + 1))
        return b""

    def read(self, size=-1):
        if size == -1 or self.pos + size > self.size:
            size = self.size - self.pos
        if size <= 0:
            return b""

        # Check if requested range is in buffer
        buf_end = self.buf_start + len(self.buf)
        if self.buf_start <= self.pos < buf_end:
            available = buf_end - self.pos
            if size <= available:
                data = self.buf[self.pos - self.buf_start : self.pos - self.buf_start + size]
                self.pos += size
                return data
            else:
                part1 = self.buf[self.pos - self.buf_start :]
                self.pos += len(part1)
                remaining = size - len(part1)
                part2 = self.read(remaining)
                return part1 + part2

        # Needs fetch: fetch at least buffer_size
        fetch_len = max(size, self.buffer_size)
        fetch_end = min(self.size - 1, self.pos + fetch_len - 1)
        self.buf = self._fetch_range(self.pos, fetch_end)
        self.buf_start = self.pos

        actual_read = min(size, len(self.buf))
        data = self.buf[:actual_read]
        self.pos += actual_read
        return data

if __name__ == "__main__":
    try:
        url = "https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.zip"
        print("Connecting to remote zip...")
        rz = RemoteZipFile(url)
        print("Zip size:", rz.size)
        zf = zipfile.ZipFile(rz)
        print("Archive contains files:")
        for info in zf.infolist():
            print(f"  {info.filename} ({info.file_size} bytes, compressed {info.compress_size})")
    except Exception as e:
        print("Remote zip error:", e)
