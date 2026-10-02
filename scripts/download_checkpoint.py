from pathlib import Path
import requests

url = 'https://scifact.s3.us-west-2.amazonaws.com/longchecker/latest/checkpoints/healthver.ckpt'
out = Path('work/checkpoints/healthver.ckpt')
out.parent.mkdir(parents=True, exist_ok=True)
tmp = out.with_suffix('.part')
existing = tmp.stat().st_size if tmp.exists() else 0
headers = {'Range': f'bytes={existing}-'} if existing else {}
with requests.get(url, headers=headers, stream=True, timeout=(30, 120)) as r:
    r.raise_for_status()
    total = existing + int(r.headers.get('Content-Length', 0))
    mode = 'ab' if existing else 'wb'
    done = existing
    with tmp.open(mode) as handle:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
                done += len(chunk)
                if done % (100 * 1024 * 1024) < len(chunk):
                    print(f'{done}/{total} bytes ({done/total:.1%})', flush=True)
tmp.replace(out)
print(f'completed {out} {out.stat().st_size} bytes')
