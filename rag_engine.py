"""
RAG 引擎：索引 git 仓库代码 + PDF + Word 文档，提供检索增强生成。
"""

import os
import re
import pickle
import hashlib
from pathlib import Path
from typing import List

from openai import OpenAI
from config import LLM_CONFIG


# ── 文档加载 ─────────────────────────────

SKIP_EXTS = {".py", ".pyc", ".pyo", ".md", ".txt", ".yaml", ".yml", ".json",
              ".toml", ".cfg", ".ini", ".env.example", ".gitignore"}


def _load_pdf(path: Path) -> str:
    """提取 PDF 全文（跳过 OCR）"""
    import fitz
    doc = fitz.open(str(path))
    texts = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(texts).strip()


def _load_docx(path: Path) -> str:
    import docx
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def load_document(path: Path, use_ocr: bool = False) -> str | None:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return _load_pdf(path)
        elif ext in (".docx", ".doc"):
            return _load_docx(path)
        return None
    except Exception as e:
        print(f"  [WARN] 无法解析 {path.name}: {e}")
        return None


# ── 文件扫描（只扫 PDF/Word，控制深度）───

def load_codebase(root_dir: str) -> List[dict]:
    """加载仓库中所有 PDF/Word 文档"""
    docs = []
    root = Path(root_dir).resolve()
    # 只扫 PDF 和 Word 文件，跳过隐藏目录
    for f in root.rglob("*"):
        if any(part.startswith(".") for part in f.relative_to(root).parts):
            continue
        if f.is_file() and f.suffix.lower() in (".pdf", ".doc", ".docx"):
            content = load_document(f, use_ocr=False)
            if content and content.strip():
                docs.append({"path": str(f.relative_to(root)), "content": content})
    return docs


# ── 分块 ─────────────────────────────────

def chunk_document(doc: dict, chunk_size: int = 800, overlap: int = 100) -> List[dict]:
    lines = doc["content"].splitlines()
    chunks = []
    buffer = []
    size = 0
    for line in lines:
        buffer.append(line)
        size += len(line) + 1
        if size >= chunk_size:
            text = "\n".join(buffer)
            chunks.append({"path": doc["path"], "text": text, "seq": len(chunks)})
            overlap_lines = []
            overlap_size = 0
            for l in reversed(buffer):
                overlap_lines.insert(0, l)
                overlap_size += len(l) + 1
                if overlap_size >= overlap:
                    break
            buffer = overlap_lines
            size = overlap_size
    if buffer:
        chunks.append({"path": doc["path"], "text": "\n".join(buffer), "seq": len(chunks)})
    return chunks


# ── 分词 ─────────────────────────────────

def tokenize(text: str) -> List[str]:
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    english = re.findall(r"[a-zA-Z]+\d*|\d+[a-zA-Z]+", text)
    upper = re.findall(r"[A-Z]{2,}", text)
    tokens = [t.lower() for t in chinese + english + upper]
    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ── Embedding（批量版）───────────────────

def get_embeddings_batch(texts: List[str], client: OpenAI, model: str = "text-embedding-v3") -> List[List[float]]:
    """批量获取 embedding，一次 API 调用处理多条文本"""
    if not texts:
        return []
    # 分批：API 单次最多 2048 条
    # 阿里百炼 embedding API 限制单次最多 10 条
    batch_size = 10
    all_embeds = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        # 按输入顺序排序
        sorted_data = sorted(resp.data, key=lambda x: x.index)
        all_embeds.extend([d.embedding for d in sorted_data])
    return all_embeds


# ── 持久化索引 ──────────────────────────

INDEX_CACHE_FILE = None  # 在 RAGEngine.__init__ 中设置

def _cache_path(repo_dir: str) -> str:
    """基于目录内容的 hash 生成缓存路径"""
    return os.path.join(repo_dir, ".rag_cache.pkl")


def _compute_digest(repo_dir: str) -> str:
    """计算所有 PDF 文件的修改时间和大小的 hash，用于检测变更"""
    h = hashlib.md5()
    for f in sorted(Path(repo_dir).rglob("*.pdf")):
        if any(part.startswith(".") for part in f.relative_to(repo_dir).parts):
            continue
        stat = f.stat()
        h.update(f"{f.relative_to(repo_dir)}:{stat.st_mtime}:{stat.st_size}".encode())
    return h.hexdigest()


# ── 混合向量存储 ─────────────────────────

class SimpleVectorStore:
    def __init__(self):
        self.chunks: List[dict] = []
        self.embeddings: List[List[float]] = []
        self._term_index: dict[str, list[tuple[int, int]]] = {}

    def add(self, chunks: List[dict], embeddings: List[List[float]]):
        self.chunks.extend(chunks)
        self.embeddings.extend(embeddings)
        base = len(self.chunks) - len(chunks)
        for i, chunk in enumerate(chunks):
            tokens = tokenize(chunk["text"])
            term_counts = {}
            for t in tokens:
                term_counts[t] = term_counts.get(t, 0) + 1
            for term, count in term_counts.items():
                if term not in self._term_index:
                    self._term_index[term] = []
                self._term_index[term].append((base + i, count))

    def search(self, query_embed: List[float], top_k: int = 5) -> List[dict]:
        import numpy as np
        q = np.array(query_embed)
        scores = [
            np.dot(q, np.array(e)) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-10)
            for e in self.embeddings
        ]
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [{**self.chunks[i], "score": scores[i], "method": "semantic"} for i in top_indices]

    def keyword_search(self, query: str, top_k: int = 5) -> List[dict]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = [0.0] * len(self.chunks)
        import math
        N = len(self.chunks)
        for term in query_tokens:
            if term not in self._term_index:
                continue
            postings = self._term_index[term]
            df = len(postings)
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
            for idx, count in postings:
                scores[idx] += idf * (count / (count + 1.5))
        raw_query = query.lower()
        for i, chunk in enumerate(self.chunks):
            if raw_query in chunk["text"].lower():
                scores[i] += len(query_tokens) * 2
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [{**self.chunks[i], "score": scores[i], "method": "keyword"} for i in top_indices if scores[i] > 0]

    def hybrid_search(self, query: str, query_embed: List[float], top_k: int = 5, alpha: float = 0.5) -> List[dict]:
        import numpy as np
        q = np.array(query_embed)
        sem_scores = np.array([
            np.dot(q, np.array(e)) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-10)
            for e in self.embeddings
        ])
        sem_min, sem_max = sem_scores.min(), sem_scores.max()
        if sem_max > sem_min:
            sem_scores = (sem_scores - sem_min) / (sem_max - sem_min)

        query_tokens = tokenize(query)
        kw_scores = np.zeros(len(self.chunks))
        if query_tokens:
            import math
            N = len(self.chunks)
            for term in query_tokens:
                if term not in self._term_index:
                    continue
                postings = self._term_index[term]
                df = len(postings)
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                for idx, count in postings:
                    kw_scores[idx] += idf * (count / (count + 1.5))
            raw_query = query.lower()
            for i, chunk in enumerate(self.chunks):
                if raw_query in chunk["text"].lower():
                    kw_scores[i] += len(query_tokens) * 2
            kw_min, kw_max = kw_scores.min(), kw_scores.max()
            if kw_max > kw_min:
                kw_scores = (kw_scores - kw_min) / (kw_max - kw_min)

        combined = alpha * sem_scores + (1 - alpha) * kw_scores
        top_indices = sorted(range(len(combined)), key=lambda i: combined[i], reverse=True)[:top_k]
        return [{
            **self.chunks[i], "score": float(combined[i]),
            "sem_score": float(sem_scores[i]), "kw_score": float(kw_scores[i]),
            "method": "hybrid",
        } for i in top_indices]

    @property
    def size(self):
        return len(self.chunks)


# ── RAG Engine（全局单例 + 磁盘缓存）─────

_engine_instance = None
_engine_lock = threading_lock = None
import threading as _threading
_engine_lock = _threading.Lock()


class RAGEngine:
    def __init__(self, repo_dir: str):
        self.repo_dir = repo_dir
        self.store = SimpleVectorStore()
        cfg = LLM_CONFIG["dashscope"]
        self.client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
        self.embed_model = "text-embedding-v3"
        self._indexed = False
        self._cache_file = _cache_path(repo_dir)

    def _try_load_cache(self) -> bool:
        """尝试从磁盘加载缓存的索引"""
        cache_path = self._cache_file
        digest_path = cache_path + ".digest"
        if not os.path.exists(cache_path) or not os.path.exists(digest_path):
            return False
        try:
            with open(digest_path) as f:
                cached_digest = f.read().strip()
            if cached_digest != _compute_digest(self.repo_dir):
                print("  文件已变更，重新索引")
                return False
            with open(cache_path, "rb") as f:
                data = pickle.load(f)
            self.store.chunks = data["chunks"]
            self.store.embeddings = data["embeddings"]
            self.store._term_index = data["term_index"]
            self._indexed = True
            print(f"  从缓存加载: {len(self.store.chunks)} 个片段")
            return True
        except Exception as e:
            print(f"  缓存加载失败: {e}")
            return False

    def _save_cache(self):
        """将索引保存到磁盘"""
        try:
            data = {
                "chunks": self.store.chunks,
                "embeddings": self.store.embeddings,
                "term_index": self.store._term_index,
            }
            with open(self._cache_file, "wb") as f:
                pickle.dump(data, f)
            with open(self._cache_file + ".digest", "w") as f:
                f.write(_compute_digest(self.repo_dir))
            print(f"  索引已缓存到磁盘")
        except Exception as e:
            print(f"  缓存保存失败: {e}")

    def index(self):
        """索引整个仓库"""
        # 先尝试从缓存加载
        if self._try_load_cache():
            return len(self.store.chunks)

        print(f"  扫描目录: {self.repo_dir}")
        docs = load_codebase(self.repo_dir)
        print(f"  发现 {len(docs)} 个文档")

        # 分批分块 + 批量 embedding
        all_chunks = []
        for doc in docs:
            chunks = chunk_document(doc)
            all_chunks.extend(chunks)

        print(f"  分块: {len(all_chunks)} 个片段")
        print(f"  生成 embedding（批量处理 {len(all_chunks)} 条）...")

        chunk_texts = [c["text"] for c in all_chunks]
        all_embeds = get_embeddings_batch(chunk_texts, self.client, self.embed_model)

        self.store.add(all_chunks, all_embeds)
        self._indexed = True
        self._save_cache()
        print(f"  索引完成: {len(all_chunks)} 个片段")
        return len(all_chunks)

    def retrieve(self, query: str, top_k: int = 5, mode: str = "hybrid", alpha: float = 0.5) -> List[dict]:
        if not self._indexed:
            self.index()
        q_emb = get_embeddings_batch([query], self.client, self.embed_model)[0]
        if mode == "keyword":
            return self.store.keyword_search(query, top_k=top_k)
        elif mode == "semantic":
            return self.store.search(q_emb, top_k=top_k)
        else:
            return self.store.hybrid_search(query, q_emb, top_k=top_k, alpha=alpha)

    def build_context(self, results: List[dict]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r['path']} (相似度: {r['score']:.3f})\n```\n{r['text'][:1500]}\n```")
        return "\n\n".join(parts)

    def query(self, question: str, top_k: int = 5) -> dict:
        results = self.retrieve(question, top_k=top_k)
        context = self.build_context(results)
        cfg = LLM_CONFIG["dashscope"]
        llm_client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
        system_msg = (
            "你是一个知识库助手。你的知识库是当前项目中的所有文档（代码、PDF、Word 等）。\n"
            "请根据检索到的文档内容回答用户问题。\n"
            "回答必须使用中文。\n"
            "引用文档时请标注文件路径和 [1]、[2] 编号。\n"
            "如果检索到的内容不足以回答问题，请明确告知。"
        )
        resp = llm_client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"问题：{question}\n\n相关文档内容：\n{context}"},
            ],
            temperature=0.2,
        )
        answer = resp.choices[0].message.content.strip()
        return {"answer": answer, "sources": list(set(r["path"] for r in results)), "context": context}


def get_engine(repo_dir: str) -> RAGEngine:
    """获取全局唯一的 RAGEngine 实例"""
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = RAGEngine(repo_dir)
    return _engine_instance
