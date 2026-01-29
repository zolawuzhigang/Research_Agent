"""
根据比赛要求，读取项目根目录下的 question.jsonl，
调用 AgentOrchestrator 逐题生成答案，并输出提交用 JSONL：

{"id": 0, "answer": "answer_1"}
{"id": 1, "answer": "answer_2"}
...
"""

import asyncio
import json
from pathlib import Path
import sys
from typing import List, Dict, Any

from loguru import logger

# 把项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.python_version import check_python_version  # noqa: E402
check_python_version()

from src.agent import AgentOrchestrator  # noqa: E402


async def run_once(agent: AgentOrchestrator, q: Dict[str, Any]) -> Dict[str, Any]:
    """对单个问题调用 Agent 并返回 {id, answer} 结构。"""
    qid = q.get("id")
    question = q.get("Question") or q.get("question") or ""
    question_str = str(question)

    if not question_str.strip():
        logger.warning(f"问题 {qid} 为空，返回空答案")
        return {"id": qid, "answer": ""}

    logger.info(f"开始处理问题 id={qid}")
    try:
        result = await agent.process_task(question_str)
    except Exception as e:
        logger.error(f"处理问题 id={qid} 时出错: {e}")
        # 比赛提交文件必须有答案字段，这里给出一个占位答案
        return {"id": qid, "answer": ""}

    # 从结果中提取 answer 字段；如果没有，则降级为空字符串
    answer = ""
    if isinstance(result, dict):
        answer = str(result.get("answer") or "").strip()

    if not answer:
        logger.warning(f"问题 id={qid} 未生成有效答案，使用空字符串占位")

    return {"id": qid, "answer": answer}


async def main(
    input_path: Path = Path("question.jsonl"),
    output_path: Path = Path("submission.jsonl"),
) -> None:
    """主入口：读取 JSONL，逐题调用 Agent，写出提交文件。"""
    if not input_path.exists():
        raise FileNotFoundError(f"找不到题目文件: {input_path}")

    logger.info(f"读取测试集: {input_path}")
    questions: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            questions.append(json.loads(line))

    logger.info(f"共读取 {len(questions)} 道题目")

    # 初始化 Agent（使用现有配置，多 Agent 模式）
    agent = AgentOrchestrator(use_multi_agent=True)

    results: List[Dict[str, Any]] = []
    for idx, q in enumerate(questions):
        logger.info(f"===== 处理第 {idx + 1}/{len(questions)} 题 =====")
        res = await run_once(agent, q)
        results.append(res)

    logger.info(f"写出提交文件: {output_path}")
    with output_path.open("w", encoding="utf-8") as f:
        for item in results:
            # 按比赛要求：每行一个 json，包含 id 和 answer 字段
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    logger.info("生成提交文件完成")


if __name__ == "__main__":
    asyncio.run(main())

