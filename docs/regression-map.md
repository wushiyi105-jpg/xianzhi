# 问题与回归测试映射

每个修过的问题都留了能复现的测试；测试名可以直接跑：

```bash
python -m unittest tests.test_xianzhi.TestMarketAnchor -v
```

| issue | 问题 | 对应测试 |
|---|---|---|
| #3 | 否定句被判成瑕疵（`无拆修`/`无进水`/`屏幕无划痕` 扣满 30%，`原装电池两块` 判成电池衰减） | `TestNegationRegression.test_negated_flaws_ignored`<br>`TestNegationRegression.test_positive_flaw_kept`<br>`TestNegationRegression.test_negated_keyword_is_flaw`<br>`TestNegationRegression.test_battery_pack_not_decay`<br>`TestNegationRegression.test_battery_health_counts`<br>`TestNegationRegression.test_clean_phone_not_capped` |
| #4 | 成色词重叠（`九成新` 被判成 95新，虚高 24%） | `TestConditionOverlapRegression.test_jiuchengxin_is_9`<br>`TestConditionOverlapRegression.test_95xin_is_good`<br>`TestConditionOverlapRegression.test_gap_between_two_conditions` |
| #5 | 爱回收到手价等于挂价，与「低 15%–25%」的说明矛盾 | `TestPlatformNetRegression.test_aihuishou_discount`<br>`TestPlatformNetRegression.test_hongbulin_ten_percent`<br>`TestPlatformNetRegression.test_sale_platforms_unchanged`<br>`TestPlatformNetRegression.test_gap_between_platforms` |
| #6 | 年限冲突（`2021 年买的` + `用了 4 年` 取成 6 年） | `TestYearsConflictRegression.test_used_years_wins`<br>`TestYearsConflictRegression.test_year_only`<br>`TestYearsConflictRegression.test_used_only` |
| #7 | 网页「最低接受价」框不生效 | `TestUserFloor.test_floor_overrides_formula`<br>`TestUserFloor.test_floor_default_is_formula`<br>`TestUserFloor.test_bargain_respects_user_floor`<br>`TestHttpLayer.test_quote_floor_applied`<br>`TestCliLayer.test_quote_floor_flag`<br>`TestCliLayer.test_quote_missing_file_exit_2` |
| #8 | 定价锚点错了（原价折旧给出 942，真实行情 1500–2200） | `TestMarketAnchor.test_iphone13_lands_in_real_band`<br>`TestMarketAnchor.test_market_price_works_without_original`<br>`TestMarketAnchor.test_unknown_model_falls_back_to_formula`<br>`TestMarketAnchor.test_gap_alert_when_formula_far_off`<br>`TestMarketAnchor.test_storage_changes_price`<br>`TestMarketAnchor.test_longest_alias_wins`<br>`TestMarketAnchor.test_condition_adjusts_market_price`<br>`TestMarketAnchor.test_seed_table_is_broad_enough`<br>`TestHttpLayer.test_quote_numbers`<br>`TestHttpLayer.test_quote_flags_formula_gap`<br>`TestCliLayer.test_quote_file_ok`<br>`TestCliLayer.test_quote_market_without_original` |
| #9 | 行情表没交代可信度：来源/样本量/挂价口径/覆盖率缺失，型号缺失时只给裸数字 | `TestMarketProvenance.test_every_row_has_meta`<br>`TestMarketProvenance.test_basis_is_asking_not_deal`<br>`TestMarketProvenance.test_coverage_is_stated`<br>`TestMarketProvenance.test_formula_path_says_no_market_and_low`<br>`TestCliLayer.test_quote_file_ok`（行情来源/样本量/非实时）<br>`TestCliLayer.test_quote_formula_warns_no_market`<br>`TestHttpLayer.test_page_served`（行情来源/行情覆盖） |
| #10 | 公式对无行情品类系统性偏低：4299 冰箱算出 495（残值 11%） | `TestFormulaResidual.test_appliance_residual_in_real_band`<br>`TestFormulaResidual.test_appliance_condition_squash_softens_coef`<br>`TestFormulaResidual.test_floor_hit_is_reported`<br>`TestFormulaResidual.test_phone_formula_unchanged` |
| #11 | 「以行情为准」把估算抬成事实 | `TestCliLayer.test_quote_file_ok`（并排句 + `assertNotIn("以行情为准")` + `(经验值,非统计)`）<br>`TestHttpLayer.test_page_served`（页面脚本同样不得出现该措辞） |

## 为什么这样对应

- **#3 六条**：三条管否定（`无拆修` 不算、`有划痕` 算、`无划痕` 但真的写了「非原装」仍要算），三条管电池（`原装电池两块` 不算衰减、`电池健康 82%` 算、干净手机不被误扣满）。
- **#4 三条**：先各自归属（`九成新`→9成新、`95新`→95新），再断言两者系数真的不同档，防止只改关键词表却没改取值顺序。
- **#5 四条**：回收平台折价生效、寄卖平台按费率、两个个人交易平台不受影响、回收价必须明显低于个人成交价。
- **#6 三条**：两者同时出现取「用了 N 年」、只有年份、只有年数，三种输入都锁死。
- **#7 六条**：规则层（底价覆盖、默认底价、砍价不破底价）+ HTTP 真请求 + CLI 真子进程；`--file` 读不到给中文提示并以 2 退出。
- **#8 十二条**：前八条在规则层锁住「行情优先」的全部行为（真实区间、无原价、型号缺失、偏离提示、容量分档、别名最长命中、成色单调、种子表规模），后四条在 HTTP/CLI 层锁住接口输出。
- **#9 七条**：四条在规则层/数据层（每行 meta 齐全、基准是 asking 不是成交价、样本量留 null、覆盖率与品类名、无型号时的提示文案含型号数与「公式值通常偏低」），三条在入口层（CLI 打出行情来源与样本量、CLI 打无行情提示、网页脚本含行情来源与覆盖）。
- **#10 四条**：家电残值落回 1300–2000 且 ≥30%、家电压缩后的成色系数高于原系数、触底时 `floor_hit` 为真且基数等于原价 30%、手机公式价不被牵连（仍 <1200 保护 942 那个量级）。
- **#11 两条入口层断言**：CLI 必须打出并排句「公式折旧…行情估算…两者均为估算」，且**不许**出现「以行情为准」；网页脚本同理。措辞属于输出契约，所以钉在入口层而不是规则层。

规则层测「算得对不对」，入口层测「接上之后还对不对」；两层都断，才算这个 bug 真的不会回来。
