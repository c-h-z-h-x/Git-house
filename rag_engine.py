"""
RAG 引擎：索引 git 仓库代码 + PDF + Word 文档，提供检索增强生成。
"""

import os
import re
from pathlib import Path
from typing import List

from openai import OpenAI
from config import LLM_CONFIG


# ── 文档加载（支持 .py .md .txt .pdf .docx）────

IGNORE_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules"}

TEXT_EXTS = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".json",
    ".toml", ".cfg", ".ini", ".env.example", ".gitignore",
}


def _load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_pdf(path: Path) -> str:
    """提取 PDF 全文"""
    import fitz
    doc = fitz.open(str(path))
    texts = []
    for page in doc:
        texts.append(page.get_text())
    doc.close()
    return "\n".join(texts)


def _load_docx(path: Path) -> str:
    """提取 Word 全文"""
    import docx
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def load_document(path: Path) -> str | None:
    """根据扩展名自动选择解析器"""
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTS:
            return _load_text_file(path)
        elif ext == ".pdf":
            return _load_pdf(path)
        elif ext == ".docx":
            return _load_docx(path)
        elif ext == ".doc":
            return _load_docx(path)  # .doc 也尝试用 python-docx
        return None
    except Exception as e:
        print(f"  [WARN] 无法解析 {path.name}: {e}")
        return None


def load_codebase(root_dir: str) -> List[dict]:
    """加载仓库中所有支持的文件"""
    docs = []
    root = Path(root_dir).resolve()
    for f in root.rglob("*"):
        # 跳过隐藏目录
        if any(part.startswith(".") for part in f.relative_to(root).parts):
            continue
        if f.is_file():
            content = load_document(f)
            if content and content.strip():
                docs.append({"path": str(f.relative_to(root)), "content": content})
    return docs


# ── 分块 ─────────────────────────────────

def chunk_document(doc: dict, chunk_size: int = 800, overlap: int = 100) -> List[dict]:
    """将文档按行分块"""
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
            # overlap: 保留尾部若干行
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


# ── 分词工具 ─────────────────────────────

def tokenize(text: str) -> List[str]:
    """简单分词：保留中文词 + 英文单词 + 数字，过滤停用词"""
    import re
    # 提取中文词（2字以上）
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    # 提取英文单词 + 数字
    english = re.findall(r"[a-zA-Z]+\d*|\d+[a-zA-Z]+", text)
    # 提取首字母缩写（如 CMake, RAG）
    upper = re.findall(r"[A-Z]{2,}", text)
    
    tokens = chinese + english + upper
    # 转小写归一化
    tokens = [t.lower() for t in tokens]
    # 去重但保留顺序
    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ── Embedding ────────────────────────────

def get_embedding(text: str, client: OpenAI, model: str = "text-embedding-v3") -> List[float]:
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding


# ── 混合向量存储（语义 + 关键词）───────────

class SimpleVectorStore:
    """
    简易向量存储 + 关键词搜索（BM25 风格）
    
    - search(): 纯语义搜索（余弦相似度）
    - keyword_search(): 纯关键词搜索（词频匹配）
    - hybrid_search(): 语义 + 关键词加权融合
    """

    def __init__(self):
        self.chunks: List[dict] = []
        self.embeddings: List[List[float]] = []
        # 关键词索引
        self._term_index: dict[str, list[tuple[int, int]]] = {}  # term -> [(chunk_idx, count)]

    def add(self, chunks: List[dict], embeddings: List[List[float]]):
        self.chunks.extend(chunks)
        self.embeddings.extend(embeddings)
        # 建立倒排索引
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
        """纯语义搜索：余弦相似度"""
        import numpy as np
        q = np.array(query_embed)
        scores = [
            np.dot(q, np.array(e)) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-10)
            for e in self.embeddings
        ]
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [{**self.chunks[i], "score": scores[i], "method": "semantic"} for i in top_indices]

    def keyword_search(self, query: str, top_k: int = 5) -> List[dict]:
        """
        关键词搜索：基于 BM25 风格的词频匹配
        特别适合搜课程名："人工智能导引"、"微积分A"、"大学物理"
        """
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # 对每个 chunk 计算关键词得分
        scores = [0.0] * len(self.chunks)
        import math
        N = len(self.chunks)
        
        for term in query_tokens:
            if term not in self._term_index:
                continue
            postings = self._term_index[term]
            df = len(postings)  # 包含该词的文档数
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
            for idx, count in postings:
                scores[idx] += idf * (count / (count + 1.5))

        # 额外加分：完整短语匹配（如 "人工智能导引" 完全出现在 chunk 中）
        raw_query = query.lower()
        for i, chunk in enumerate(self.chunks):
            if raw_query in chunk["text"].lower():
                scores[i] += len(query_tokens) * 2

        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]
        return [{**self.chunks[i], "score": scores[i], "method": "keyword"} for i in top_indices if scores[i] > 0]

    def hybrid_search(self, query: str, query_embed: List[float], top_k: int = 5,
                      alpha: float = 0.5) -> List[dict]:
        """
        混合搜索：语义 + 关键词，按权重融合
        alpha=1: 纯语义  alpha=0: 纯关键词
        """
        import numpy as np
        
        # 语义得分（归一化到 [0,1]）
        q = np.array(query_embed)
        sem_scores = np.array([
            np.dot(q, np.array(e)) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-10)
            for e in self.embeddings
        ])
        sem_min, sem_max = sem_scores.min(), sem_scores.max()
        if sem_max > sem_min:
            sem_scores = (sem_scores - sem_min) / (sem_max - sem_min)

        # 关键词得分（归一化到 [0,1]）
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

        # 加权融合
        combined = alpha * sem_scores + (1 - alpha) * kw_scores
        top_indices = sorted(
            range(len(combined)), key=lambda i: combined[i], reverse=True
        )[:top_k]
        return [{
            **self.chunks[i],
            "score": float(combined[i]),
            "sem_score": float(sem_scores[i]),
            "kw_score": float(kw_scores[i]),
            "method": "hybrid",
        } for i in top_indices]

    @property
    def size(self):
        return len(self.chunks)


# ── RAG Engine ───────────────────────────

class RAGEngine:
    def __init__(self, repo_dir: str):
        self.repo_dir = repo_dir
        self.store = SimpleVectorStore()
        cfg = LLM_CONFIG["dashscope"]
        self.client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
        self.embed_model = "text-embedding-v3"
        self._indexed = False

    def index(self):
        """索引整个仓库（代码 + PDF + Word）"""
        print(f"  扫描目录: {self.repo_dir}")
        docs = load_codebase(self.repo_dir)
        print(f"  发现 {len(docs)} 个文档")

        all_chunks = []
        all_embeds = []
        for doc in docs:
            chunks = chunk_document(doc)
            for chunk in chunks:
                emb = get_embedding(chunk["text"], self.client, self.embed_model)
                all_chunks.append(chunk)
                all_embeds.append(emb)

        self.store.add(all_chunks, all_embeds)
        self._indexed = True
        print(f"  已索引 {len(all_chunks)} 个片段")
        return len(all_chunks)

    def retrieve(self, query: str, top_k: int = 5, mode: str = "hybrid",
                   alpha: float = 0.5) -> List[dict]:
        """检索文档
        
        参数:
            mode: "hybrid" 混合 / "semantic" 纯语义 / "keyword" 纯关键词
            alpha: 混合权重（1=纯语义, 0=纯关键词）
        """
        if not self._indexed:
            self.index()
        q_emb = get_embedding(query, self.client, self.embed_model)
        
        if mode == "keyword":
            return self.store.keyword_search(query, top_k=top_k)
        elif mode == "semantic":
            return self.store.search(q_emb, top_k=top_k)
        else:
            return self.store.hybrid_search(query, q_emb, top_k=top_k, alpha=alpha)

    def build_context(self, results: List[dict]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] {r['path']} (相似度: {r['score']:.3f})\n"
                f"```\n{r['text'][:1500]}\n```"
            )
        return "\n\n".join(parts)

    def query(self, question: str, top_k: int = 5) -> dict:
        """一站式 RAG 问答"""
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

        user_msg = f"问题：{question}\n\n相关文档内容：\n{context}"

        resp = llm_client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
        )
        answer = resp.choices[0].message.content.strip()

        return {
            "answer": answer,
            "sources": list(set(r["path"] for r in results)),
            "context": context,
        }
