"""
ToolHub - unify tools from 3 sources:
1) native tools (src/tools) - highest priority
2) skills tools (src/skills) - middle priority
3) mcps tools (src/mcps) - lowest priority

Conflict resolution:
- global priority: tools > skills > mcps
- within same source: try faster/last-success candidate first
- if a candidate fails, fallback to next candidate (same source), then next source
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from loguru import logger
import asyncio
import random
import re


def _extract_capabilities_from_description(description: str, name: str) -> List[str]:
    """
    从工具描述和名称中自动提取能力标签。
    例如: "使用搜索引擎搜索网络信息" + name="search_web" -> ["search", "web", "research"]
    """
    if not description:
        description = ""
    text = (description + " " + name).lower()

    # 能力标签映射（关键词 -> 能力标签）
    capability_keywords = {
        "search": ["search", "搜索", "检索", "查找", "find", "query"],
        "web": ["web", "网络", "internet", "online"],
        "research": ["research", "研究", "调研", "investigate"],
        "calculate": ["calculate", "计算", "compute", "math", "数学", "算"],
        "time": ["time", "时间", "clock", "date", "日期", "now", "当前"],
        "weather": ["weather", "天气", "forecast", "预报", "climate", "气候"],
        "document": ["document", "文档", "file", "文件", "pdf", "docx", "xlsx"],
        "pdf": ["pdf", "portable document"],
        "extract": ["extract", "提取", "parse", "解析"],
        "analyze": ["analyze", "分析", "analysis", "summary", "总结"],
        "test": ["test", "测试", "testing", "automation", "自动化"],
        "webapp": ["webapp", "web app", "web application", "web应用"],
        "map": ["map", "地图", "location", "位置", "geography", "地理"],
        "history": ["history", "历史", "conversation", "对话", "previous", "之前"],
    }

    found = set()
    for cap, keywords in capability_keywords.items():
        if any(kw in text for kw in keywords):
            found.add(cap)

    # 如果没有匹配到，至少根据 name 推断一个基础标签
    if not found:
        name_lower = name.lower()
        if "search" in name_lower or "检索" in name_lower:
            found.add("search")
        elif "calc" in name_lower or "算" in name_lower:
            found.add("calculate")
        elif "time" in name_lower or "时间" in name_lower:
            found.add("time")
        elif "weather" in name_lower or "天气" in name_lower:
            found.add("weather")
        elif "pdf" in name_lower:
            found.update(["pdf", "document", "extract"])
        elif "test" in name_lower or "测试" in name_lower:
            found.add("test")

    return sorted(list(found))


@dataclass
class ToolCandidate:
    name: str
    source: str  # "tools" | "skills" | "mcps"
    tool: Any  # must have async execute(input_data) -> Dict[str, Any]
    priority: int  # lower is better
    meta: Dict[str, Any]
    # capabilities: List[str] - 功能标签，用于“功能相似工具”的并发选优
    # 例如: ["search", "web", "research"] 表示这是一个搜索类工具


class ToolHub:
    def __init__(self):
        self._candidates_by_name: Dict[str, List[ToolCandidate]] = {}
        # performance cache: name -> index of last successful candidate
        self._last_success_index: Dict[str, int] = {}
        # capability index: capability -> List[ToolCandidate] (for functional similarity matching)
        self._candidates_by_capability: Dict[str, List[ToolCandidate]] = {}
        # 并发安全锁（保护 _last_success_index 的更新）
        self._update_lock = asyncio.Lock()
        # 配置缓存（避免频繁读取配置）
        self._config_cache: Optional[Dict[str, Any]] = None
        self._config_cache_time: float = 0.0
        self._config_cache_ttl: float = 60.0  # 缓存60秒

    def register_candidate(self, candidate: ToolCandidate) -> None:
        arr = self._candidates_by_name.setdefault(candidate.name, [])
        arr.append(candidate)
        # stable sort by priority (tools>skills>mcps), keep insertion order otherwise
        arr.sort(key=lambda c: c.priority)
        logger.info(f"ToolHub registered: {candidate.name} from {candidate.source}")

        # 同时按能力标签索引（用于功能相似工具发现）
        capabilities = candidate.meta.get("capabilities") or []
        if isinstance(capabilities, list):
            for cap in capabilities:
                if isinstance(cap, str) and cap.strip():
                    cap_lower = cap.strip().lower()
                    self._candidates_by_capability.setdefault(cap_lower, []).append(candidate)

    def list_tools(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for name, cands in self._candidates_by_name.items():
            out.append({
                "name": name,
                "candidates": [{"source": c.source, "priority": c.priority, "meta": c.meta} for c in cands],
            })
        return out

    def has_tool(self, name: str) -> bool:
        return name in self._candidates_by_name and len(self._candidates_by_name[name]) > 0

    def find_by_capability(self, capability: str) -> List[ToolCandidate]:
        """
        根据能力标签查找所有功能相似的工具（不管名字是否相同）。
        例如: find_by_capability("search") 返回所有声明了 "search" 能力的工具。
        """
        cap_lower = capability.strip().lower()
        candidates = self._candidates_by_capability.get(cap_lower, [])
        # 去重（同一个工具可能被多个标签索引）
        seen = set()
        unique = []
        for cand in candidates:
            key = (cand.name, cand.source)
            if key not in seen:
                seen.add(key)
                unique.append(cand)
        return unique

    def _get_timeout_config(self) -> float:
        """获取超时配置（带缓存）"""
        import time
        current_time = time.time()
        
        # 检查缓存是否有效
        if (self._config_cache is not None and 
            current_time - self._config_cache_time < self._config_cache_ttl):
            return self._config_cache.get("timeout", 30.0)
        
        # 重新读取配置
        try:
            from src.config.config_loader import get_config
            config = get_config()
            tool_config = config.get_section("tools") or {}
            timeout = tool_config.get("timeout", 30.0)
            self._config_cache = {"timeout": timeout}
            self._config_cache_time = current_time
            return timeout
        except (ImportError, AttributeError):
            default_timeout = 30.0
            self._config_cache = {"timeout": default_timeout}
            self._config_cache_time = current_time
            return default_timeout

    async def _call_candidate(self, cand: ToolCandidate, input_data: Any, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        安全调用单个候选工具，统一结果结构。
        支持超时控制，防止工具执行时间过长。
        优化：添加性能监控和资源清理。
        """
        import time
        
        timeout = timeout or self._get_timeout_config()
        start_time = time.time()
        task: Optional[asyncio.Task] = None
        
        try:
            # 创建任务以便可以取消
            task = asyncio.create_task(cand.tool.execute(input_data))
            # 使用 asyncio.wait_for 实现超时控制
            result = await asyncio.wait_for(task, timeout=timeout)
            duration = time.time() - start_time
            
            # 记录性能指标
            try:
                from src.utils.metrics import get_metrics
                metrics = get_metrics()
                metrics.record_performance(f"tool_execution_{cand.name}", duration)
                metrics.record_performance(f"tool_execution_{cand.source}", duration)
            except (ImportError, AttributeError):
                pass  # 如果 metrics 不可用，忽略
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.warning(f"ToolHub candidate timeout ({timeout}s): {cand.name} from {cand.source}")
            
            # 尝试取消任务（如果仍在运行）
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # 记录错误和性能
            try:
                from src.utils.metrics import get_metrics
                metrics = get_metrics()
                metrics.record_error(f"ToolTimeout_{cand.name}", f"timeout after {timeout}s")
                metrics.record_performance(f"tool_execution_{cand.name}", duration)
            except (ImportError, AttributeError):
                pass
            
            return {"success": False, "error": f"tool_timeout_after_{timeout}s", "_meta": {"source": cand.source}}
        except asyncio.CancelledError:
            # 任务被取消（正常情况）
            duration = time.time() - start_time
            metrics = get_metrics()
            metrics.record_performance(f"tool_execution_{cand.name}", duration)
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.warning(f"ToolHub candidate exception: {cand.name} from {cand.source}: {e}")
            
            # 记录错误和性能
            try:
                from src.utils.metrics import get_metrics
                metrics = get_metrics()
                metrics.record_error(f"ToolException_{cand.name}", str(e))
                metrics.record_performance(f"tool_execution_{cand.name}", duration)
            except (ImportError, AttributeError):
                pass
            
            return {"success": False, "error": str(e), "_meta": {"source": cand.source}}

        if result is None:
            result = {"success": False, "error": "tool_returned_none"}
        elif not isinstance(result, dict):
            result = {"success": True, "result": result}

        # treat missing success as success=True for backwards compatibility
        if "success" not in result:
            result["success"] = True

        result.setdefault("_meta", {})
        result["_meta"].update({"source": cand.source})
        return result

    def _pick_best(self, results: Dict[int, Dict[str, Any]], cands: List[ToolCandidate]) -> Optional[int]:
        """
        从一批候选结果中挑选“最优”下标：
        - success=True
        - result 非空且长度尽量长
        - 同等条件下优先 priority 更高的候选
        """
        best_idx: Optional[int] = None
        best_score: float = -1.0

        for idx, res in results.items():
            if not res.get("success"):
                continue
            
            # 检查是否有明显错误标记
            error = res.get("error", "")
            if error and any(kw in error.lower() for kw in ["timeout", "failed", "exception", "error"]):
                continue
            
            val = res.get("result")
            text = ""
            if isinstance(val, str):
                text = val.strip()
            elif val is not None:
                text = str(val).strip()

            # 空结果或过短结果跳过
            if not text or len(text) < 3:
                continue

            # 质量评分（检查是否有结构化数据）
            quality_score = 0.0
            if isinstance(val, dict):
                quality_score = 0.2  # 结构化数据加分
                # 检查是否有有用的字段
                if any(k in val for k in ["results", "data", "content", "items"]):
                    quality_score = 0.3

            # 长度评分（优化：更智能的长度评估）
            if len(text) < 10:
                length_score = 0.3  # 过短结果降分
            elif len(text) <= 500:
                length_score = min(len(text), 500) / 500.0  # 0~1，理想长度
            elif len(text) <= 2000:
                length_score = 0.8 - (len(text) - 500) / 1500.0 * 0.3  # 逐渐降分
            else:
                length_score = 0.5 * (1.0 - min((len(text) - 2000) / 5000.0, 0.5))  # 过长结果大幅降分

            # 优先级评分
            priority_score = 1.0 / (1 + cands[idx].priority)  # tools(0) > skills(1) > mcps(2)
            
            # 综合评分（可配置权重，当前：长度50% + 质量20% + 优先级30%）
            score = 0.5 * length_score + 0.2 * quality_score + 0.3 * priority_score

            if score > best_score:
                best_score = score
                best_idx = idx

        return best_idx

    async def execute_by_capability(
        self, capability: str, input_data: Any, max_parallel: int = 3, llm_client = None
    ) -> Dict[str, Any]:
        """
        基于能力标签并发调用功能相似的工具（不管名字是否相同）。
        支持混合策略：根据工具类型和数量决定是选最优还是综合回答。
        """
        cands = self.find_by_capability(capability)
        if not cands:
            return {
                "success": False, 
                "error": f"no_tools_with_capability: {capability}",
                "suggestions": self._suggest_similar_capabilities(capability)
            }

        # 按 priority 排序，优先高优先级工具
        cands.sort(key=lambda c: c.priority)
        # 随机打乱同优先级内的顺序，增强鲁棒性
        grouped: Dict[int, List[ToolCandidate]] = {}
        for c in cands:
            grouped.setdefault(c.priority, []).append(c)
        sorted_cands = []
        for prio in sorted(grouped.keys()):
            group = grouped[prio]
            random.shuffle(group)
            sorted_cands.extend(group)

        # 决定策略：如果相似工具 <= 2，全部调用；否则根据工具类型决定
        num_tools = len(sorted_cands)
        should_synthesize = self._should_synthesize(capability, capability, num_tools)
        
        # 并发调用（如果应该综合，调用所有工具；否则最多 max_parallel 个）
        if should_synthesize and num_tools <= 2:
            # 全部调用
            batch_size = num_tools
        else:
            batch_size = min(max_parallel, len(sorted_cands))
        
        first_batch = sorted_cands[:batch_size]
        tasks = {i: asyncio.create_task(self._call_candidate(cand, input_data)) for i, cand in enumerate(first_batch)}
        
        # 根据策略决定等待方式
        if should_synthesize:
            # 综合策略：等待所有任务完成
            await asyncio.gather(*tasks.values(), return_exceptions=True)
            results: List[Dict[str, Any]] = []
            for i in range(batch_size):
                try:
                    res = tasks[i].result()
                    if isinstance(res, dict):
                        results.append(res)
                    else:
                        results.append({"success": False, "error": f"unexpected_result_type: {type(res)}"})
                except Exception as e:
                    logger.warning(f"ToolHub capability task {i} raised exception: {e}")
                    results.append({"success": False, "error": str(e)})
            
            # 综合所有成功的结果
            return await self._synthesize_results(results, capability, input_data, llm_client)
        else:
            # 选最优策略：第一个成功后立即取消其他任务
            try:
                done, pending = await asyncio.wait(
                    tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=None
                )
                
                # 检查是否有成功的结果
                results: Dict[int, Dict[str, Any]] = {}
                best_idx: Optional[int] = None
                
                for completed_task in done:
                    for i, task in tasks.items():
                        if task == completed_task:
                            try:
                                res = task.result()
                                if isinstance(res, dict):
                                    results[i] = res
                                    if res.get("success") and best_idx is None:
                                        best_idx = i
                                else:
                                    results[i] = {"success": False, "error": f"unexpected_result_type: {type(res)}"}
                            except Exception as e:
                                logger.warning(f"ToolHub capability task {i} raised exception: {e}")
                                results[i] = {"success": False, "error": str(e)}
                            break
                
                # 如果找到成功的结果，取消其他任务
                if best_idx is not None:
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    return results[best_idx]
                
                # 如果没有成功的结果，等待所有任务完成
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                    for pending_task in pending:
                        for i, task in tasks.items():
                            if task == pending_task:
                                try:
                                    res = task.result()
                                    if isinstance(res, dict):
                                        results[i] = res
                                    else:
                                        results[i] = {"success": False, "error": f"unexpected_result_type: {type(res)}"}
                                except Exception as e:
                                    logger.warning(f"ToolHub capability task {i} raised exception: {e}")
                                    results[i] = {"success": False, "error": str(e)}
                                break
                
                # 重新选优
                best_idx = self._pick_best(results, first_batch)
                if best_idx is not None:
                    return results[best_idx]
            finally:
                # 确保所有任务都被清理
                for task in tasks.values():
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass

        # 第一批失败，尝试剩余候选
        remaining = sorted_cands[batch_size:]
        all_errors: List[str] = []
        for cand in remaining:
            res = await self._call_candidate(cand, input_data)
            if res.get("success"):
                return res
            all_errors.append(f"{cand.name}({cand.source}): {res.get('error', 'unknown')}")

        return {
            "success": False, 
            "error": "all_capability_tools_failed", 
            "_meta": {"capability": capability, "errors": all_errors[:5]}
        }
    
    def _suggest_similar_capabilities(self, capability: str) -> List[str]:
        """建议相似的能力标签"""
        cap_lower = capability.lower()
        all_caps = set(self._candidates_by_capability.keys())
        
        # 简单的相似度匹配（包含关系）
        suggestions = [c for c in all_caps if cap_lower in c or c in cap_lower]
        return suggestions[:3]  # 最多返回3个建议

    def _should_synthesize(self, tool_name: str, capability: Optional[str] = None, num_tools: int = 1) -> bool:
        """
        判断是否应该综合多个工具的结果。
        
        规则：
        1. 如果相似工具 == 2，全部调用并综合
        2. 计算类工具 → 选最优（结果应该一致）
        3. 搜索类工具 → 综合回答（信息互补）
        4. 数据提取类工具 → 综合回答（多源验证）
        """
        # 单个工具不需要综合
        if num_tools <= 1:
            return False
        
        # 规则1: 如果相似工具 == 2，全部调用并综合
        if num_tools == 2:
            return True
        
        # 规则2-4: 根据工具类型决定
        name_lower = tool_name.lower()
        cap_lower = (capability or "").lower()
        
        # 计算类工具 → 选最优
        calc_keywords = ["calculate", "calc", "计算", "算", "math", "数学"]
        if any(kw in name_lower for kw in calc_keywords) or any(kw in cap_lower for kw in calc_keywords):
            return False
        
        # 搜索类工具 → 综合回答
        search_keywords = ["search", "搜索", "检索", "查找", "find", "query", "web", "网络"]
        if any(kw in name_lower for kw in search_keywords) or any(kw in cap_lower for kw in search_keywords):
            return True
        
        # 数据提取类工具 → 综合回答
        extract_keywords = ["extract", "提取", "parse", "解析", "pdf", "document", "文档", "xlsx", "docx"]
        if any(kw in name_lower for kw in extract_keywords) or any(kw in cap_lower for kw in extract_keywords):
            return True
        
        # 时间类工具 → 选最优（结果应该一致）
        time_keywords = ["time", "时间", "date", "日期"]
        if any(kw in name_lower for kw in time_keywords) or any(kw in cap_lower for kw in time_keywords):
            return False
        
        # 默认：如果有多个工具，综合回答（更安全）
        return num_tools > 1

    async def _synthesize_results(
        self, 
        results: List[Dict[str, Any]], 
        tool_name: str, 
        input_data: Any,
        llm_client = None
    ) -> Dict[str, Any]:
        """
        使用LLM综合多个工具的结果。
        
        Args:
            results: 多个工具的执行结果列表
            tool_name: 工具名称
            input_data: 原始输入
            llm_client: LLM客户端（可选，如果为None则尝试获取）
        
        Returns:
            综合后的结果
        """
        if not results:
            return {"success": False, "error": "no_results_to_synthesize"}
        
        # 如果只有一个结果，直接返回
        if len(results) == 1:
            return results[0]
        
        # 收集所有成功的结果
        successful_results = [r for r in results if r.get("success")]
        if not successful_results:
            # 所有结果都失败，返回第一个错误
            return results[0]
        
        # 如果只有一个成功的结果，直接返回
        if len(successful_results) == 1:
            return successful_results[0]
        
        # 准备综合提示词（智能截断以控制token消耗）
        # 根据工具类型和结果数量动态调整截断长度
        num_results = len(successful_results)
        # 如果结果太多或总长度过长，使用更激进的截断策略
        total_length_estimate = sum(len(str(r.get("result", ""))) for r in successful_results)
        
        # 定义截断策略
        if total_length_estimate > 2000 or num_results > 3:
            # 大量结果：每个结果最多200字符，直接使用简单合并
            logger.info(f"工具结果总长度 {total_length_estimate} 字符，{num_results} 个结果，使用简单合并策略")
            return self._simple_merge_results(successful_results)
        
        # 中等结果：根据工具类型智能截断
        results_text = []
        for i, res in enumerate(successful_results, 1):
            result_value = res.get("result", "")
            source = res.get("_meta", {}).get("source", "unknown")
            if isinstance(result_value, dict):
                result_str = str(result_value)
            else:
                result_str = str(result_value)
            
            # 根据工具类型和结果数量动态调整截断长度
            tool_name_lower = tool_name.lower()
            if "calculate" in tool_name_lower or "calc" in tool_name_lower:
                max_len = 100  # 计算类工具结果通常很短
            elif "search" in tool_name_lower or "web" in tool_name_lower:
                max_len = 300 if num_results <= 2 else 200  # 搜索类工具，结果多时更短
            elif "extract" in tool_name_lower or "pdf" in tool_name_lower:
                max_len = 300  # 数据提取类工具
            else:
                max_len = 250  # 默认
            
            truncated = result_str[:max_len]
            if len(result_str) > max_len:
                truncated += "...（已截断）"
            
            results_text.append(f"工具{i} ({source}):\n{truncated}")
        
        prompt = f"""你是一个信息综合专家。请综合以下多个工具的执行结果，生成一个准确、全面的答案。

原始查询: {str(input_data)[:200]}

工具执行结果:
{chr(10).join(results_text)}

要求:
1. 综合所有工具的结果，提取关键信息
2. 如果多个工具提供了相同的信息，可以合并
3. 如果工具结果有冲突，请指出并说明
4. 如果工具结果互补，请整合所有信息
5. 生成一个清晰、准确的综合答案

请直接给出综合后的答案，不要包含推理过程："""

        # 获取LLM客户端（严格模式：不允许在这里隐式创建并偷偷使用“默认基座模型”）
        # - 如果调用方没有显式传入 llm_client，则直接走降级合并，不触发任何LLM调用
        if llm_client is None:
            logger.info("未提供 llm_client，跳过LLM综合，使用简单文本合并")
            return self._simple_merge_results(successful_results)
        
        # 尝试使用LLM综合
        if llm_client:
            try:
                # 调用LLM综合结果（带超时控制）
                import asyncio
                if hasattr(llm_client, 'generate_async'):
                    synthesized = await asyncio.wait_for(
                        llm_client.generate_async(prompt),
                        timeout=10.0  # 10秒超时
                    )
                else:
                    loop = asyncio.get_event_loop()
                    if hasattr(asyncio, 'to_thread'):
                        synthesized = await asyncio.wait_for(
                            asyncio.to_thread(llm_client.generate, prompt),
                            timeout=10.0
                        )
                    else:
                        synthesized = await asyncio.wait_for(
                            loop.run_in_executor(None, lambda: llm_client.generate(prompt)),
                            timeout=10.0
                        )
                
                if synthesized and synthesized.strip():
                    return {
                        "success": True,
                        "result": synthesized.strip(),
                        "_meta": {
                            "synthesized": True,
                            "source_count": len(successful_results),
                            "sources": [r.get("_meta", {}).get("source", "unknown") for r in successful_results]
                        }
                    }
            except asyncio.TimeoutError:
                logger.warning("LLM综合结果超时，使用简单文本合并")
            except Exception as e:
                logger.warning(f"LLM综合结果失败: {e}，使用简单文本合并")
        
        # 降级：简单文本合并（不调用LLM）
        return self._simple_merge_results(successful_results)
    
    def _simple_merge_results(self, successful_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        简单文本合并（不调用LLM），用于降级策略。
        每个结果最多300字符，总长度控制在合理范围内。
        """
        logger.info(f"使用简单文本合并 {len(successful_results)} 个工具的结果")
        merged_parts = []
        for i, res in enumerate(successful_results, 1):
            result_value = res.get("result", "")
            source = res.get("_meta", {}).get("source", "unknown")
            if isinstance(result_value, dict):
                result_str = str(result_value)
            else:
                result_str = str(result_value)
            
            # 每个结果最多300字符
            truncated = result_str[:300]
            if len(result_str) > 300:
                truncated += "...（已截断）"
            
            merged_parts.append(f"[来源{i} ({source})]: {truncated}")
        
        merged_text = "\n\n".join(merged_parts)
        return {
            "success": True,
            "result": merged_text,
            "_meta": {
                "synthesized": True,
                "synthesis_method": "simple_merge",  # 标记为简单合并
                "source_count": len(successful_results),
                "sources": [r.get("_meta", {}).get("source", "unknown") for r in successful_results]
            }
        }

    async def execute(self, name: str, input_data: Any, llm_client=None) -> Dict[str, Any]:
        """
        Execute tool by name with fallback.
        - 对同名的多个候选工具（tools/skills/mcps），会优先对最多3个进行并发调用，
          从中选出“质量最优”的结果；
        - 如果并发批次全部失败，再对剩余候选按优先级顺序依次尝试。
        Returns a dict with at least {success: bool, ...}
        """
        cands = self._candidates_by_name.get(name) or []
        if not cands:
            return {"success": False, "error": f"tool_not_found: {name}"}

        # 单一候选保留原有顺序逻辑
        if len(cands) == 1:
            res = await self._call_candidate(cands[0], input_data)
            if res.get("success"):
                async with self._update_lock:
                    self._last_success_index[name] = 0
            return res

        # 决定策略
        should_synthesize = self._should_synthesize(name, None, len(cands))

        # 构造候选顺序：最近成功优先，然后按 priority
        base_order = list(range(len(cands)))
        base_order.sort(key=lambda i: cands[i].priority)
        start_idx = self._last_success_index.get(name)
        if start_idx is not None and 0 <= start_idx < len(cands):
            if start_idx in base_order:
                base_order.remove(start_idx)
            base_order.insert(0, start_idx)

        # 根据策略决定批次大小
        if should_synthesize and len(cands) <= 2:
            # 全部调用
            batch_size = len(cands)
        else:
            # 最多3个
            batch_size = min(3, len(base_order))
        
        first_batch = base_order[:batch_size]
        # 在同一 priority 层内轻微打乱，避免总是固定同一个
        random.shuffle(first_batch)

        tasks = {idx: asyncio.create_task(self._call_candidate(cands[idx], input_data)) for idx in first_batch}
        
        if should_synthesize:
            # 综合策略：等待所有任务完成
            await asyncio.gather(*tasks.values(), return_exceptions=True)
            results: List[Dict[str, Any]] = []
            for idx in first_batch:
                try:
                    res = tasks[idx].result()
                    if isinstance(res, dict):
                        results.append(res)
                    else:
                        results.append({"success": False, "error": f"unexpected_result_type: {type(res)}"})
                except Exception as e:
                    logger.warning(f"ToolHub parallel task {idx} raised exception: {e}")
                    results.append({"success": False, "error": str(e)})
            
            # 综合所有成功的结果
            synthesized = await self._synthesize_results(results, name, input_data, llm_client)
            if synthesized.get("success"):
                # 更新成功索引（使用第一个成功的工具）
                for i, res in enumerate(results):
                    if res.get("success"):
                        async with self._update_lock:
                            self._last_success_index[name] = first_batch[i]
                        break
            return synthesized
        else:
            # 选最优策略：第一个成功后立即取消其他任务
            try:
                done, pending = await asyncio.wait(
                    tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=None
                )
                
                # 检查是否有成功的结果
                parallel_results: Dict[int, Dict[str, Any]] = {}
                best_idx: Optional[int] = None
                
                for completed_task in done:
                    for idx, task in tasks.items():
                        if task == completed_task:
                            try:
                                res = task.result()
                                if isinstance(res, dict):
                                    parallel_results[idx] = res
                                    if res.get("success") and best_idx is None:
                                        best_idx = idx
                                else:
                                    parallel_results[idx] = {"success": False, "error": f"unexpected_result_type: {type(res)}"}
                            except Exception as e:
                                logger.warning(f"ToolHub parallel task {idx} raised exception: {e}")
                                parallel_results[idx] = {"success": False, "error": str(e)}
                            break
                
                # 如果找到成功的结果，取消其他任务
                if best_idx is not None:
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    
                    async with self._update_lock:
                        self._last_success_index[name] = best_idx
                    return parallel_results[best_idx]
                
                # 如果没有成功的结果，等待所有任务完成
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                    for pending_task in pending:
                        for idx, task in tasks.items():
                            if task == pending_task:
                                try:
                                    res = task.result()
                                    if isinstance(res, dict):
                                        parallel_results[idx] = res
                                    else:
                                        parallel_results[idx] = {"success": False, "error": f"unexpected_result_type: {type(res)}"}
                                except Exception as e:
                                    logger.warning(f"ToolHub parallel task {idx} raised exception: {e}")
                                    parallel_results[idx] = {"success": False, "error": str(e)}
                                break
                
                # 重新选优
                best_idx = self._pick_best(parallel_results, cands)
                if best_idx is not None:
                    async with self._update_lock:
                        self._last_success_index[name] = best_idx
                    return parallel_results[best_idx]
            finally:
                # 确保所有任务都被清理
                for task in tasks.values():
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass

        # 并发批次没有成功结果，对剩余候选按顺序依次尝试
        remaining = [i for i in base_order if i not in first_batch]
        all_errors: List[str] = []
        for idx in remaining:
            res = await self._call_candidate(cands[idx], input_data)
            if res.get("success"):
                async with self._update_lock:
                    self._last_success_index[name] = idx
                return res
            error_msg = str(res.get("error") or "tool_failed")
            all_errors.append(f"{cands[idx].source}: {error_msg}")
            logger.warning(f"ToolHub candidate failed: {name} from {cands[idx].source}: {error_msg}")

        return {
            "success": False, 
            "error": "all_candidates_failed", 
            "_meta": {"name": name, "errors": all_errors[:5]}  # 只保留前5个错误
        }

