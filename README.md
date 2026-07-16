# 穹途末路

这个仓库里收集了一些适合穹宝体质的课程复习资料与题库，并打造了一个一站式数学资料检索、AI题库生成工具，希望对大家有所帮助(´｡• ᵕ •｡`)

如想参与建设或有更好的想法或建议，欢迎 email 与我们联系：2920095282@qq.com

部分复习资料来源：

- **[mathsdream/THU-math-source](https://github.com/mathsdream/THU-math-source)**

- **伟大的蓝妈妈**

- **无穹书院五字班大群内各位同学的无私分享**

---

## 从零开始使用（写给第一次接触的人）

这是一个 **Web 应用**，不是普通的静态网页。**不能直接双击 index.html 打开**。你需要先启动一个后端服务，然后通过浏览器访问。

下面是完整步骤：

### 你需要准备什么

| 项目 | 说明 | 获取方式 |
|------|------|----------|
| 一台电脑 | Windows / macOS / Linux 均可 | 你正在用的这台 |
| Python | 版本 3.9 或更高（最好是3.13以上） | [python.org](https://www.python.org/downloads/) |
| API Key | 让 AI 工作的钥匙，免费申请 | 见下方说明 |

### 第 1 步：获取代码

在仓库页面点击绿色的 **Code → Download ZIP**，解压到电脑上。

### 第 2 步：配置 API Key

这个应用需要调用 AI 接口，你需要申请一个免费的 API Key。

**推荐使用阿里百炼（免费额度，国内直连）：**

1. 打开 https://bailian.console.aliyun.com
2. 注册/登录阿里云账号
3. 在「模型广场」找到 `qwen-plus`，开通服务
4. 在「API-KEY 管理」创建一个 **API Key**（以 `sk-` 开头）
5. 在仓库文件夹中找到 `.env.example` 文件
6. **复制一份并重命名为 `.env`**
7. 用记事本打开 `.env`，把 `DASHSCOPE_API_KEY=***` 里的 `***` 换成你刚申请的 Key
8. **关于工作空间地址**：如果你申请的是普通 API Key（`sk-` 开头），`.env` 里**不需要**填 `BAILIAN_BASE_URL`，系统自动使用公共地址。只有工作空间专用 Key（`sk-ws-` 开头）才需要填写对应的 `BAILIAN_BASE_URL`。

### 第 3 步：安装依赖

打开终端（CMD / PowerShell / 终端），进入仓库文件夹，运行：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 如果提示 `pip 不是命令`，说明 Python 没装好，回去检查第 0 步。

### 第 4 步：启动服务

你已经完成了所有准备工作！接下来在终端中输入：

```bash
python app.py
```

看到类似下面的输出就说明启动成功了：

```
INFO:     Uvicorn running on http://127.0.0.1:8000
[后台] 索引完成: 1674 个片段
```

> **首次启动**会自动索引仓库里的 PDF 文件（约 1-2 分钟），期间搜索功能不可用，稍等片刻即可。
> **第二次及之后启动**会从缓存加载，1 秒完成。

**Windows 用户：** 也可以双击 `start.bat`，自动完成第 3、4 步。
**Mac / Linux 用户：** 终端运行 `chmod +x start.sh && ./start.sh`。

### 第 5 步：打开页面

打开你的浏览器，在地址栏输入：

**http://127.0.0.1:8000**

看到聊天界面说明一切正常，可以试着让Agent检索复习资料或生成题目了。

### 关闭服务

在终端里按 `Ctrl + C` 即可停止服务。

### 常见问题

**Q: 提示 "Python 未找到"？**
A: 去 https://www.python.org/downloads/ 下载安装 Python 3.9+。安装时记得勾选「Add Python to PATH」。

**Q: 启动后浏览器没自动弹出来？**
A: 手动在浏览器地址栏输入 `http://127.0.0.1:8000` 即可。

**Q: 页面打开后是空白/无法连接？**
A: 确认终端还在运行（没有按 Ctrl+C）。如果终端退了，重新运行 `python app.py`。

**Q: 搜索说"知识库索引中"？**
A: 首次启动需要 1-2 分钟索引所有 PDF，等终端显示「索引完成」后再搜索。


**Q: API Key 分 `sk-` 和 `sk-ws-` 两种，有什么区别？**
A: `sk-` 是普通 Key，用公共地址；`sk-ws-` 是工作空间 Key，需要在 `.env` 里额外填 `BAILIAN_BASE_URL`。普通用户用 `sk-` 就行，配置更简单。

**Q: 可以部署到服务器上让别人访问吗？**
A: 可以，但需要修改 `app.py` 中的 `host="127.0.0.1"` 为 `host="0.0.0.0"`，并注意网络安全。

---

## 功能一览

| 功能 | 怎么用 | 示例 |
|------|--------|------|
| **搜索资料** | 直接说关键词 | 「搜一下微积分的资料」 |
| **下载文件** | 搜索结果自带下载按钮 | 点击即可下载 |
| **生成练习题** | 说"生成 + 科目 + 填空题" | 「生成线代填空题」 |
| **做习题** | 自动跳转到习题面板 | 填答案 → 提交批改 |

---


## 技术栈

- **LLM**: Qwen-Plus / GPT-4o-mini / DeepSeek-Chat
- **RAG**: 阿里百炼 text-embedding-v3 + 混合检索（语义+关键词）
- **框架**: LangGraph Agent + FastAPI + WebSocket + Python
- **前端**: HTML + CSS + Vanilla JS（无框架依赖）
- **文档解析**: PyMuPDF + python-docx
