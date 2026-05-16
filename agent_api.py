from fastapi import FastAPI
import requests
import json
import os

app = FastAPI()

# 确保这里是你的真实 API Key
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
    summary = 调AI(text)  # 直接拿用户的输入作为提示词
    return {"summary": summary}
import os

@app.post("/count-folder")
def count_folder(folder_path: str):
    """统计指定文件夹里所有 txt 文件的字数和行数"""
    统计结果列表 = []
    
    for 文件名 in os.listdir(folder_path):
        if 文件名.endswith(".txt"):
            文件路径 = os.path.join(folder_path, 文件名)
            with open(文件路径, "r", encoding="utf-8") as f:
                内容 = f.read()
            字数 = len(内容)
            行数 = len(内容.split("\n"))
            统计结果列表.append(f"{文件名}：{字数}字，{行数}行")
    
    结果 = "\n".join(统计结果列表)
    return {"folder": folder_path, "files_count": len(统计结果列表), "result": 结果}
@app.post("/agent-task")
def agent_task(task: str, folder_path: str = None):
    """
    统一的 Agent 任务接口——支持多步推理。
    用户输入自然语言指令，Agent 自动规划并逐步执行。
    """
    # 1. 工具列表
    工具列表_text = """
1. 总结文本：输入一段文字，返回一句话总结
2. 统计字数：输入一段文字，返回字数和行数
3. 统计文件夹：输入文件夹路径，统计该文件夹里所有txt文件的字数和行数
4. 合并文件夹：输入文件夹路径，把该文件夹里所有txt文件合并成一个新文件
"""
    
    # 2. 让 DeepSeek 规划步骤
    规划提示词 = f"""你是一个任务规划助手。用户会给你一句需求，你把它拆成子任务。
可用工具：{工具列表_text}
用户需求：{task}

请按以下格式输出你的计划（只输出这个格式，不要加任何多余的话）：
步骤1：工具名，参数：xxx
步骤2：工具名，参数：xxx

如果有多个步骤，继续写步骤3、步骤4。注意：如果后续步骤需要用到前一步的结果，参数写'第1步的结果'。"""
    
    步骤计划 = 调AI(规划提示词).strip()
    
    # 3. 逐步执行
    中间结果 = {}
    执行记录 = []
    
    for line in 步骤计划.split("\n"):
        line = line.strip()
        if not line:
            continue
        
        # 判断当前步骤调用哪个工具
        if "总结文本" in line:
            待总结 = task.split("总结")[-1].strip("：:，,。 ") if "总结" in task else task
            if "第1步的结果" in line and "步骤1" in 中间结果:
                待总结 = 中间结果["步骤1"]
            result = 调AI("用一句话总结：" + 待总结)
            中间结果["步骤1"] = result
        
        elif "统计字数" in line:
            待统计 = task
            result = f"字数：{len(待统计)}，行数：{len(待统计.split(chr(10)))}"
        
        elif "统计文件夹" in line:
            if not folder_path:
                return {"error": "需要提供 folder_path 参数"}
            统计结果列表 = []
            for 文件名 in os.listdir(folder_path):
                if 文件名.endswith(".txt"):
                    文件路径 = os.path.join(folder_path, 文件名)
                    with open(文件路径, "r", encoding="utf-8") as f:
                        内容 = f.read()
                    统计结果列表.append(f"{文件名}：{len(内容)}字，{len(内容.split(chr(10)))}行")
            result = "\n".join(统计结果列表)
            if "步骤1" not in 中间结果:
                中间结果["步骤1"] = result
            else:
                中间结果["步骤2"] = result
        
        elif "合并文件夹" in line:
            if not folder_path:
                return {"error": "需要提供 folder_path 参数"}
            所有内容列表 = []
            for 文件名 in os.listdir(folder_path):
                if 文件名.endswith(".txt"):
                    文件路径 = os.path.join(folder_path, 文件名)
                    with open(文件路径, "r", encoding="utf-8") as f:
                        所有内容列表.append(f"=== {文件名} ===\n{f.read()}")
            result = "\n\n".join(所有内容列表)
            if "步骤1" not in 中间结果:
                中间结果["步骤1"] = result
            else:
                中间结果["步骤2"] = result
        
        else:
            result = f"未识别的工具：{line}"
        
        执行记录.append({"step": line, "result": result})
    
    return {
        "task": task,
        "plan": 步骤计划,
        "execution": 执行记录
    }