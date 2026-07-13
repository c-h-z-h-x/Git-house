"""
RAG 引擎：索引 git 仓库代码，提供检索增强生成。
复用自你的 rag 作业代码风格，适配 LangChain Agent。
"""

import os
import re
from pathlib import Path
from typing import List

from openai import OpenAI
from config import LLM_CONFIG


# ── 文档加载 ─────────────────────────────

IGNORE_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules"}
IGNORE_EXTS = {".pyc", ".pyo"}
TEXT_EXTS = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".json",
    ".toml", ".cfg", ".ini", ".env.example", ".gitignore",
}


def load_codebase(root_dir: str) -> List[dict]:
    """加载仓库中所有文本文件，返回 [{path, content}]"""
    docs = []
    root = Path(root_dir).resolve()
    for f in root.rglob("*"):
        if any(part.startswith(".") for part in f.relative_to(root).parts):
            continue
        if f.suffix in IGNORE_EXTS or f.suffix not in TEXT_EXTS:
            continue
        if f.is_file():
            try:
                content = f.read_text(encoding="utf-8")
                if content.strip():
                    docs.append({"path": str(f.relative_to(root)), "content": content})
            except Exception:
                pass
    return docs


# ── 分块 ─────────────────────────────────

def chunk_document(doc: dict, chunk_size: int = 800, overlap: int = 100) -> List[dict]:
    """将文档按行分块，保留路径信息"""
    lines = doc["content"].splitlines()
    chunks = []
    buffer = []
    size = 0

    for line in lines:
        buffer.append(line)
        size += len(line) + 1
        if size >= chunk_size:
            text = "\n".join(buffer)
            chunks.append({
                "path": doc["path"],
                "text": text,
                "seq": len(chunks),
            })
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
        chunks.append({
            "path": doc["path"],
            "text": "\n".join(buffer),
            "seq": len(chunks),
        })
    return chunks


# ── Embedding ────────────────────────────

def get_embedding(text: str, client: OpenAI, model: str = "text-embedding-v3") -> List[float]:
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding


# ── 简单向量存储（内存版）────────────────

class SimpleVectorStore:
    """简易向量存储，生产环境可用 Chroma/Qdrant 替代"""

    def __init__(self):
        self.chunks: List[dict] = []
        self.embeddings: List[List[float]] = []

    def add(self, chunks: List[dict], embeddings: List[List[float]]):
        self.chunks.extend(chunks)
        self.embeddings.extend(embeddings)

    def search(self, query_embed: List[float], top_k: int = 5) -> List[dict]:
        import numpy as np
        q = np.array(query_embed)
        scores = [np.dot(q, np.array(e)) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-10)
                  for e in self.embeddings]
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            {**self.chunks[i], "score": scores[i]}
            for i in top_indices
        ]


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
        """索引整个仓库"""
        docs = load_codebase(self.repo_dir)
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
        return len(all_chunks)

    def retrieve(self, query: str, top_k: int = 5) -> List[dict]:
        if not self._indexed:
            self.index()
        q_emb = get_embedding(query, self.client, self.embed_model)
        return self.store.search(q_emb, top_k=top_k)

    def build_context(self, results: List[dict]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] {r['path']} (相似度: {r['score']:.3f})\n"
                f"```\n{r['text']}\n```"
            )
        return "\n\n".join(parts)

    def query(self, question: str, top_k: int = 5) -> dict:
        """一站式 RAG 问答"""
        results = self.retrieve(question, top_k=top_k)
        context = self.build_context(results)

        cfg = LLM_CONFIG["dashscope"]
        llm_client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])

        system_msg = (
            "你是一个代码仓库助手。你的知识库是当前项目的所有代码文件。\n"
            "请根据检索到的代码上下文回答用户问题。\n"
            "回答必须使用中文。\n"
            "引用代码时请标注文件路径和 [1]、[2] 编号。\n"
            "如果检索到的内容不足以回答问题，请明确告知。"
        )

        user_msg = f"问题：{question}\n\n相关代码上下文：\n{context}"

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
            "sources": [r["path"] for r in results],
            "context": context,
        }
