# 技能使用指南

OpenGame 的三层技能系统：Template Skill（模板学习）→ Debug Skill（自动修复）→ GameSkill（5 阶段生成）。

---

## 架构总览

```
用户提示词
    │
    ▼
GameSkill（6-phase 编排器）
    │
    ├── Phase 1: 分类 + 脚手架  ──► 复制模板文件
    ├── Phase 2: GDD 生成       ──► LLM 生成设计文档
    ├── Phase 3: 资产生成       ──► AssetService（图片/音频/视频）
    ├── Phase 4: 配置注册       ──► 编辑 gameConfig.json/main.ts
    ├── Phase 5: 代码实现       ──► TurnLoop Agent（工具执行）
    └── Phase 6: 调试验证       ──► DebugSkill（Algorithm 1）
```

---

## Template Skill（模板库进化）

从已完成的游戏项目中"学习"可复用的代码模板。

### 核心流程

```
Collect（采集文件）
  → Classify（分类游戏类型）
    → Extract（提取代码模式）
      → Abstract（泛化为模板）
        → Merge（合并到模板库）
          → Save（持久化）
```

### CLI 使用

```bash
# 从成品游戏进化模板库
python -m opengame evolve ./path-to-completed-game

# 预览模式（不写入）
python -m opengame evolve ./path-to-completed-game --dry-run

# 指定模板库路径
python -m opengame evolve ./my-game --library ./my-templates
```

### 5 种游戏原型

| 原型 | 物理特征 | 典型游戏 |
|------|----------|----------|
| `platformer` | 有重力、侧视角、连续移动 | 马里奥、空洞骑士 |
| `top_down` | 无重力、俯视角、连续移动 | 塞尔达、弹幕射击 |
| `grid_logic` | 无重力、俯视角、网格离散移动 | 贪吃蛇、2048、扫雷 |
| `tower_defense` | 无重力、俯视角、路径移动 | 塔防、保卫萝卜 |
| `ui_heavy` | 无重力、无视角、纯 UI | 挂机、点击、经营 |

### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| ProjectCollector | `collector.py` | 遍历项目目录，收集源文件生成 ProjectSnapshot |
| Classifier | `classifier.py` | LLM 优先 + 关键词回落，识别原型 |
| PatternExtractor | `extractor.py` | 正则解析 TS 类/方法/钩子/导入/配置 |
| Abstractor | `abstractor.py` | LLM 驱动代码泛化 + 规则回落 |
| FamilyMerger | `merger.py` | 创建新 family 或合并到已有（含稳定性追踪） |
| LibraryManager | `library_manager.py` | JSON 持久化、CRUD、families 目录 |

---

## Debug Skill（自动调试修复）

Algorithm 1：REPEAT...UNTIL 循环，自动诊断和修复构建/测试错误。

### 算法流程

```
REPEAT:
    1. Pre-execution validation（协议规则检查）
    2. npm run build → 成功？
    3. npm test → 成功？
    4. IF 失败:
       a. Diagnose（3 层诊断：entry 评分 → rule 匹配 → LLM 分析）
       b. Repair（5 种修复：edit/shell/create/delete/config）
       c. Verify（重新运行失败阶段）
       d. Record to protocol
UNTIL 全部通过 OR max_iterations 达到
```

### CLI 使用

```bash
# 调试游戏项目
python -m opengame debug ./my-game

# 自动修复模式
python -m opengame debug ./my-game --auto-fix

# 限制迭代次数
python -m opengame debug ./my-game --max-iterations 10
```

### 核心组件

| 组件 | 职责 |
|------|------|
| ProtocolManager | 加载/保存/初始化 debug protocol JSON |
| ProjectValidator | 执行前验证检查（文件/配置/导入） |
| StageRunner | npm build/test/dev 执行 + TypeScript 错误解析 |
| ErrorDiagnoser | 3 层错误匹配（entry 评分 ≥10 → rule 查询 → LLM 分析） |
| ErrorRepairer | 5 种修复类型（edit: 搜索替换, shell: 命令执行, create: 新建文件, delete: 删除, config: stub） |
| OutcomeRecorder | 记录诊断结果到 protocol（新 entry 创建 + 匹配计数） |
| RuleGeneralizer | 重复 ≥3 次的错误泛化为预防规则 |

### Debug Protocol 数据流

```
构建失败
  → StageRunner 解析 TS 错误（TS2322, TS2339, MODULE_NOT_FOUND...）
  → ErrorDiagnoser 匹配 protocol entries（错误码 10pts + 消息模式 5pts + 文件上下文 3pts）
  → 匹配到：应用已知修复 / 未匹配：LLM 生成修复
  → StageRunner 重新运行 stage 验证修复
  → OutcomeRecorder 记录到 protocol（新 entry 或 增加计数）
  → 重复 3 次以上的错误 → RuleGeneralizer 泛化为预防规则
```

---

## Game Skill（6-phase 游戏生成）

完整的游戏生成编排器，接收自然语言提示词并输出可玩的游戏。

### 6 阶段详情

**Phase 1: 分类 + 脚手架**
- 关键词 + 物理信号分类（5 种原型）
- 复制 core 模板到输出目录
- 复制原型特定模块（src/）
- 复制文档模板

**Phase 2: GDD 生成**
- LLM 生成 6 段 Game Design Document：
  1. Game Overview（概述）
  2. Core Mechanics（核心机制）
  3. Level Design（关卡设计）
  4. Art and Audio（美术音频）
  5. Technical Specs（技术规格）
  6. Implementation Plan（实现计划）

**Phase 3: 资产生成**
- 从 GDD Section 4 解析资产规格
- 调用 AssetService 生成图片/音频/视频
- 单资产失败不阻塞 pipeline（fallback placeholder）
- 输出 `public/assets/asset-pack.json`

**Phase 4: 配置注册**
- 更新 `gameConfig.json`（标题、物理参数）
- 更新 `main.ts`（场景注册）
- 更新 `TitleScreen.ts`（游戏标题）

**Phase 5: 代码实现**
- 委托给 TurnLoop Agent（Phase 2 实现）
- Agent 使用 21 个工具读取/编辑/搜索/执行代码
- 3 层阅读策略：API 摘要 → 目标源码 → 模块手册

**Phase 6: 调试验证**
- 委托给 DebugSkill（Algorithm 1）
- 构建 → 测试 → 修复 → 重复
- 协议进化（错误模式 → 预防规则）

### CLI 使用

```bash
# 生成游戏
python -m opengame generate -p "Build a Snake clone with WASD controls"

# 指定输出目录和模型
python -m opengame generate -p "A platformer with double jump" \
    -o ./my-game -m deepseek-v4-pro
```

---

## 4 层上下文压缩系统

Agent 会话可能变得很长（数百条消息），TurnLoop 集成了 4 个压缩策略：

| 策略 | 触发条件 | 作用 |
|------|----------|------|
| **ChatCompression** | 历史超过 70% token 限制 | LLM 摘要为 XML `<state_snapshot>` |
| **ToolOutputSummarize** | 单输出 > 2000 字符 | LLM 压缩大型输出 |
| **ToolOutputTruncate** | 在追加到历史记录前 | 基于剩余 context window 硬截断 |
| **TokenLimitChecker** | 每轮 | 硬性 turn/token 天花板（95% 安全边际） |
