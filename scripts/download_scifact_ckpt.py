# -*- coding: utf-8 -*-
"""
多线程分片下载 scifact.ckpt（走代理 127.0.0.1:7897）
- 8 线程，每线程负责一段，失败自动重试
- 支持断点续传（.part 已存在则跳过该段）
- 完成后校验总大小并拼接
"""
import os
import sys
import time
import urllib.request
import threading
from pathlib import Path

URL = "https://scifact.s3.us-west-2.amazonaws.com/longchecker/latest/checkpoints/scifact.ckpt"
PROXY = "http://127.0.0.1:7897"
DEST = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\checkpoints\scifact.ckpt")
PARTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\checkpoints\_parts_scifact")
N_THREADS = 8
LOG = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\checkpoints\download_scifact.log")
RETRIES = 8


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def opener():
    ph = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    return urllib.request.build_opener(ph)


def get_size():
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(URL, method="HEAD")
            with opener().open(req, timeout=30) as r:
                return int(r.headers["Content-Length"])
        except Exception as e:
            log(f"HEAD 失败({attempt+1}): {e}")
            time.sleep(3)
    raise RuntimeError("无法获取文件大小")


def download_part(index, start, end):
    part = PARTS / f"part_{index:02d}"
    done = part.stat().st_size if part.exists() else 0
    if done >= (end - start):
        return done
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(URL, headers={"Range": f"bytes={start+done}-{end-1}"})
            mode = "ab" if done > 0 else "wb"
            got = 0
            with opener().open(req, timeout=90) as r, part.open(mode) as f:
                while True:
                    buf = r.read(1 << 16)
                    if not buf:
                        break
                    f.write(buf)
                    got += len(buf)
            # 校验该段是否完整
            if part.stat().st_size >= (end - start):
                log(f"段 {index:02d} 完成 ({end-start} 字节)")
                return part.stat().st_size
            else:
                raise IOError("段不完整")
        except Exception as e:
            log(f"段 {index:02d} 第{attempt+1}次失败: {str(e)[:100]}，续传重试")
            time.sleep(2)
    raise RuntimeError(f"段 {index:02d} 多次失败")


def main():
    LOG.unlink(missing_ok=True)
    PARTS.mkdir(parents=True, exist_ok=True)
    total = get_size()
    log(f"文件总大小: {total} 字节 ({total/1024/1024:.2f} MB)")
    chunk = total // N_THREADS
    ranges = [(i, i * chunk, (i + 1) * chunk if i < N_THREADS - 1 else total) for i in range(N_THREADS)]

    threads = []
    results = [None] * N_THREADS
    for i, (idx, s, e) in enumerate(ranges):
        t = threading.Thread(target=lambda k=idx, ss=s, ee=e: results.__setitem__(k, download_part(k, ss, ee)))
        threads.append(t)
        t.start()

    t0 = time.time()
    last_report = 0
    while any(t.is_alive() for t in threads):
        time.sleep(5)
        done = sum(p.stat().st_size for p in PARTS.glob("part_*"))
        now = time.time()
        if now - last_report > 30:
            speed = done / 1024 / 1024 / (now - t0)
            pct = done / total * 100
            log(f"进度 {pct:.1f}% ({done/1024/1024:.0f}/{total/1024/1024:.0f} MB) @ {speed:.2f} MB/s")
            last_report = now
    for t in threads:
        t.join()

    # 合并
    log("所有段完成，开始拼接...")
    with DEST.open("wb") as out:
        for i in range(N_THREADS):
            part = PARTS / f"part_{i:02d}"
            out.write(part.read_bytes())
    final = DEST.stat().st_size
    log(f"拼接完成: {final} 字节，与预期 {total} 比对: {'一致 ✅' if final == total else '不一致 ❌'}")
    # 清理 parts
    for p in PARTS.glob("part_*"):
        p.unlink()


if __name__ == "__main__":
    main()
