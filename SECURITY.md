# 安全说明

## 数据在哪

报价记录全部在本地 SQLite（默认 `data/xianzhi.db`）。不上传、不调用除你自己配置的模型和 webhook 之外的地址。

## 报了什么

发现注入、越权、路径穿越，或价格公式被异常输入带偏，发邮件到 wushiyi105@gmail.com，标题写 `xianzhi security`。
三个工作日内回复，修完在 CHANGELOG 里写明版本。

## 不要做的

- 不要把带真实交易记录的库提交进仓库；
- 不要把模型 key 或 webhook 地址写进 `.env.example`；
- 部署到公网前先加认证，这个服务默认只监听本机。
