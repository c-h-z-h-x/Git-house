import re, uuid

# 验证文件名生成
query = "打包线代资料"
safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in query)[:20].strip()
if not safe:
    safe = "docs"
unique_id = uuid.uuid4().hex[:8]
filename = f"{safe}_{unique_id}.zip"
print(f"查询词: {query}")
print(f"生成文件名: {filename}")

# 验证 JavaScript regex (Python re 模拟)
url = f"/download/{filename}"
pattern = r"/download/[^\s<\"']+"
match = re.search(pattern, url)
print(f"测试 URL: {url}")
print(f"regex 匹配: {'YES' if match else 'NO'}")
print(f"匹配内容: {match.group() if match else 'N/A'}")

# 验证 basename 安全
import posixpath
basename = posixpath.basename(filename)
print(f"basename 安全: {basename == filename}")

# 验证中文查询情形
queries = ["线代", "微积分A", "linear algebra", "人工智能导引", ""]
for q in queries:
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in q)[:20].strip()
    if not safe:
        safe = "docs"
    fn = f"{safe}_{uuid.uuid4().hex[:8]}.zip"
    url = f"/download/{fn}"
    match = re.search(pattern, url)
    print(f"  '{q}' -> {fn}  match={'YES' if match else 'NO'}")
