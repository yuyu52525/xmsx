# Yungou Life — Enterprise Data Warehouse & Retail Analytics Platform

**English** | [简体中文](README.md)

> A complete, reproducible, end-to-end data platform for a simulated omnichannel retailer:
> raw CSV → ODS → DWD → DWS → ADS → forecasting → NL2SQL → BI dashboard / data wall / chat UI → one-command Docker deployment.

| | |
|---|---|
| **Course** | Enterprise Project Practice (Data Science & Big Data Technology, B.Eng.) |
| **Team** | Letian — Yu Tianle (余天乐), Student ID 20230308098 |
| **Scope** | 51 warehouse tables · 9 containerized services · 3 visualization front-ends · 10 data APIs |
| **Data** | 2024-01-01 → 2024-12-31, 114,809 source rows (111,037 after cleaning) |
| **Status** | All deliverables complete and verified end to end (39/39 automated checks pass) |

---

## Table of Contents

- [Why this project](#why-this-project)
- [Architecture](#architecture)
- [Key results](#key-results)
- [Feature highlights](#feature-highlights)
- [Quick start](#quick-start)
- [Access points](#access-points)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Data model](#data-model)
- [Metric definitions](#metric-definitions)
- [Data API](#data-api)
- [Performance engineering](#performance-engineering)
- [Engineering practices](#engineering-practices)
- [Documentation](#documentation)
- [Known limitations](#known-limitations)
- [Team](#team)
- [License](#license)

---

## Why this project

A retailer with 60 stores and three online channels (app, web, mini-program) needs four answers every day: *how much did we sell, what changed, where is the money, and who is worth keeping.* In the source system those answers live in six flat CSV exports that no one can trust:

- 600 duplicated orders and 602 impossible amounts (as low as −4,994.73, as high as 9.96 M);
- seven enum fields with 6–16 spelling variants (`pv` / `PV` / `浏览` are three different values to `GROUP BY`);
- line-item amounts that simply do not add up to the order total.

This project turns that raw material into something an executive can read in one screen: a **layered warehouse with a single, documented definition for every metric**, three ways to consume it, and a one-command deployment so anyone can reproduce the demo.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ⑤ Deployment      Docker Compose — 9 services (7 long-running + 2 init)  │
├──────────────────────────────────────────────────────────────────────────┤
│  ④ Presentation    Superset (6 charts) · ECharts wall (7 charts) ·        │
│                    Streamlit NL2SQL · FastAPI (10 JSON endpoints)         │
├──────────────────────────────────────────────────────────────────────────┤
│  ③ Serving layer   ClickHouse  ydsh_ads  (11 result-set replicas)         │
│                    MySQL       ydsh_mysql (3 KPI snapshots, read-only)    │
├──────────────────────────────────────────────────────────────────────────┤
│  ② Warehouse       ADS 11 → DWS 9 → DWD 25 → ODS 6      (51 tables)       │
│                    Hive 4.0 on Tez · ORC + SNAPPY · monthly partitions    │
├──────────────────────────────────────────────────────────────────────────┤
│  ① Sources         6 CSV exports (114,809 rows) · MySQL metastore         │
└──────────────────────────────────────────────────────────────────────────┘
```

**Layer contract.** Each layer reads only from the layer above it. ODS is a byte-for-byte landing zone (dirty data included, by design). DWD is where cleaning, standardization and star-schema modelling happen. DWS pre-aggregates by day/week/month. ADS contains one table per chart, with the metric definition baked in — the number on the screen and the number in the document are guaranteed to be the same number.

**Why a separate serving layer.** Hive-on-Tez pays a session and query-planning cost on every statement (1–15 s in this environment); the whole ADS layer is only 2,666 rows. Replicating it into ClickHouse brings the same queries down to 30–50 ms. ClickHouse is **not** a second warehouse: it runs no ETL, and it is rebuilt from Hive whenever a definition changes.

---

## Key results

| Metric | Value |
|---|---|
| GMV (order basis) | **36,116,687.06 CNY** |
| Valid GMV (revenue-eligible) | 24,185,272.59 CNY (66.96%) |
| Orders / buyers | 14,398 / 1,000 |
| Average order value / ARPU | 2,508.45 / 36,116.69 CNY |
| Category sales total (allocation basis) | 35,833,305.06 CNY |
| Top category | Sports & Outdoors — 5,343,128.16 CNY (14.91%) |
| Top province | Shaanxi — 2,851,136.58 CNY (7.89%) |
| Channel mix | App 25.46% · Web 24.99% · Store 24.93% · Mini-program 24.63% |
| Payment mix | WeChat 26.77% · Alipay 26.22% · Bank card 23.59% · COD 23.42% |
| Warehouse size | ODS 6 · DWD 25 · DWS 9 · ADS 11 = **51 tables** |
| Row reduction after cleaning | 114,809 → 111,037 (−3,772 rows, 3.29%) |

---

## Feature highlights

**Data engineering**

- Four-layer Hive warehouse with 51 tables, explicit naming conventions, and a per-field Chinese `COMMENT` on every column.
- Idempotent load scripts (`DROP TABLE IF EXISTS` + `INSERT OVERWRITE`): re-running produces the same result.
- `dwd_order` is partitioned by `order_month` (12 partitions) and bucketed by `user_id` (8 buckets); partition pruning was measured at **6.0×** (15.44 s → 2.58 s).
- 14 `stg_*` staging tables kept on purpose: every cleaning step is auditable, line count by line count.

**Analytics & AI**

- 21 documented KPIs; every definition resolves to a field, and everything is cross-checked by summation tests.
- GMV forecast (daily, linear regression) validated with 6-fold rolling backtest — **and reported honestly: MAPE 12.72% vs 12.11% for the naive "historical mean" baseline, i.e. the model added no value.**
- NL2SQL over the warehouse (GLM-4-Flash, any OpenAI-compatible provider), with a read-only SQL guard, a token usage log (~3.5k tokens per question) and an offline demo mode.

**Visualization**

- **Superset** dashboard: 6 charts (KPI cards, monthly trend, category bars, province ranking bars, payment pie, store ranking), 3 native filters and cross-filtering — created entirely through the REST API and re-runnable (`superset-init` is idempotent).
- **ECharts data wall**: 7 panel types at a 1920×1080 design size with `transform: scale()` responsiveness, fully localized assets (works offline) and a JSON snapshot fallback if the API is down.
- **Streamlit Q&A**: question → SQL → guard → execute → table + chart, with history, error surfacing, CSV export.

**Delivery**

- 9 services orchestrated with health-checked dependency ordering; the whole stack starts with `docker compose up -d`.
- One-command verification: `python 第5周/py/e2e_verify.py` runs 39 cross-layer consistency checks.

---

## Quick start

**Prerequisites:** Windows 10/11 with Docker Desktop (WSL2), ≥ 8 GB RAM, and these ports free: 3307, 9083, 10000, 10002, 8123, 9000, 8088, 8000, 8501.

```bash
git clone git@github.com:yuyu52525/xmsx.git
cd xmsx

# 1. Configure secrets (never committed — .env is git-ignored)
cp .env.example .env
#    Required: SUPERSET_SECRET_KEY, LLM_API_KEY (optional), CLICKHOUSE_PASSWORD

# 2. Build images (Superset + Hive drivers; app image with FastAPI/Streamlit)
docker compose build

# 3. Start all 9 services
docker compose up -d

# 4. Verify: 7 healthy + 2 clean one-shot exits
docker compose ps
```

Then load the warehouse (first run only — skip if `data/warehouse` already contains data):

```bash
# ODS → DWD → DWS → ADS, in this order
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第1周/sql/ods/create_ods.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第1周/sql/ods/load_ods.sql
# ... see docs/部署手册 (Deployment Manual) for the full 8-step sequence

# Replicate ADS into the serving layer
python 第4周/py/export_to_clickhouse.py
python 第4周/py/export_to_mysql.py
```

Finally, run the end-to-end self-check:

```bash
python 第5周/py/e2e_verify.py     # expect: 39 checks, 39 passed, ~150 s
```

---

## Access points

| Entry | URL | Credentials |
|---|---|---|
| ECharts data wall | http://localhost:8000/ | none |
| Superset dashboard | http://localhost:8088/superset/dashboard/ydgmv-overview/ | admin / admin |
| Streamlit NL2SQL | http://localhost:8501/ | none |
| API docs (OpenAPI) | http://localhost:8000/api/docs | none |
| Health check | http://localhost:8000/api/health | none |

---

## Tech stack

| Concern | Choice | Why |
|---|---|---|
| Warehouse | Apache Hive 4.0.0 on Tez | Required by the course; full partitioning/bucketing; runs in a single Docker host |
| Metastore | MySQL 8.0 | Officially supported by Hive; reused for Superset metadata and KPI snapshots |
| Storage format | ORC + SNAPPY | Columnar + cheap compression; 933 KB for 12 partitions vs 1.38 MB of CSV |
| Serving cache | ClickHouse 24.8 | Millisecond aggregates, SQL close enough to Hive to share queries |
| BI | Apache Superset 4.1.2 | Hive/MySQL sources, native filters, REST-API-automatable |
| Data wall | ECharts 5.5.1 (local) | Widest chart coverage (map/heatmap/scatter/dual-axis); works offline |
| Chat UI | Streamlit 1.67 | Pure-Python interactivity for a single question→SQL→chart flow |
| Data API | FastAPI + uvicorn | Auto-generated OpenAPI docs, async, plays well with pandas |
| LLM | GLM-4-Flash (pluggable) | Free tier, OpenAI-compatible, adequate Chinese SQL generation |
| Packaging | Docker Compose v2 | Health-checked multi-service orchestration on one host |
| VCS | Git + GitHub | Branch/PR history is part of the grading rubric |

---

## Repository layout

```
.
├── docker-compose.yml          # 9 services, health checks, dependency ordering
├── .env.example                # template only — placeholders, no real secrets
├── data/                       # git-ignored: csv/, warehouse/, mysql/
├── lib/                        # MySQL JDBC driver for the Hive metastore
├── 第1周/ (week 1)             # environment, ODS landing layer, quality pre-assessment
├── 第2周/ (week 2)             # cleaning, DWD star schema, EDA
├── 第3周/ (week 3)             # DWS/ADS, KPI definitions, forecasting, NL2SQL, AI insights
├── 第4周/ (week 4)             # Superset, ECharts wall, Streamlit, Docker, load testing
├── 第5周/ (week 5)             # integration & docs: e2e checks, five deliverable documents
├── README.md                   # Chinese README
└── README.en.md                # this file
```

Each weekly folder is self-contained and contains `sql/`, `py/`, `docs/` and `evidence/` (real command output, kept as proof rather than screenshots of claims).

---

## Data model

**Star schema at the DWD layer** — 4 dimensions, 3 fact tables, 4 code-mapping mini-dimensions.

| Table | Rows | Grain | Notes |
|---|---|---|---|
| `dim_user` | 1,000 | one row per user | age band, province → region, member level code |
| `dim_product` | 600 | one row per product | category, brand, price, launch date |
| `dim_store` | 60 | one row per store | **60 IDs but only 52 names — always aggregate by `store_id`** |
| `dim_date` | 731 | one row per day | 2023-01-01 → 2024-12-31 |
| `dwd_order` | 14,398 | one row per order | `order_month` partition, `user_id` bucketing |
| `dwd_order_item` | 34,979 | one row per order line | dual amount fields, see below |
| `dwd_user_behavior` | 60,000 | one row per event | Oct–Dec 2024 only |

**The dual-amount decision (the single most important modelling choice).**

| Field | Formula | Use | Summable to GMV? |
|---|---|---|---|
| `item_amount` | `qty × unit_price × (1 − discount)` | raw line amount | No |
| `alloc_amount` | `pay_amount × item_amount / Σ(item_amount per order)` | allocates the order total onto lines | Yes |

Source line amounts do not reconcile with order totals (mean absolute gap ≈ 141.5k CNY per order). Without allocation, category shares would sum to a number unrelated to GMV. After allocation, the category total equals 35,833,305.06 CNY — within **0.65 CNY** of the order total for orders that have line items (pure rounding drift), and category shares sum to 100%.

**The 283,382.65 CNY gap** between GMV (36,116,687.06) and allocated line totals (35,833,305.06) is explained: 114 of 14,398 orders have no line items (99.2% coverage). The two figures must never be added together.

---

## Metric definitions

Three metric tiers: atomic (measures on facts) → derived (measure + dimensions + period) → composite (arithmetic between derived metrics).

| ID | Metric | Definition | Value (2024) |
|---|---|---|---|
| K01 | GMV | `SUM(pay_amount)` on all orders | 36,116,687.06 |
| K02 | Valid GMV | `SUM(pay_amount) WHERE is_valid_revenue = 1` | 24,185,272.59 |
| K04 | Orders | `COUNT(DISTINCT order_id)` | 14,398 |
| K06 | Buyers | `COUNT(DISTINCT user_id)` | 1,000 |
| K07 | AOV | K01 / K04 | 2,508.45 |
| K08 | ARPU | K01 / K06 | 36,116.69 |
| K12 | Monthly repurchase rate | buyers with ≥2 orders that month / buyers that month | 45.82% – 50.85% |
| K13 | Category sales | `SUM(alloc_amount)` by category | 35,833,305.06 total |
| K17 | Sales per sqm | store GMV / floor area | per store |
| K19 | RFM segment | R/F/M scored 1–5, 8 segments | 1,000 users |

**Consistency is enforced, not assumed.** Daily, weekly and monthly DWS totals all equal K01; six order-basis ADS tables all equal K01; two allocation-basis ADS tables equal 35,833,305.06; and the difference between the two equals the spend of the 114 line-item-less orders.

---

## Data API

`GET /api/health` · `/api/kpi` · `/api/month` · `/api/daily` · `/api/category` · `/api/province` · `/api/paytype` · `/api/hour_category` · `/api/store?top=N` · `/api/rfm` · `/api/channel` · `/api/all?nocache=1`

`POST /api/ask` — `{"question": "What is the GMV share by payment method?"}` → `{sql, row_count, data}`

Every response carries its provenance:

```json
{ "ok": true, "backend": "clickhouse", "elapsed_ms": 12.4, "cached": false, "data": [ ... ] }
```

`backend` tells you which engine served the request, so a slow response is immediately attributable. `nocache=1` bypasses the 10-second in-process cache (used by the load tests — measuring cache hits would flatter the numbers).

---

## Performance engineering

| Optimization | Before | After | Speed-up |
|---|---|---|---|
| Partition pruning (`order_month='2024-11'`) | 15.44 s | 2.58 s | **6.0×** |
| Pre-aggregated ADS vs. recomputing from detail | 3.25 s | 1.13 s | **2.9×** |
| Serving-layer cache (20 concurrent, p50) | 2,491 ms | 381 ms | **6.5×** |
| Read path: Hive → ClickHouse (8 concurrent, p50) | 4,418 ms | 39 ms | **113×** |

Failure rate under 20 concurrent clients: **0%**.

**A negative result is kept on purpose:** bucketed join between `dwd_order` and `dim_user` measured 16.47 s with no benefit — `dim_user` has 1,000 rows, so Hive broadcasts it via map join and never touches the shuffle. Optimization claims need a baseline.

---

## Engineering practices

- **Conventional commits**, feature branches, and archived PR records (including a real merge-conflict transcript).
- **Idempotent everything**: table creation drops first, loads overwrite, the Superset bootstrap re-runs safely.
- **Evidence over adjectives**: query output, timing and verification logs are committed under each `evidence/` folder.
- **Secrets discipline**: three-tier config (template → local `.env` → container env). No key ever appears in code, image or log; `git grep "sk-"` returns nothing.
- **Honest reporting**: the forecast model loses to the baseline and says so; four metrics are documented as "computable but not interpretable" because the simulated data cannot support them (see below).

---

## Known limitations

These are properties of the simulated dataset, not bugs. They are documented so that no one mistakes an artefact for a business insight.

| # | Limitation | Consequence |
|---|---|---|
| 1 | Every user orders 4–27 times a year | Lifetime repurchase rate = 100%, no discriminative power → monthly repurchase rate used instead |
| 2 | Behaviour events are independently sampled, not session paths | "Purchase rate 35% > add-to-cart rate 24%" is meaningless; only event volumes are reported |
| 3 | Only one year of orders | No YoY comparison; ISO 2024-W53 covers just 2 days and must not be read as "the worst week" |
| 4 | `order_hour` is randomly populated | The hour×category heatmap proves the pipeline works; it supports **no** statement about peak hours |
| 5 | 8 store names are shared by 2 different store IDs | Name-level aggregation silently merges two stores; all outputs group by `store_id` |

---

## Documentation

| Document | File |
|---|---|
| Requirements (business background, requirements, metric system) | `第5周/docs/需求文档.docx` |
| Data quality & cleaning report (five defect classes, repair rates) | `第5周/docs/数据质量清洗报告.docx` |
| Architecture design (four layers, dimensional modelling, technology choices) | `第5周/docs/架构设计文档.docx` |
| Deployment manual (environment, 8-step deployment, 20 troubleshooting entries) | `第5周/docs/部署手册.docx` |
| API configuration guide (secrets, LLM providers, endpoints, rotation SOP) | `第5周/docs/API配置指南.docx` |
| End-to-end integration record | `第5周/docs/端到端联调记录.md` |
| AI collaboration log / personal retrospective | `第5周/docs/第5周_AI协同日志.docx`, `第5周/docs/项目反思日志.docx` |

---

## Team

| Name | Student ID | Roles |
|---|---|---|
| Yu Tianle (余天乐) | 20230308098 | Project lead · data engineer · analyst / AI engineer · visualization & deployment engineer |

Five-week scope: environment & ODS → cleaning & DWD → DWS/ADS & AI → visualization & Docker → integration, documentation and release.

---

## License

Course project, released for learning and portfolio purposes. The dataset is synthetic; no real customer or transaction data is included. Add a license file (e.g. MIT) before any public distribution.