import os
import re
import requests
import json
import subprocess
from fastapi import FastAPI

# 记忆文件路径（部署到 Render 后用 /tmp 目录，本地用桌面）
if os.environ.get("RENDER"):
    记忆路径 = "/tmp/memory.txt"
else:
    记忆路径 = os.path.join(os.path.expanduser("~"), "Desktop", "memory.txt")

app = FastAPI()
API_KEY = "sk-0e8783799096454caed38dd355b911b9"

def 调AI(提示词):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + API_KEY
    }
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": 提示词}],
        "max_tokens": 200
    }
    r = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=data)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"]
    else:
        return f"AI调用失败，状态码：{r.status_code}"

@app.post("/summarize")
def summarize(text: str):
    return {"summary": 调AI(text)}

@app.post("/count-folder")
def count_folder(folder_path: str):
    统计结果列表 = []
    for 文件名 in os.listdir(folder_path):
        if 文件名.endswith(".txt"):
            with open(os.path.join(folder_path, 文件名), "r", encoding="utf-8") as f:
                内容 = f.read()
            统计结果列表.append(f"{文件名}：{len(内容)}字，{len(内容.split(chr(10)))}行")
    结果 = "\n".join(统计结果列表)
    return {"folder": folder_path, "files_count": len(统计结果列表), "result": 结果}

@app.post("/agent-task")
def agent_task(task: str, folder_path: str = None):
    # 1. 读取历史记忆
    历史记忆 = ""
    if os.path.exists(记忆路径):
        with open(记忆路径, "r", encoding="utf-8") as f:
            历史记忆 = f.read()

    # 2. 工具列表
    工具列表_text = """
1. 总结文本：输入一段文字，返回一句话总结
2. 翻译文本：输入一段中文，返回英文翻译
3. 统计文件夹：输入文件夹路径，统计该文件夹里所有txt文件的字数和行数
4. 合并文件夹：输入文件夹路径，把该文件夹里所有txt文件合并成一个新文件
5. 写代码：输入一段需求描述，自动生成对应的 Python 脚本文件，保存到桌面，并自动运行它
"""

    # 3. 规划步骤
    规划提示词 = f"""你是一个任务规划助手。根据用户需求，判断该用哪个工具。
可用工具：{工具列表_text}
用户需求：{task}
请只回答工具名字，不要加任何解释。比如：写代码"""
    
    步骤计划 = 调AI(规划提示词).strip()
    
    # 4. 执行步骤
    中间结果 = {}
    执行记录 = []

    for line in 步骤计划.split("\n"):
        line = line.strip()
        if not line:
            continue

        if "总结文本" in line:
            待总结 = task.split("总结")[-1].strip("：:，,。 ") if "总结" in task else task
            待总结 = 中间结果.get("步骤1", 待总结)
            result = 调AI("用一句话总结：" + 待总结)
            中间结果["步骤1"] = result

        elif "翻译文本" in line:
            待翻译 = task
            if "刚才" in task or "上一次" in task or "上一轮" in task:
                for 行 in reversed(历史记忆.split("\n")):
                    if 行.startswith("结果："):
                        待翻译 = 行.replace("结果：", "").strip()
                        break
            result = 调AI("请把以下内容翻译成英文：" + 待翻译)

        elif "统计文件夹" in line:
            if not folder_path:
                return {"error": "需要提供 folder_path 参数"}
            统计结果列表 = []
            for 文件名 in os.listdir(folder_path):
                if 文件名.endswith(".txt"):
                    with open(os.path.join(folder_path, 文件名), "r", encoding="utf-8") as f:
                        内容 = f.read()
                    统计结果列表.append(f"{文件名}：{len(内容)}字，{len(内容.split(chr(10)))}行")
            result = "\n".join(统计结果列表)

        elif "合并文件夹" in line:
            if not folder_path:
                return {"error": "需要提供 folder_path 参数"}
            所有内容列表 = []
            for 文件名 in os.listdir(folder_path):
                if 文件名.endswith(".txt"):
                    with open(os.path.join(folder_path, 文件名), "r", encoding="utf-8") as f:
                        所有内容列表.append(f"=== {文件名} ===\n{f.read()}")
            result = "\n\n".join(所有内容列表)

        elif "写代码" in line:
            需求描述 = task.split("写代码")[-1].strip("：:，,。 ") if "写代码" in task else task
            路径匹配 = re.search(r'[A-Za-z]:[\\/][^\s，。]*', task)
            
            if 路径匹配:
                完整需求 = f"需求：{需求描述}\n在代码中直接使用文件夹路径：{路径匹配.group(0)}，不要使用input()。"
            else:
                完整需求 = f"需求：{需求描述}\n不要使用input()，所有参数通过变量直接定义。"

            代码 = 调AI("请严格按照要求输出Python代码，不要添加任何解释或说明。" + 完整需求)
            if "```" in 代码:
                代码 = 代码.replace("```python", "").replace("```", "").strip()

            # 根据环境选择保存路径（本地用桌面，Render 用 /tmp）
            if os.environ.get("RENDER"):
                保存路径 = "/tmp/generated_script.py"
            else:
                保存路径 = os.path.join(os.path.expanduser("~"), "Desktop", "generated_script.py")
            with open(保存路径, "w", encoding="utf-8") as f:
                f.write(代码)

            try:
                运行结果 = subprocess.run(["python", 保存路径], capture_output=True, text=True, timeout=10)
                if 运行结果.returncode == 0:
                    result = f"脚本已保存并运行成功。输出：\n{运行结果.stdout}"
                else:
                    result = f"脚本已保存但运行出错：\n{运行结果.stderr}"
            except subprocess.TimeoutExpired:
                result = "脚本运行超时（超过10秒），已自动终止。"

        else:
            result = f"未识别的工具：{line}"

        执行记录.append({"step": line, "result": result})

    # 5. 保存记忆
    本次记录 = f"任务：{task}\n结果：{执行记录[-1]['result'] if 执行记录 else '无'}\n---\n"
    with open(记忆路径, "a", encoding="utf-8") as f:
        f.write(本次记录)

    return {
        "task": task,
        "plan": 步骤计划,
        "execution": 执行记录
    }   
