# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean` 或 `file=<CSV>` 三选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批和当前复核状态。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。

补抽更正可 `POST|PATCH|PUT /api/runs/<id>/correction`（别名 `/supplement`、`/inspection`），接收 `revision`、可选 `case` 以及 `second_samples`/`second_defects`（也接受 `samples2`/`defects2`、`supplement_*` 等近义字段，或嵌套 `supplement` 对象）。更正经同一把乐观锁写入并令 `revision+1`，随后按新件数重算该组状态与 `balance`；更正先提交后，旧 `revision` 的签发收到 `STALE_REVIEW`。

签发重试支持幂等：请求头 `Idempotency-Key`（或 `X-Request-Id`），或 JSON 字段 `idempotency_key`/`request_id`。同一把键（同一运行）的重复请求返回首次回执，`revision` 不再增加。不带键时，同一 `revision`、同一意见的 `APPROVED` 原样重试也会回放首次签发结果，不会重复签发；不同内容的旧版本请求仍返回 `STALE_REVIEW`。

`GET /api/runs/<id>/receipt?key=<Idempotency-Key>` 可取回已记录的回执。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、业务证据和复核信息的 JSON。
