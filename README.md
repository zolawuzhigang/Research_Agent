# Research Agent - 天池大赛项目

## 项目简介

本项目是参加阿里云"用PAI-LangStudio实现Research Agent"竞赛（赛题ID: 532449）的完整解决方案。目标是构建一个基于Qwen系列模型、能够自主规划任务、调用外部工具并整合多源证据的智能体，在GAIA基准测试上取得前10名的成绩。

**竞赛链接**: https://tianchi.aliyun.com/competition/entrance/532449/customize818

## 核心特性

- 🤖 **智能规划**: 采用ReAct框架，能够自主分解复杂问题并制定执行计划
- 🔍 **工具调用**: 集成搜索引擎等多种工具，获取实时信息
- 🎯 **高准确率**: 通过多轮优化，在验证集上达到高正确率
- 📦 **完整部署**: 支持PAI-EAS一键部署，提供稳定API服务
- 📝 **规范文档**: 包含完整的技术文档和规范说明

## 技术架构

```
用户问题
  ↓
HTTP输入节点
  ↓
ReAct规划引擎 (Python节点)
  ↓
工具调用循环 (搜索/计算等)
  ↓
答案合成器
  ↓
答案归一化处理器
  ↓
HTTP输出节点
  ↓
最终答案
```

## 快速开始

### 前置要求

1. **Python 3.13.9**：本项目强制使用 Python 3.13.9，避免多解释器导致依赖不一致。详见 [PYTHON_VERSION.md](PYTHON_VERSION.md)。运行脚本时请使用 `python3.13` 或 `py -3.13`，或创建 3.13.9 虚拟环境。
2. **阿里云账号**: 需要开通PAI-LangStudio和PAI-EAS服务
3. **免费试用**: 领取PAI-DSW和PAI-EAS的免费试用权益
4. **API密钥**: 准备SerpAPI密钥（或其他搜索引擎API）

### 安装步骤

#### 1. 导入项目到PAI-LangStudio

1. 登录 [PAI-LangStudio控制台](https://pai.console.aliyun.com/)
2. 创建新应用
3. 导入本项目ZIP包（`research_agent_project.zip`）

#### 2. 配置环境变量

在LangStudio项目中配置以下环境变量：

```bash
# 模型配置
DASHSCOPE_API_KEY=your_dashscope_api_key

# 搜索工具配置
SERPAPI_KEY=your_serpapi_key

# 其他配置
LOG_LEVEL=INFO
```

#### 3. 配置模型节点

1. 在工作流中添加"LLM调用"节点
2. 选择Qwen系列模型（推荐：qwen-max）
3. 配置模型参数：
   - Temperature: 0.1（低随机性）
   - Max Tokens: 2000

#### 4. 配置工具节点

1. 添加"HTTP请求"节点用于搜索
2. 配置SerpAPI或其他搜索引擎
3. 测试工具调用是否正常

#### 5. 测试工作流

1. 使用测试数据运行工作流
2. 检查每个节点的输出
3. 验证最终答案格式

### 部署到PAI-EAS

1. 在LangStudio中点击"一键部署"
2. 选择PAI-EAS服务
3. 配置服务参数（实例规格、并发数等）
4. 等待部署完成
5. 获取Endpoint和Token

## API使用示例

### 请求格式

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "法国首都在哪里？"}' \
  https://your-endpoint.pai-eas.cn/api/v1/predict
```

### 响应格式

```json
{
  "answer": "巴黎"
}
```

### Python示例

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
print(result["answer"])
```

## 项目结构

```
ailiyunAgent/
├── README.md                    # 项目说明（本文件）
├── PROJECT_PLAN.md              # 项目工程计划
├── TECHNICAL_DESIGN.md          # 技术设计文档
├── SPECIFICATION.md             # 项目规范文档
├── requirements.txt             # Python依赖（本地开发用）
├── config/                      # 配置文件
│   └── config.yaml
├── src/                         # 源代码（本地开发用）
│   ├── agent/                   # Agent核心模块
│   ├── tools/                   # 工具模块
│   └── utils/                   # 工具函数
├── scripts/                     # 脚本文件
│   ├── setup_env.py
│   └── evaluate.py
├── docs/                        # 文档目录
│   ├── DEVELOPMENT_PLAN.md
│   ├── PHASES_DETAILED.md
│   └── TECHNICAL_ARCHITECTURE.md
└── data/                        # 数据目录
    ├── train/
    ├── test/
    └── processed/
```

## 核心模块说明

### 1. ReAct规划引擎

采用ReAct（Reasoning + Acting）框架，引导模型进行逐步思考并决定何时调用工具。

**工作流程**:
1. **思考**: 分析问题本质，确定需要的信息
2. **行动**: 调用工具（如搜索）
3. **观察**: 分析工具返回结果
4. 重复上述步骤，直到可以给出准确答案
5. **最终回答**: 输出简洁的最终答案

### 2. 工具集成

- **搜索引擎**: SerpAPI或阿里云IQS
- **计算工具**: 处理数学计算问题
- **日期工具**: 处理日期计算问题
- **单位换算**: 处理单位转换问题

### 3. 答案归一化

将模型输出的原始答案处理成符合赛题评分标准的格式：
- 转为小写
- 去除首尾空格
- 处理数值格式
- 规范多实体分隔符

## 开发指南

### 本地开发

1. 克隆项目
```bash
git clone <repository-url>
cd ailiyunAgent
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，填入API密钥
```

4. 运行测试
```bash
python scripts/evaluate.py
```

### 在PAI-LangStudio中开发

1. 在LangStudio中创建新应用
2. 使用工作流模式或代码模式开发
3. 参考`TECHNICAL_DESIGN.md`中的代码示例
4. 使用测试数据验证功能

## 性能优化

### 提示词优化
- 改进ReAct模板，提高推理质量
- 添加few-shot示例
- 优化工具调用指令

### 工具策略优化
- 优化搜索词提取
- 改进工具选择逻辑
- 增加结果过滤机制

### 答案处理优化
- 改进归一化函数
- 增加答案验证
- 处理边界情况

## 测试与验证

### 单元测试
```bash
pytest tests/
```

### 验证集测试
```bash
python scripts/evaluate.py --validation-set
```

### API测试
```bash
python scripts/test_api.py --endpoint YOUR_ENDPOINT --token YOUR_TOKEN
```

## 常见问题

### Q: 如何提高正确率？
A: 1) 优化提示词，特别是ReAct模板；2) 改进工具调用策略；3) 增强答案归一化处理；4) 分析错误案例，针对性改进。

### Q: 部署失败怎么办？
A: 1) 检查EAS服务配额；2) 检查工作流配置；3) 查看部署日志；4) 联系阿里云技术支持。

### Q: 如何调试工作流？
A: 1) 使用LangStudio的日志功能；2) 在每个节点添加print输出；3) 使用测试数据逐步验证；4) 查看SLS日志。

## 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

本项目仅用于天池竞赛，请遵守竞赛规则。

## 相关文档

- [项目工程计划](./PROJECT_PLAN.md) - 详细的开发计划和里程碑
- [技术设计文档](./TECHNICAL_DESIGN.md) - 系统架构和实现细节
- [项目规范文档](./SPECIFICATION.md) - 代码规范和API规格

## 联系方式

- **赛题支持**: 通过天池平台论坛
- **技术问题**: 参考阿里云文档中心
- **项目问题**: 在项目Issue中提出

---

**最后更新**: 2026-01-28
**项目版本**: 1.0.0
**竞赛状态**: 进行中
