# 智服通 Zhifutong

基于 **LLM 意图规划 + YAML 流程编排** 的电商智能客服助手。后端以 FastAPI 提供对话接口，通过大模型将用户消息规划为结构化 TurnPlan，由流程引擎确定性执行业务流程，支持多轮对话、任务中断恢复、对象消息与历史会话。

## 功能特性

- **多轮任务处理**：支持查订单、查物流、退款申请、相似商品推荐、转人工等电商客服流程，任务跨轮次续跑
- **LLM 意图规划**：大模型将每条消息规划为 `task` / `knowledge` / `chitchat` 三轨道的结构化 TurnPlan，规划结果经校验器校验后才执行
- **YAML 流程编排**：业务流程（步骤、槽位、条件分支、话术模板）全部声明在 `flow_config/user_flows.yml` 中，改业务不改代码
- **Action 插件机制**：订单查询、物流查询、商品推荐等外部接口调用封装为 Action，由 FlowExecutor 确定性执行，结果写回槽位
- **任务中断与恢复**：退款途中可以切去查物流，再说「继续刚才的」即可从上次中断的步骤恢复
- **对象消息处理**：前端点击订单/商品卡片后，后端自动聚焦该对象并填充对应槽位
- **历史会话**：完整对话按 Session/Turn 结构持久化，提供历史查询接口；会话超时自动切段并隔离上下文

## 内置业务流程

| Flow                             | 说明              |
| -------------------------------- | --------------- |
| `onboarding`                     | 欢迎引导，介绍可处理的电商服务 |
| `order_status_query`             | 查询订单状态          |
| `logistics_tracking`             | 查询物流进度          |
| `refund_request`                 | 退款申请            |
| `similar_product_recommendation` | 相似商品推荐          |
| `human_handoff`                  | 转人工             |

## 整体架构

```
用户消息 (POST /api/chat)
    │
    ▼
DialogueService ──► 按 sender_id 加载 DialogueState（MySQL）
    │
    ▼
DialogueEngine ──── 准备 Session / Turn
    │
    ▼
TurnPlanner (LLM) ─ 输出结构化 TurnPlan
    │
    ▼
TurnPlanValidator ─ 校验规划合法性，不合法走澄清
    │
    ├── task ──────► TaskHandler ──► FlowExecutor
    │                                  ├── CollectSlotStep  收集槽位（缺槽则提问等待）
    │                                  ├── ActionFlowStep   调用 Action 查询外部接口
    │                                  └── ResponseFlowStep 渲染模板回复
    ├── knowledge ─► KnowledgeHandler（知识咨询）
    └── chitchat ──► ChitChatHandler（闲聊）
    │
    ▼
Turn 写回当前 Session，DialogueState 整体持久化
```

## 核心设计

### 多轮对话状态

每个用户对应一份 `DialogueState` 聚合根，包含：

- `sessions / turns`：完整对话历史，60 分钟不活跃自动切段
- `task_state`：当前任务（`flow_id / step_id / slots`）与被中断的任务栈
- `focused_object`：当前聚焦的订单/商品对象

每条消息「加载状态 → 处理 → 整体写回」，任务从持久化的 `step_id` 和 `slots` 确定性续跑，不依赖 LLM 记忆或前端传上下文。

### LLM 只规划，程序来执行

LLM 不直接决定调用哪个工具、也不自由生成回复。它只输出结构化 TurnPlan；流程推进、工具调用、话术渲染全部由代码确定性完成，调用路径可预测、可单测，避免 function calling 带来的参数编造风险。

### Action 机制

自定义 Action 只需继承 `Action` 基类实现 `run()` 并注册到 `ActionRegistry`，即可在 YAML 流程中通过 `ActionFlowStep` 引用。Action 的输入从槽位读取，输出以 `slot_updates` 写回槽位，供后续步骤与响应模板使用。

## 技术栈

| 类别     | 技术                                           |
| ------ | -------------------------------------------- |
| Web 框架 | FastAPI + Uvicorn                            |
| LLM    | LangChain + langchain-openai（JSON 结构化输出）     |
| 状态持久化  | MySQL + SQLAlchemy 2.0（Async，整体 JSON upsert） |
| 流程编排   | PyYAML 声明式流程配置 + 自研 FlowExecutor             |
| 外部调用   | httpx（异步调用商城 API）                            |
| 模板渲染   | Jinja2                                       |

## 快速开始

环境要求：Python 3.11+，MySQL

1. 安装依赖（项目使用 [uv](https://docs.astral.sh/uv/) 管理）：

```bash
uv sync
```

1. 在项目根目录创建 `.env`：

```dotenv
LLM_API_KEY=你的大模型APIKey
LLM_MODEL=模型名称
LLM_BASE_URL=大模型接口地址
DATABASE_URL=mysql+aiomysql://用户名:密码@localhost:3306/数据库名
COMMERCE_API_BASE_URL=商城接口地址
APP_HOST=127.0.0.1
APP_PORT=8000
```

1. 启动服务：

```bash
uv run main.py
```

1. 对话接口：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"sender_id": "user_1", "type": "text", "text": "帮我查一下订单状态"}'
```

| 接口                  | 方法   | 说明             |
| ------------------- | ---- | -------------- |
| `/api/chat`         | POST | 发送用户消息，返回机器人回复 |
| `/api/chat/history` | GET  | 查询历史会话消息       |

## 目录结构

```
customer-service-0226
├── main.py                     # 启动入口
├── flow_config/
│   └── user_flows.yml          # 槽位与业务流程声明
├── zhifutong/
│   ├── app/                    # FastAPI 应用与聊天接口
│   ├── domain/                 # 领域模型：DialogueState / Session / Turn
│   ├── engine/                 # DialogueEngine 调度中心
│   ├── plan/                   # TurnPlanner 规划器与校验器
│   ├── task/                   # 任务轨道：流程执行、Action 机制、命令处理
│   ├── knowledge/              # 知识咨询轨道
│   ├── chitchat/               # 闲聊轨道
│   ├── clarify/                # 澄清回复
│   ├── prompts/                # Jinja2 提示词模板
│   ├── repository/             # DialogueState 持久化
│   ├── clients/                # LLM / 数据库 / HTTP 客户端
│   └── conf/                   # 配置加载
└── test/                       # 测试
```

## License

MIT
