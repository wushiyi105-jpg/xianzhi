# 更新记录

## 1.0.0

- 新栈重写：domain 规则层（成色词表、数码/家电折旧公式、平台费率）+ SQLAlchemy 存储
- 行情锚定：命中 10 个型号走 mid/low/high，未命中返回公式 ±8% 并标 `pricing.no_market`
- 成色词表最长匹配，前 3 字否定窗口过滤"没有/无/不/未/非"
- 平台到手价对比，回收价低于挂价 85% 出 `fees.recycle_gap`
- 数字守卫：引用了输入里没有的数字整句丢弃
- Alembic `0001_init` + `migrate` 子命令（0.x 旧库先备份再转 cents 表）
- CLI：quote / listing / history / migrate / serve / doctor；Web 单页 + `/health`
- 测试 26 条，覆盖迁移、守卫、公式边界
