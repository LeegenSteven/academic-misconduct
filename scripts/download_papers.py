from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from itertools import chain
import re
import sys
import time
from urllib.parse import urlparse

import requests
import urllib3


TARGET = Path(r"D:\引文不端")

PAPERS = [
    (
        "核心01_Sarol_2024_Assessing_Citation_Integrity.pdf",
        ["pmc://PMC11231046"],
    ),
    (
        "核心02_Wadden_2022_MultiVerS.pdf",
        ["https://aclanthology.org/2022.findings-naacl.6.pdf"],
    ),
    (
        "核心03_Wadden_2020_SciFact_Fact_or_Fiction.pdf",
        ["https://aclanthology.org/2020.emnlp-main.609.pdf"],
    ),
    (
        "核心04_Gu_2021_PubMedBERT.pdf",
        ["https://arxiv.org/pdf/2007.15779"],
    ),
    (
        "核心05_Nogueira_2020_MonoT5_Document_Ranking.pdf",
        ["https://aclanthology.org/2020.findings-emnlp.63.pdf"],
    ),
    (
        "扩展01_Beltagy_2020_Longformer.pdf",
        ["https://arxiv.org/pdf/2004.05150"],
    ),
    (
        "扩展02_Sarrouti_2021_HealthVer.pdf",
        ["https://aclanthology.org/2021.findings-emnlp.297.pdf"],
    ),
    (
        "扩展03_Kotonya_2020_Public_Health_Fact_Checking.pdf",
        ["https://aclanthology.org/2020.emnlp-main.623.pdf"],
    ),
    (
        "扩展04_Kilicoglu_2019_Confirm_or_Refute.pdf",
        ["pmc://PMC7357398"],
    ),
    (
        "扩展05_Hsiao_2023_OpCitance.pdf",
        [
            "https://www.nature.com/articles/s41597-023-02134-x.pdf",
            "pmc://PMC10139909",
        ],
    ),
    (
        "扩展06_Li_2023_Cited_Text_Spans.pdf",
        ["https://arxiv.org/pdf/2309.06365"],
    ),
    (
        "扩展07_Cohan_2017_Contextualizing_Citations.pdf",
        ["https://arxiv.org/pdf/1705.08063"],
    ),
    (
        "扩展08_Chandrasekaran_2019_CL_SciSumm.pdf",
        ["https://arxiv.org/pdf/1907.09854"],
    ),
    (
        "扩展09_De_Lacey_1985_Quotation_and_Reference_Accuracy.pdf",
        ["pmc://PMC1416756"],
    ),
    (
        "扩展10_Jergas_2015_Quotation_Accuracy_Meta_Analysis.pdf",
        ["pmc://PMC4627914"],
    ),
    (
        "扩展11_Pavlovic_2021_Accuracy_of_Biomedical_Citations.pdf",
        ["pmc://PMC8048031"],
    ),
    (
        "扩展12_Kilicoglu_2018_Text_Mining_for_Research_Integrity.pdf",
        ["pmc://PMC6291799"],
    ),
    (
        "扩展13_Hsiao_2022_Retracted_Papers_in_Citation_Contexts.pdf",
        ["pmc://PMC9520488"],
    ),
    (
        "扩展14_Cohan_2019_Citation_Intent_Classification.pdf",
        ["https://aclanthology.org/N19-1361.pdf"],
    ),
    (
        "扩展15_Beltagy_2019_SciBERT.pdf",
        ["https://aclanthology.org/D19-1371.pdf"],
    ),
]


ARXIV_IP = "151.101.195.42"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def solve_pmc_challenge(session: requests.Session, pdf_url: str) -> requests.Response:
    challenge_page = session.get(pdf_url, timeout=(10, 30))
    challenge_page.raise_for_status()
    challenge_match = re.search(r'const POW_CHALLENGE = "([^"]+)"', challenge_page.text)
    difficulty_match = re.search(r'const POW_DIFFICULTY = "(\d+)"', challenge_page.text)
    if not challenge_match or not difficulty_match:
        raise ValueError("PMC PDF challenge was not recognized")
    challenge = challenge_match.group(1)
    prefix = "0" * int(difficulty_match.group(1))
    nonce = 0
    while not hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest().startswith(prefix):
        nonce += 1
    session.cookies.set(
        "cloudpmc-viewer-pow",
        f"{challenge},{nonce}",
        domain="pmc.ncbi.nlm.nih.gov",
        path="/",
    )
    return session.get(pdf_url, stream=True, timeout=(10, 45))


def open_response(session: requests.Session, url: str) -> requests.Response:
    if url.startswith("pmc://"):
        pmcid = url.removeprefix("pmc://")
        article_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
        article = session.get(article_url, timeout=(10, 30))
        article.raise_for_status()
        match = re.search(
            r'<meta\s+name="citation_pdf_url"\s+content="([^"]+)"',
            article.text,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError(f"PMC PDF URL was not found for {pmcid}")
        return solve_pmc_challenge(session, match.group(1))

    parsed = urlparse(url)
    if parsed.hostname == "arxiv.org":
        bypass_url = url.replace("https://arxiv.org", f"https://{ARXIV_IP}", 1)
        return session.get(
            bypass_url,
            headers={"Host": "arxiv.org"},
            stream=True,
            verify=False,
            timeout=(10, 45),
        )
    return session.get(url, stream=True, timeout=(10, 45))


def download(name: str, urls: list[str]) -> tuple[int, str]:
    destination = TARGET / name
    if destination.exists() and destination.read_bytes()[:5] == b"%PDF":
        return destination.stat().st_size, "existing"

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 Codex academic paper downloader"})
    errors = []
    for url in urls:
        temporary = destination.with_suffix(".pdf.part")
        try:
            response = open_response(session, url)
            response.raise_for_status()
            iterator = response.iter_content(chunk_size=256 * 1024)
            first_chunk = next(iterator)
            if not first_chunk.startswith(b"%PDF"):
                content_type = response.headers.get("content-type", "unknown")
                raise ValueError(f"not a PDF ({content_type})")
            digest = hashlib.sha256()
            size = 0
            with temporary.open("wb") as output:
                for chunk in chain((first_chunk,), iterator):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if size < 20_000:
                raise ValueError(f"PDF unexpectedly small ({size} bytes)")
            temporary.replace(destination)
            return size, digest.hexdigest()[:12]
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            if temporary.exists():
                temporary.unlink()
            time.sleep(1)
    raise RuntimeError("; ".join(errors))


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    failures = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(download, name, urls): (index, name)
            for index, (name, urls) in enumerate(PAPERS, start=1)
        }
        for future in as_completed(futures):
            index, name = futures[future]
            try:
                size, marker = future.result()
                print(
                    f"OK {index:02d}/{len(PAPERS)} {size / 1024:.1f} KiB {marker} {name}",
                    flush=True,
                )
            except Exception as exc:
                failures.append((name, str(exc)))
                print(f"FAIL {index:02d}/{len(PAPERS)} {name}: {exc}", flush=True)
    if failures:
        print("\nFailed downloads:", file=sys.stderr)
        for name, error in failures:
            print(f"- {name}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
