# 清华大学无穹书院课程复习平台

收集了一些适合穹宝体质的课程复习资料与题库，希望对大家有所帮助(´｡• ᵕ •｡`)

部分复习资料来源：

* [mathsdream/THU-math-source](https://github.com/mathsdream/THU-math-source)

如想参与建设或有更好的想法或建议，欢迎email与我们联系：2920095282@qq.com

---

## ⚠️ 重要：如何正确打开

**这是一个 Web 应用（不是普通网页），需要启动后端服务才能使用。不能直接双击 index.html！**

## 🚀 一键启动（Windows）

**第1步：** 下载或 clone 本仓库到你的电脑

**第2步：** 进入仓库文件夹，**双击 `start.bat`**

> 它会自动帮你完成：
> 1. 检测 Python 是否安装
> 2. 自动安装所需的依赖包
> 3. 启动 Web 服务
> 4. 弹出浏览器窗口

**第3步：** 浏览器自动打开 `http://127.0.0.1:8000`，开始使用

### 手动启动（备选）

```bash
# 安装依赖（仅首次需要）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制环境变量配置
cp .env.example .env   # 然后编辑 .env 填入你的 API Key

# 启动服务
python app.py
```

然后浏览器访问 👉 **http://127.0.0.1:8000**

## ❓ 常见问题

**Q: 为什么双击 index.html 显示拒绝访问？**
A: 这是 Web 应用，需要先运行 `start.bat` 启动后端服务，然后才能打开页面。

**Q: start.bat 怎么用？**
A: 在仓库文件夹里找到 `start.bat`，鼠标左键快速点两下即可。

**Q: 启动后浏览器没自动打开？**
A: 手动访问 `http://127.0.0.1:8000`

**Q: 提示 "Python 未找到"？**
A: 先安装 Python 3.9+：https://www.python.org/downloads/

## ✨ 功能

- 📄 **搜索复习资料** — 输入关键词，AI 自动检索 PDF 文档
- 📥 **直接下载** — 搜索结果中每个文件都带下载链接
- 📝 **生成练习题** — 说「生成线代填空题」，自动出 10 道概念填空题
- 🧠 **智能问答** — 基于 RAG 引擎，结合文档内容回答你的问题

## ⚙️ 配置

首次使用需要配置 API Key。复制 `.env.example` 为 `.env`，填入你的 Key：

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 通义千问 DashScope（默认，推荐） |
| `OPENAI_API_KEY` | OpenAI（可选） |
| `DEEPSEEK_API_KEY` | DeepSeek（可选） |

## 🛠 技术栈

- **LLM**: Qwen-Plus / GPT-4o-mini / DeepSeek-Chat
- **RAG**: 阿里百炼 text-embedding-v3 + 混合检索（语义+关键词）
- **框架**: LangGraph Agent + FastAPI + WebSocket
- **文档解析**: PyMuPDF + easyOCR + python-docx
