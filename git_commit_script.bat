git add -A
git commit -m "fix: 下载按钮无法点击（中文文件名不匹配正则）

- app.py/agent.py: 中文文件名保留（isalnum 自动含 Unicode）
- index.html: linkify 正则从 [\w.-]+ 放宽为 [^\s<\"']+，支持中文路径"
git push origin main
