# StataGraph V0.2.2 — 本地微观数据库图谱 Smoke Test

TASK_ID: STG_DATABASE_GRAPH_LOCAL_METADATA_SMOKE_20261103
STATUS: READY_FOR_OPENCODE
AUTHOR: ChatGPT
EXECUTOR: OpenCode
next_actor: ChatGPT
automation_ready: false

## 唯一目标

使用本机现有的 data-control 控制仓库，验证 StataGraph V0.2.2 能否真实索引并检索 CFPS、CHFS、CSMAR 等数据库的文件级和变量级 metadata。

本任务只验证已经提交的代码，不新增、不修改科研代码，也不重新整理数据库。

## 固定输入

- StataGraph：当前仓库根目录。
- 数据控制仓库：C:\Users\admin\Documents\data-control。
- 允许读取：
  - catalog/datasets.csv
  - catalog/data_registry.csv
  - metadata/<dataset>/files.csv
  - metadata/<dataset>/variables.csv

## 执行步骤

1. 确认 StataGraph 当前代码版本为 0.2.2。
2. 确认 C:\Users\admin\Documents\data-control 存在，且包含上述 catalog / metadata 文件。
3. 记录 data-control 的 git status --short 和 HEAD；若存在任何未提交改动，立即停止并报告 BLOCKED，不得覆盖。
4. 仅在 data-control 控制仓库执行 git pull --ff-only，同步最新 catalog、metadata 和 .gitignore；记录同步前后 HEAD。禁止在数据本体目录执行任何 Git 操作。
5. 在 StataGraph 仓库执行：

   python -m pip install -e .
   statagraph index-databases "C:\Users\admin\Documents\data-control"

6. 检查生成的 C:\Users\admin\Documents\data-control\.statagraph\database_index.json。
7. 执行以下检索：

   statagraph search-databases "C:\Users\admin\Documents\data-control" CFPS
   statagraph search-database-variables "C:\Users\admin\Documents\data-control" "个人id" --dataset-id cfps --limit 5
   statagraph search-database-variables "C:\Users\admin\Documents\data-control" "hhid" --dataset-id chfs --limit 5
   statagraph search-database-variables "C:\Users\admin\Documents\data-control" "Stkcd" --dataset-id csmar --limit 5
   statagraph database-profile "C:\Users\admin\Documents\data-control" cfps
   statagraph database-profile "C:\Users\admin\Documents\data-control" chfs
   statagraph database-profile "C:\Users\admin\Documents\data-control" csmar

8. 检查索引摘要、三组检索结果、source metadata row、Registry status 和 local path 字段。
9. 再次检查 data-control 的 git status --short，确认生成的 .statagraph/ 缓存被忽略，没有改动任何受版本控制的 catalog / metadata 文件。

## 验收标准

- 能读取数据集目录和 Registry。
- CFPS、CHFS、CSMAR 均能建立文件和变量索引；如果某个数据集缺少 metadata，报告实际缺项，不猜测补齐。
- 中文变量标签和英文变量名均能命中。
- 检索结果保留变量所属文件、变量名、标签、类型、metadata 来源文件和行号。
- 只有 Registry 为 VERIFIED 的数据集出现 local_path_relative；其他状态不得暴露可用本地路径。
- .statagraph/database_index.json 生成成功且不出现在 Git 未跟踪文件中。
- 不修改 StataGraph 源代码，不修改 data-control 的 tracked 文件，不访问原始数据镜像。

## 安全边界

- 禁止读取 C:\Users\admin\Documents\data 下的任何原始微观数据文件。
- 禁止打开 .dta、.sav、.sas7bdat、CSV 原始数据以读取观测值。
- 禁止递归扫描 data 镜像、猜测路径、下载、移动、重命名或覆盖任何文件。
- 禁止修改 catalog/data_registry.csv、catalog/datasets.csv 和 metadata/。
- 如果固定控制仓库路径不存在或 metadata 不完整，停止并报告 BLOCKED；不得搜索其他目录替代。

## 交付

将真实命令输出摘要、数据集/文件/变量计数、三组变量检索结果、Registry 门禁检查、Git status 和异常写入 OPENCODE_REPORT.md。

只执行本任务，不自行扩展功能。
