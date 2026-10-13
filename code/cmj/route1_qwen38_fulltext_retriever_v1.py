"""
路线一 被引全文检索模块
功能：PDF/XML全文解析 → 句段切分 → 页/段/句/字符位置映射 → BM25检索
输出：原文句段 + 位置信息（页/段/句/字符偏移）
"""
import os, re, json, hashlib
from pathlib import Path
from typing import List, Dict, Optional

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


class Sentence:
    """一个句子单元，包含位置信息"""
    def __init__(self, text: str, page: int, paragraph: int, sentence_idx: int,
                 char_start: int, char_end: int, source_file: str = ""):
        self.text = text.strip()
        self.page = page
        self.paragraph = paragraph
        self.sentence_idx = sentence_idx
        self.char_start = char_start
        self.char_end = char_end
        self.source_file = source_file
        self.sentence_id = f"P{page:03d}:S{sentence_idx:03d}"

    def to_dict(self):
        return {
            "sentence_id": self.sentence_id,
            "text": self.text,
            "page": self.page,
            "paragraph": self.paragraph,
            "sentence_idx": self.sentence_idx,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "source_file": self.source_file,
        }


class FullTextRetriever:
    """被引全文解析与BM25检索"""

    def __init__(self):
        self.sentences: List[Sentence] = []
        self.bm25 = None
        self.tokenized_corpus = []
        self.source_hash = ""

    def parse_pdf(self, pdf_path: str) -> List[Sentence]:
        """解析PDF，提取带位置信息的句子"""
        if not HAS_PYMUPDF:
            raise ImportError("需要安装PyMuPDF: pip install pymupdf")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF不存在: {pdf_path}")

        # 计算文件哈希
        with open(pdf_path, "rb") as f:
            self.source_hash = hashlib.sha256(f.read()).hexdigest()

        doc = fitz.open(pdf_path)
        sentences = []
        global_char_offset = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            # 按段落分割（空行）
            paragraphs = re.split(r'\n\s*\n', text)
            for para_idx, para in enumerate(paragraphs):
                para = para.strip()
                if not para:
                    continue
                # 按句子分割（简单规则：.!?后跟空格或换行）
                raw_sentences = re.split(r'(?<=[.!?])\s+', para)
                for sent_idx, sent in enumerate(raw_sentences):
                    sent = sent.strip()
                    if len(sent) < 10:  # 跳过过短的片段
                        continue
                    char_start = global_char_offset + text.find(sent) if sent in text else global_char_offset
                    char_end = char_start + len(sent)
                    sentences.append(Sentence(
                        text=sent,
                        page=page_num + 1,  # 1-based页码
                        paragraph=para_idx,
                        sentence_idx=sent_idx,
                        char_start=char_start,
                        char_end=char_end,
                        source_file=os.path.basename(pdf_path),
                    ))
                global_char_offset += len(para) + 2

        doc.close()
        self.sentences = sentences
        self._build_bm25()
        return sentences

    def parse_xml(self, xml_path: str) -> List[Sentence]:
        """解析PMC XML/BioC JSON，提取带位置信息的句子"""
        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"XML不存在: {xml_path}")

        with open(xml_path, "rb") as f:
            self.source_hash = hashlib.sha256(f.read()).hexdigest()

        # BioC JSON格式
        if xml_path.endswith(".json"):
            with open(xml_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sentences = self._parse_bioc_json(data)
        else:
            # 简单XML解析
            import xml.etree.ElementTree as ET
            tree = ET.parse(xml_path)
            root = tree.getroot()
            sentences = self._parse_pmc_xml(root)

        self.sentences = sentences
        self._build_bm25()
        return sentences

    def _parse_bioc_json(self, data: dict) -> List[Sentence]:
        """解析BioC JSON格式"""
        sentences = []
        for doc in data.get("documents", []):
            for passage in doc.get("passages", []):
                text = passage.get("text", "")
                section = passage.get("infons", {}).get("section", "unknown")
                offset = int(passage.get("offset", 0))
                raw_sents = re.split(r'(?<=[.!?])\s+', text)
                for sent_idx, sent in enumerate(raw_sents):
                    sent = sent.strip()
                    if len(sent) < 10:
                        continue
                    sentences.append(Sentence(
                        text=sent,
                        page=0,  # XML无页码
                        paragraph=hash(section) % 10000,
                        sentence_idx=sent_idx,
                        char_start=offset,
                        char_end=offset + len(sent),
                        source_file=section,
                    ))
        return sentences

    def _parse_pmc_xml(self, root) -> List[Sentence]:
        """解析PMC XML格式（简化版）"""
        sentences = []
        # 提取abstract和body中的段落
        for elem in root.iter():
            if elem.tag in ["p", "abstract", "title"]:
                text = "".join(elem.itertext()).strip()
                if len(text) < 10:
                    continue
                raw_sents = re.split(r'(?<=[.!?])\s+', text)
                for sent_idx, sent in enumerate(raw_sents):
                    sent = sent.strip()
                    if len(sent) < 10:
                        continue
                    sentences.append(Sentence(
                        text=sent,
                        page=0,
                        paragraph=abs(hash(elem.tag)) % 10000,
                        sentence_idx=sent_idx,
                        char_start=0,
                        char_end=len(sent),
                        source_file=elem.tag,
                    ))
        return sentences

    def _tokenize(self, text: str) -> List[str]:
        """简单分词：小写+非字母数字分割"""
        return re.findall(r'[a-z0-9]+', text.lower())

    def _build_bm25(self):
        """构建BM25索引"""
        if not HAS_BM25:
            print("警告: rank_bm25未安装，BM25检索不可用。pip install rank_bm25")
            return
        self.tokenized_corpus = [self._tokenize(s.text) for s in self.sentences]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """BM25检索，返回top_k个句子及位置信息"""
        if self.bm25 is None:
            raise RuntimeError("BM25索引未构建，请先调用parse_pdf或parse_xml")

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for rank, idx in enumerate(top_indices):
            sent = self.sentences[idx]
            results.append({
                "rank": rank + 1,
                "score": round(float(scores[idx]), 4),
                **sent.to_dict(),
            })
        return results

    def get_sentence_by_id(self, sentence_id: str) -> Optional[Dict]:
        """按sentence_id获取句子"""
        for s in self.sentences:
            if s.sentence_id == sentence_id:
                return s.to_dict()
        return None

    def save_index(self, output_path: str):
        """保存解析结果为JSONL"""
        with open(output_path, "w", encoding="utf-8") as f:
            for s in self.sentences:
                f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
        # 保存元信息
        meta = {
            "source_hash": self.source_hash,
            "total_sentences": len(self.sentences),
            "output_file": os.path.basename(output_path),
        }
        with open(output_path + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        print(f"索引已保存: {output_path} ({len(self.sentences)}句)")

    def load_index(self, index_path: str):
        """从JSONL加载索引"""
        self.sentences = []
        with open(index_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                s = Sentence(
                    text=d["text"], page=d["page"], paragraph=d["paragraph"],
                    sentence_idx=d["sentence_idx"], char_start=d["char_start"],
                    char_end=d["char_end"], source_file=d.get("source_file", "")
                )
                self.sentences.append(s)
        self._build_bm25()
        print(f"索引已加载: {index_path} ({len(self.sentences)}句)")


# ========== 命令行使用 ==========
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="被引全文解析与BM25检索")
    parser.add_argument("--input", required=True, help="PDF或XML文件路径")
    parser.add_argument("--query", type=str, default=None, help="检索查询")
    parser.add_argument("--top_k", type=int, default=10)
    parser.add_argument("--save_index", type=str, default=None, help="保存索引路径")
    args = parser.parse_args()

    retriever = FullTextRetriever()

    if args.input.endswith(".pdf"):
        sents = retriever.parse_pdf(args.input)
    else:
        sents = retriever.parse_xml(args.input)

    print(f"解析完成: {len(sents)} 句")

    if args.save_index:
        retriever.save_index(args.save_index)

    if args.query:
        results = retriever.search(args.query, top_k=args.top_k)
        print(f"\nBM25检索 (top-{args.top_k}):")
        for r in results:
            print(f"  [{r['rank']}] score={r['score']} {r['sentence_id']} (p{r['page']})")
            print(f"      {r['text'][:120]}...")
