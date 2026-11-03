2026-11-03 22:14｜执行器：ChatGPT｜当前阶段：①数据准备—微观数据库图谱索引与检索验收

# StataGraph V0.2.2 — 全部微观数据库元数据索引与检索验收

TASK_ID: STG_DATABASE_GRAPH_LOCAL_METADATA_SMOKE_20261103
TASK_REVISION: 2
STATUS: READY_FOR_OPENCODE
AUTHOR: ChatGPT
EXECUTOR: OpenCode
NEXT_ACTOR: ChatGPT
AUTOMATION_READY: NO
ATTEMPT: 1
MAX_ATTEMPTS: 1

## 一、唯一目标

使用已经实现的 StataGraph V0.2.2，对中央数据控制仓库中的全部 dataset catalog / metadata 建立本地数据库图谱，并验证 AI 能否通过数据集名称、文件名、英文变量名和中文变量标签定位目标。

本轮重点不是重新整理原始数据，而是验证现有元数据图谱的覆盖率、检索能力、来源追溯和 Registry 路径门禁。

## 二、研究范围

索引范围：`catalog/datasets.csv` 中全部数据集，不得只索引 CFPS、CHFS、CSMAR 三个示例。

优先检查以下微观数据库：

- 家庭/个人调查：CFPS、CHFS、CHARLS、CGSS、CLDS、CHIPS、TFCF、Hurun；
- 企业/上市公司微观数据：CSMAR、上市公司招聘、上市公司人员分布、企业劳动收入等；
- 其他 catalog 数据集也应进入数据库目录索引，但不得因本任务扩大到原始数据内容分析。

现有 metadata_summary.csv 中的主要调查数据库参考规模（这些是 metadata 行数，不是去重后的变量数）：

| 数据库 | 文件数 | DTA文件数 | 变量/表头元数据行 |
|---|---:|---:|---:|
| CFPS | 52 | 34 | 19,101 |
| CHFS | 142 | 46 | 31,038 |
| CHARLS | 26 | 19 | 8,392 |
| CGSS | 315 | 31 | 22,072 |
| CLDS | 93 | 31 | 38,133 |
| CHIPS | 226 | 114 | 9,770 |
| TFCF | 9 | 0 | 1,187 |
| CSMAR | 4,535 | 537 | 17,766 |
| Hurun | 49 | 0 | 0 |

以上仅作覆盖核对基准；实际输出必须以当前控制仓库文件为准。不得把 metadata 行数写成唯一变量数量。

## 三、固定输入与允许读取范围

- StataGraph：当前仓库根目录。
- 数据控制仓库：`C:\Users\admin\Documents\data-control`。
- 只允许读取：
  - `catalog/datasets.csv`
  - `catalog/data_registry.csv`
  - `metadata/<dataset>/files.csv`
  - `metadata/<dataset>/variables.csv`
  - 必要时读取对应 metadata README 解释字段覆盖情况。

不读取 `C:\Users\admin\Documents\data` 下的原始微观数据。

## 四、执行步骤

1. 确认 StataGraph 当前代码版本包含 V0.2.2 database graph 功能；不得自行改写索引器或搜索算法。
2. 检查固定的 data-control 路径存在。
3. 在 data-control 中记录 `git status --short` 与 HEAD。若有任何未提交改动，立即 BLOCKED，禁止覆盖或清理。
4. 仅在 data-control 控制仓库执行 `git pull --ff-only`，记录同步前后 HEAD。禁止在 data 本体目录执行 Git 操作。
5. 在 StataGraph 仓库执行：
   - `python -m pip install -e .`
   - `statagraph index-databases "C:\Users\admin\Documents\data-control"`
6. 检查本地缓存 `.statagraph/database_index.json`，记录：
   - 数据集总数；
   - 文件记录数；
   - 变量记录数；
   - documentation entries；
   - unparsed variable rows；
   - 实际读取的 metadata 文件数；
   - VERIFIED / 非 VERIFIED 数据集数。
7. 对比 `metadata_summary.csv` 和各数据库 README，核对文件数、DTA 数、变量元数据行数。差异必须报告，不得为了对齐而改 metadata。
8. 对全部数据集执行目录检索；对以下数据库执行 profile：
   - CFPS、CHFS、CHARLS、CGSS、CLDS、CHIPS、TFCF、Hurun、CSMAR。
9. 执行变量检索测试，至少覆盖：
   - CFPS：家庭收入、个人收入、教育、就业、个人ID；
   - CHFS：家庭收入、净资产、负债、消费、hhid；
   - CHARLS：收入、健康、就业、养老金；
   - CGSS：收入、教育、就业；
   - CLDS：工资、就业、行业、家庭；
   - CHIPS：收入、工资、家庭；
   - TFCF：收入、家庭；
   - CSMAR：Stkcd、fyear、资产、员工。
10. 对每个检索结果保留数据集、文件相对路径、变量名、变量标签、存储类型、原始格式、metadata 来源文件和行号、Registry 状态。
11. 检查路径门禁：
   - 只有 `verification_status=VERIFIED` 且 canonical path 非空的数据集允许出现 `local_path_relative`；
   - BLOCKED、REVIEW、UNRESOLVED、NOT_REGISTERED 等状态不得暴露可用本地路径。
12. 检查 StataGraph 生成的 `.statagraph/database_index.json` 被 Git ignore；再次执行 data-control 的 `git status --short`，确保 tracked 文件无变化。

## 五、检索质量判断

本轮只评价当前 V0.2.2 已实现的字面/标签检索，不得声称已经实现语义搜索。

重点报告：

- 中文标签能否检索；
- 英文变量名能否检索；
- 中文标签缺失的数据库/文件占比；
- 同名变量是否出现在多个波次或文件；
- 是否能区分变量名相同但文件/波次不同的记录；
- 文件路径年份只能作为 discovery hint，不得直接当作正式调查波次；
- 相似变量名或标签不能证明定义、单位、调查对象和统计范围可比。

如某个查询无结果，记录无结果，不得编造候选变量。

## 六、交付

更新 StataGraph 仓库根目录 `OPENCODE_REPORT.md`，至少包含：

1. 实际执行命令、退出码、索引摘要；
2. 全部数据集覆盖表；
3. 九个重点数据库的文件/变量记录计数；
4. 中文与英文变量检索样例；
5. 变量标签缺失和元数据不完整情况；
6. Registry 路径门禁结果；
7. data-control 同步前后 HEAD、Git status；
8. 是否存在代码解析错误、未解析变量行或文件关联失败；
9. 明确说明本轮未读取原始微观数据。

## 七、禁止事项

- 不读取、抽样、打开或扫描任何原始微观数据（包括 .dta、.sav、.sas7bdat、原始 CSV/XLSX 数据）。
- 不递归扫描 data 本体，不猜路径，不访问 Registry 以外的本地路径。
- 不修改 StataGraph 源代码、data-control tracked 文件、catalog、registry 或 metadata。
- 不生成或提交原始数据副本、观测级数据、变量取值或隐私信息。
- 不把 path-derived year 当作正式波次。
- 不自动补写缺失标签，不把同名变量认定为同口径。
- 不因检索无结果而自行修改索引器或扩大任务。

## 八、完成条件与下一步

本轮通过条件：全部 catalog 数据集被索引；重点数据库均能 profile；中英文检索、来源行号和 Registry 路径门禁得到真实测试；缓存生成且 Git tracked 文件无变化。

完成后停止，NEXT_ACTOR=ChatGPT。

ChatGPT 审核后再决定是否进入第二阶段：对指定数据库/指定文件开展受控的原始变量结构诊断（如变量标签、样本量、ID、波次、缺失率和取值范围），以及是否为常用经济学概念建立经过核对的中文/英文同义词映射。第二阶段不在本任务内执行。
