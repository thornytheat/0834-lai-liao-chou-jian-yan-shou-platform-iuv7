# 字段与业务定义

输入编码 UTF-8，允许 BOM。首行必须匹配样例列顺序。记录键和业务组保留原始字符串。`kind` 允许 plan, producer, consumer, observed；两段抽检可再给第二计划行 `plan2`（或 `second_plan`）与第二实测行 `observed2`（或 `second_observed`），也接受 `supplement`/`second` 等近义 kind 或第二条同名 `plan`/`observed`。说明列 `note` 可以跨行，限制 200 字。

业务字段按 `lot`、`samples`、`acceptance`、`defects`、`limit_bp` 排列。最终值单位见阶段结果。数字接受非负整数、全角数字和完整千分位。空串、短横线、N/A、NULL 与未知为缺值。无关字段用 0 占位。

两段方案中第一计划行给 `N,n1,c1`，第二计划行的 `samples/acceptance` 给 `n2,c2`（`defects` 列可携带首抽拒收数 `r1`，缺省 `r1=c2+1`）。第二实测行给补抽件数 `m2` 与缺陷数 `d2`；只有一条 `observed` 且其 `samples>n1` 时，视为 `n1+m2` 的合并登记。`m2<n2` 时该组状态为 `PENDING_INSPECTION`（待验）；抽满后按两次缺陷总数 `d1+d2` 对照 `c2`。首抽 `d1≤c1` 且尚无补抽实测时，可走首抽直放，但其生产方/使用方风险须分别不超过 `limit_bp`。

有限批量无放回抽检。接收概率等于缺陷数不超过接收数的超几何尾和。两段方案的使用方接收概率为“首抽直接接收”与“进入补抽后累计接收”两条互斥路径之和，证据中分别给 `first_accept_bp`、`second_accept_bp` 与合计 `consumer_accept_bp`/`total_accept_bp`。生产方风险用良批被拒概率，使用方风险用劣批被接收概率，两类风险分别审核。显示值为风险向上取整的基点。

`incoming.csv` 包含四个业务组，第二组提供不同边界，第三组触发业务拒收，第四组需要核对。另含重复表头、冲突记录、重复回放与错误列数。`ready.csv` 含可以签发的两个组。
