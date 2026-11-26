# 参与

## 本地跑起来

```bash
uv sync --extra dev
uv run xianzhi doctor
uv run pytest -q
```

## 提 PR 之前

1. 规则改动必须落在 `xianzhi/domain/rules/`，并且新增一条 `rule_id`；
2. 每条 `rule_id` 至少一条断言，`tests/` 里能单独跑；
3. `ruff check .`、`mypy xianzhi`、`pytest -q` 全过；
4. CLI 和 Web 里不要写死规则，规则只在 domain 里；
5. 改表结构就加一条 `migrations/versions/`，并写清 up/down。

## 提交信息

`type: 一句话说清改了什么`，type 用 feat / fix / docs / test / refactor。
