# 清华大学无穹书院课程复习平台

收集了一些适合穹宝体质的课程复习资料与题库，希望对大家有所帮助(´｡• ᵕ •｡`)

部分复习资料来源：

* [mathsdream/THU-math-source](https://github.com/mathsdream/THU-math-source)

如想参与建设或有更好的想法或建议，欢迎email与我们联系：2920095282@qq.com

---

## 🚀 一键启动

**Windows 用户：** 双击仓库根目录的 [**`start.bat`**](start.bat) 即可自动完成全部步骤 👇

> 1. 检测 Python 环境  ✓
> 2. 自动安装依赖     ✓
> 3. 启动 Web 服务     ✓
> 4. 打开浏览器        ✓

[![启动](https://img.shields.io/badge/🚀-双击_start.bat_启动-blue?style=for-the-badge)](start.bat)

### 手动启动（备选）

```bash
pip install -r requirements.txt
python app.py
```

然后浏览器访问 👉 **http://127.0.0.1:8000**

## ✨ 功能

- 📄 **搜索复习资料** — 输入关键词，AI 自动检索 PDF 文档
- 📦 **打包下载** — 搜索到的文档可一键打包为 ZIP 下载到本地
- 🧠 **智能问答** — 基于 RAG 引擎，结合文档内容回答你的问题

## ⚙️ 配置

在 `.env` 中设置 API Key（已预配阿里百炼工作空间）：

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 通义千问 DashScope（默认） |
| `OPENAI_API_KEY` | OpenAI（可选） |
| `DEEPSEEK_API_KEY` | DeepSeek（可选） |

## 🛠 技术栈

- **LLM**: Qwen-Plus / GPT-4o-mini / DeepSeek-Chat
- **RAG**: 阿里百炼 text-embedding-v3 + 混合检索（语义+关键词）
- **框架**: LangGraph Agent + FastAPI + WebSocket
- **文档解析**: PyMuPDF + easyOCR + python-docx
