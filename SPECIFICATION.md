# 项目规范与接口规格说明书

## 1. 代码与开发规范

### 1.1 Python代码风格

- **遵循PEP 8规范**: 使用4个空格缩进，行长度不超过100字符
- **类型提示**: 所有函数必须包含类型提示
- **文档字符串**: 所有公共函数和类必须包含Docstring
- **命名规范**:
  - 函数和变量：使用`snake_case`
  - 类名：使用`PascalCase`
  - 常量：使用`UPPER_SNAKE_CASE`
  - 私有成员：使用`_leading_underscore`

**示例**:
```python
from typing import Dict, Any, Optional

def process_question(question: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    处理用户问题
    
    Args:
        question: 用户问题文本
        context: 可选的上下文信息
    
    Returns:
        包含答案的字典
    """
    pass
```

### 1.2 日志规范（极其重要）

在PAI-LangStudio的Python节点中，必须使用结构化日志，便于在平台日志服务(SLS)中调试。

**日志格式**:
```python
import json
import time
from typing import Any, Optional

def log(step: str, message: str, data: Optional[Any] = None):
    """
    输出结构化日志
    
    Args:
        step: 步骤名称（如："planning", "tool_call", "normalization"）
        message: 日志消息
        data: 可选的附加数据
    """
    log_entry = {
        "timestamp": time.time(),
        "step": step,
        "message": message,
        "data": data
    }
    # 使用print输出，可在SLS中检索
    print(f"[AGENT_LOG] {json.dumps(log_entry, ensure_ascii=False)}")

# 使用示例
log("planning", "开始解析用户问题", {"question": user_question})
log("tool_call", "调用搜索工具", {"tool": "search_web", "query": "法国首都"})
log("normalization", "答案归一化完成", {"raw": "Answer: 巴黎", "normalized": "巴黎"})
```

**日志级别**:
- `INFO`: 正常流程信息
- `WARNING`: 警告信息（如工具调用失败但可恢复）
- `ERROR`: 错误信息（需要关注）
- `DEBUG`: 调试信息（详细步骤）

### 1.3 错误处理规范

- **统一异常处理**: 使用try-except捕获所有异常
- **错误日志**: 所有错误必须记录日志
- **错误返回**: 返回统一的错误格式

```python
def safe_execute(func, *args, **kwargs):
    """安全执行函数，统一错误处理"""
    try:
        return {"success": True, "result": func(*args, **kwargs)}
    except Exception as e:
        log("error", f"执行失败: {str(e)}", {"function": func.__name__})
        return {"success": False, "error": str(e)}
```

### 1.4 代码注释规范

- **函数注释**: 使用Google风格的Docstring
- **复杂逻辑**: 必须添加行内注释说明
- **TODO标记**: 使用`# TODO: 描述`标记待完成功能

## 2. API接口规格

### 2.1 请求规范 (Request)

#### 2.1.1 HTTP方法
- **方法**: `POST`
- **Content-Type**: `application/json`

#### 2.1.2 鉴权
- **Header**: `Authorization: Bearer <your_eas_token>`
- **Token获取**: 从PAI-EAS服务配置中获取

#### 2.1.3 请求体格式
```json
{
  "question": "法国首都在哪里？"
}
```

**字段说明**:
- `question` (string, required): 用户问题文本

#### 2.1.4 请求示例

**cURL**:
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "法国首都在哪里？"}' \
  https://your-endpoint.pai-eas.cn/api/v1/predict
```

**Python**:
```python
import requests

endpoint = "https://your-endpoint.pai-eas.cn/api/v1/predict"
token = "YOUR_TOKEN"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

data = {
    "question": "法国首都在哪里？"
}

response = requests.post(endpoint, headers=headers, json=data)
result = response.json()
```

### 2.2 响应规范 (Response)

#### 2.2.1 成功响应

**Content-Type**: 
- 流式: `text/event-stream`
- 非流式: `application/json`

**Body格式**:
```json
{
  "answer": "巴黎"
}
```

**字段说明**:
- `answer` (string, required): 最终答案
  - 文本答案：直接字符串，如`"巴黎"`
  - 数值答案：数字类型，如`140`（不要加引号）
  - 多实体答案：逗号分隔，如`"北京, 上海, 广州"`

#### 2.2.2 错误响应

```json
{
  "error": "错误描述信息",
  "code": "ERROR_CODE"
}
```

**常见错误码**:
- `INVALID_REQUEST`: 请求格式错误
- `AUTH_FAILED`: 鉴权失败
- `TIMEOUT`: 请求超时
- `INTERNAL_ERROR`: 内部错误

#### 2.2.3 响应示例

**成功响应**:
```json
{
  "answer": "巴黎"
}
```

**数值答案**:
```json
{
  "answer": 140
}
```

**多实体答案**:
```json
{
  "answer": "北京, 上海, 广州"
}
```

**错误响应**:
```json
{
  "error": "请求超时",
  "code": "TIMEOUT"
}
```

### 2.3 流式响应（如支持）

如果服务支持流式响应，格式如下：

```
data: {"answer": "巴"}
data: {"answer": "黎"}
data: {"answer": ""}
```

## 3. 测试与验证规范

### 3.1 单元测试规范

**测试文件命名**: `test_<module_name>.py`

**测试函数命名**: `test_<function_name>_<scenario>`

**示例**:
```python
import pytest
from src.utils.normalize import normalize_answer

def test_normalize_answer_basic():
    """测试基本答案归一化"""
    assert normalize_answer("Answer: 巴黎") == "巴黎"
    assert normalize_answer("  140  ") == "140"

def test_normalize_answer_multiple_entities():
    """测试多实体答案归一化"""
    result = normalize_answer("北京, 上海, 广州")
    assert result == "北京, 上海, 广州"

def test_normalize_answer_edge_cases():
    """测试边界情况"""
    assert normalize_answer("") == ""
    assert normalize_answer(None) == ""
```

### 3.2 集成测试规范

**测试流程**:
1. 准备测试数据（验证集题目）
2. 调用Agent处理每道题
3. 记录推理过程和结果
4. 计算正确率
5. 分析错误案例

**测试脚本**:
```python
def test_validation_set():
    """在验证集上测试"""
    test_cases = load_validation_set()
    results = []
    
    for case in test_cases:
        result = agent.process_task(case["question"])
        results.append({
            "question_id": case["id"],
            "question": case["question"],
            "expected": case["answer"],
            "actual": result["answer"],
            "correct": result["answer"] == case["answer"]
        })
    
    # 计算正确率
    correct_count = sum(1 for r in results if r["correct"])
    accuracy = correct_count / len(results)
    
    print(f"正确率: {accuracy:.2%}")
    return results
```

### 3.3 API测试规范

**测试清单**:
- [ ] 正常请求测试
- [ ] 鉴权测试（正确Token、错误Token、无Token）
- [ ] 请求格式测试（正确格式、错误格式）
- [ ] 超时测试
- [ ] 并发测试
- [ ] 错误处理测试

**测试脚本**:
```python
def test_api_endpoint():
    """测试API端点"""
    endpoint = "https://your-endpoint.pai-eas.cn/api/v1/predict"
    token = "YOUR_TOKEN"
    
    # 正常请求
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "测试问题"}
    )
    assert response.status_code == 200
    assert "answer" in response.json()
    
    # 错误Token测试
    response = requests.post(
        endpoint,
        headers={"Authorization": "Bearer wrong_token"},
        json={"question": "测试问题"}
    )
    assert response.status_code == 401
```

## 4. 合规性自查清单

### 4.1 技术合规性

**必须遵守**:
- [ ] ✅ 仅使用PAI Model Gallery或阿里云百炼提供的Qwen系列模型
- [ ] ✅ 禁止任何形式的模型微调或权重修改
- [ ] ✅ 禁止使用其他大模型（如GPT-4、Claude等）
- [ ] ✅ 禁止硬编码任何题目的答案或答案映射
- [ ] ✅ 禁止使用训练数据或验证集数据进行模型训练

**允许使用**:
- [x] ✅ 搜索引擎（SerpAPI、阿里云IQS等）
- [x] ✅ 计算工具、日期工具等辅助工具
- [x] ✅ 提示词工程和优化
- [x] ✅ 答案后处理和归一化

### 4.2 提交合规性

**提交前必查**:
- [ ] 代码中无硬编码答案
- [ ] 配置文件中无答案映射
- [ ] 提示词中无答案泄露
- [ ] 仅使用允许的模型
- [ ] 无模型微调痕迹
- [ ] EAS服务完全由提交的LangStudio项目部署
- [ ] 答案文件格式正确
- [ ] 所有文档完整

### 4.3 自查脚本

```python
def compliance_check():
    """合规性自查"""
    checks = {
        "no_hardcoded_answers": check_hardcoded_answers(),
        "only_qwen_models": check_model_usage(),
        "no_fine_tuning": check_fine_tuning(),
        "valid_api_format": check_api_format(),
    }
    
    all_passed = all(checks.values())
    
    if not all_passed:
        print("合规性检查失败:")
        for check, passed in checks.items():
            if not passed:
                print(f"  ✗ {check}")
    else:
        print("✓ 所有合规性检查通过")
    
    return all_passed
```

## 5. 数据格式规范

### 5.1 验证集答案文件格式

**文件格式**: JSONL (每行一个JSON对象)

**格式**:
```json
{"question_id": "1", "answer": "巴黎"}
{"question_id": "2", "answer": "140"}
{"question_id": "3", "answer": "北京, 上海, 广州"}
```

**字段说明**:
- `question_id` (string, required): 题目ID
- `answer` (string/number, required): 归一化后的答案

### 5.2 日志文件格式

**格式**: 每行一个JSON对象

**示例**:
```json
{"timestamp": 1706457600.0, "step": "planning", "message": "开始解析问题", "data": {"question": "..."}}
{"timestamp": 1706457601.0, "step": "tool_call", "message": "调用搜索工具", "data": {"tool": "search_web", "query": "..."}}
```

## 6. 性能规范

### 6.1 响应时间要求

- **单题处理时间**: < 30秒（目标：< 10秒）
- **API响应时间**: < 5秒（目标：< 2秒）

### 6.2 资源使用要求

- **内存使用**: < 4GB
- **CPU使用**: 合理范围内
- **API调用次数**: 尽量减少不必要的调用

### 6.3 并发要求

- **支持并发**: 至少支持5个并发请求
- **稳定性**: 长时间运行无内存泄漏

## 7. 文档规范

### 7.1 必需文档

- [ ] README.md - 项目说明和快速开始
- [ ] PROJECT_PLAN.md - 项目工程计划
- [ ] TECHNICAL_DESIGN.md - 技术设计文档
- [ ] SPECIFICATION.md - 本规范文档

### 7.2 文档要求

- **完整性**: 包含所有必要信息
- **清晰性**: 结构清晰，易于理解
- **可复现性**: 包含完整的复现步骤
- **示例代码**: 提供可运行的示例

## 8. 版本控制规范

### 8.1 Git提交规范

**提交信息格式**: `<type>: <description>`

**类型**:
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 其他

**示例**:
```
feat: 实现ReAct规划引擎
fix: 修复答案归一化函数中的数值处理bug
docs: 更新API使用示例
```

### 8.2 分支管理

- `main`: 主分支，稳定版本
- `develop`: 开发分支
- `feature/*`: 功能分支
- `fix/*`: 修复分支

## 9. 安全规范

### 9.1 敏感信息处理

- **API密钥**: 使用环境变量，不提交到代码库
- **Token**: 不在代码中硬编码
- **配置文件**: 敏感信息使用`.env`文件，并添加到`.gitignore`

### 9.2 输入验证

- **请求验证**: 验证所有输入参数
- **SQL注入防护**: 如使用数据库，防止SQL注入
- **XSS防护**: 如处理用户输入，防止XSS攻击

## 10. 监控与告警

### 10.1 监控指标

- API调用次数
- 响应时间
- 错误率
- 工具调用成功率

### 10.2 告警规则

- 错误率 > 10%: 发送告警
- 响应时间 > 30秒: 发送告警
- 服务不可用: 立即告警

---

**最后更新**: 2026-01-28
**规范版本**: 1.0.0
**适用范围**: 整个项目开发周期
