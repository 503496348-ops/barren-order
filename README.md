# 荒原序列 · BarrenOrder

让两个或多个Hermes Bot在同一个飞书群内通过互相@实现协作的完整解决方案。

## 典型场景

- **Bot A = 主持者**：战略/合规/方案/决策辅助
- **Bot B = 执行者**：信息采集/技术操作/文档整理
- **用户**在群里发指令，主持者接收后@执行者派发任务，执行者完成后@主持者汇报

## 快速开始

### 1. 下载技能包

克隆本仓库到本地：
```bash
git clone https://github.com/503496348-ops/barren-order.git
```

### 2. 配置

编辑 `references/配置模板.md`，填写：
- 群ID（Group ID）
- 每个Bot的名字和open_id
- 角色分配

### 3. 校验配置

```bash
python scripts/validate_config.py
```

### 4. 启动协作

在飞书群里测试通信：
```
<at user_id="ou_执行者open_id">执行者名字</at> 通信测试，请回复"收到"
```

## 目录结构

```
barren-order/
├── SKILL.md                      # 通用逻辑（Hermes技能文件）
├── references/
│   ├── 配置模板.md                 # ⚡ 用户填写自己的ID
│   ├── 消息格式规范.md             # @标签正确/错误写法
│   └── 故障排查清单.md             # 常见问题排查
└── scripts/
    ├── validate_config.py          # 配置校验脚本
    ├── message_router.py           # 优先级路由 + 断路器 + 上下文感知路由
    ├── workflow_engine.py          # ⭐ DAG工作流引擎（顺序/并行/条件分支）
    └── shared_memory.py            # ⭐ 多Agent共享记忆与上下文管理
```

## 核心原理

```
用户 → 飞书群 → Bot A（主持者）@Bot B（执行者） → Bot B处理 → @Bot A汇报 → 用户看到结果
```

## @标签唯一正确格式

```xml
<at user_id="ou_对方的open_id">对方名字</at> 消息内容
```

**⚠️ user_id必须是open_id（ou_开头），不是cli_会话ID！**

## 更多信息

详见 [SKILL.md](SKILL.md)

---

## ⭐ 新增能力（v1.1.0）

### 1. DAG工作流引擎 (`scripts/workflow_engine.py`)

对标 Dify/CrewAI 的核心编排能力：
- **顺序/并行执行**：任务自动按依赖拓扑排序，独立任务并行执行
- **条件分支**：基于上游输出的 `equals` / `contains` / `success` / `failed` 等条件路由
- **重试与超时**：每个任务可独立配置 `max_retries` / `timeout` / `retry_delay`
- **流式上下文传递**：任务输出自动注入 `shared context`，下游任务用 `{{task_xxx_output}}` 引用
- **状态持久化**：工作流执行状态可保存/恢复

```python
from scripts.workflow_engine import WorkflowBuilder, WorkflowExecutor

wf = (WorkflowBuilder("demo", "我的工作流")
    .add_task("step1", "研究", prompt="研究{{user_query}}", agent_id="researcher")
    .add_task("step2", "撰写", prompt="写报告", agent_id="writer", depends_on=["step1"])
    .build())

executor = WorkflowExecutor(wf)
result = executor.run(initial_context={"user_query": "AI趋势"})
```

内置模板：
- `create_research_report_workflow()` — 研究→撰写→审核流水线
- `create_parallel_analysis_workflow()` — 多Agent并行分析→综合

### 2. 共享Agent记忆 (`scripts/shared_memory.py`)

对标 CrewAI 的 memory 系统：
- **命名空间隔离**：`GLOBAL`（全局共享）/ `AGENT`（Agent私有）/ `SESSION` / `WORKFLOW`
- **TTL自动过期**：支持带过期时间的记忆条目
- **任务上下文**：`set_task_context()` / `get_task_context()` 在工作流任务间传递状态
- **对话历史**：按角色记录多Agent对话，支持 `get_conversation_summary()` 注入prompt
- **快照/恢复**：`create_snapshot()` / `restore_snapshot()` 实现检查点
- **全文搜索**：`memory.search("关键词")` 跨所有记忆条目检索
- **磁盘持久化**：自动/手动保存到JSON文件

```python
from scripts.shared_memory import SharedMemory, MemoryScope, AgentContextBuilder

memory = SharedMemory(persist_path=Path("memory.json"))
memory.set("user_query", "分析市场", scope=MemoryScope.GLOBAL)
memory.set_task_context("research_data", "...")

# 为特定Agent构建上下文
ctx = AgentContextBuilder(memory, "bot_a").build_context()
```

---



---

## 🚀 加入AtomCollide-AI智能体实验室

**元素碰撞-AtomCollide-AI 智能体实验室** 是一个专注于AI领域的开源组织，汇聚了众多优秀学习者。

### 核心价值

**找工作：更省力，也更精准**
- 一线大厂内推通道（字节、阿里、腾讯等）
- 全链路求职赋能包（面试题库、简历优化、晋升指导）
- 线下技术沙龙 & 人脉网络

**学AI测试：真正落地，拒绝空谈**
- 从0到1实战落地体系（Skills、MCP、RAG、AI IDE等）
- 独家自研资料与工具矩阵
- 前沿技术同步与提效方案

### 知识库

- [踩坑合集](https://vcnvmnln7wit.feishu.cn/wiki/CjV9wG8IHiIpWikCdFEcxfErnne)
- [商业化案例库](https://vcnvmnln7wit.feishu.cn/wiki/LdIxwlrKGibFEVkWMocc2K9KnBh)
- [科普专栏](https://vcnvmnln7wit.feishu.cn/wiki/K1RPwM8zji9ZchkxlOmcivUgnJe)
- [Open Build](https://vcnvmnln7wit.feishu.cn/wiki/CThswol0PiNJJbkhgT1cZIxanLb)
- [LLM/Agent/研究报告知识库](https://vcnvmnln7wit.feishu.cn/wiki/KwGQwS2TciT2EdkSBBtcYnbsnSd)
- [Skill封装合集](https://vcnvmnln7wit.feishu.cn/wiki/PDfpwqJZUibTyBkUa7TcZZ6Onpd)
- [社区治理运营知识库](https://vcnvmnln7wit.feishu.cn/wiki/MSEGwrdnTiiF9Dk8qCVcNW6InJg)

### 加入社群

| 社群 | 链接 |
|------|------|
| AI探索交流1区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=074vd565-6084-455c-ac52-9703e89a0697) |
| AI探索交流2区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=60bj94f0-1a67-48a7-abbb-9172b161c2b0) |
| AI探索交流3区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=13do1920-db46-4444-b635-005680beaf58) |
| AI探索交流4区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=f17o1b86-06f6-4f10-911a-69a299a25fe3) |
| AI探索交流5区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=2bbh6ab6-22c2-4753-b973-74bb1a2edcc9) |
| AI探索交流6区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=d19r19f7-2f47-42ba-b1ec-cb0342cf2e80) |
| AI探索交流7区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=fe9vdacc-7316-4b4d-ae4a-fdbcf56315e6) |
| AI探索交流8区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=103kfae8-1fd7-424f-984f-d66c210e42d1) |
| AI探索交流9区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=239p3cad-2f83-4baa-a230-f40386067548) |
| AI探索交流10区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=880r7cf5-3638-45ff-afb9-7944de991872) |
| AI探索交流-网文作家 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=6a3v579b-ab43-4e1a-87f9-be63bab88da7) |
| AI探索交流群-音乐达人 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=76at299e-73da-4eeb-9eba-32161e98f2f8) |
| AI探索交流群-微笑驿站 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=f2av73d0-6bb4-4a9f-9095-5fbbe83e49ec) |

---

*AtomCollide-智械工坊团队出品*

