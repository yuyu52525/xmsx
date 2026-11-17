"""Superset 运行配置（容器内挂载为 /app/pythonpath/superset_config.py）

三条关键配置，每条都对应第 4 周踩过的具体问题：
  1) PREVENT_UNSAFE_DB_CONNECTIONS=False
     4.x 默认禁止连 localhost / 私有网段，而我们的 Hive、MySQL 都是容器内网地址，
     不开这个开关，UI 里点"测试连接"永远报 Connection refused。
  2) SUPERSET_WEBSERVER_TIMEOUT / SQLLAB_TIMEOUT 放大到 180s
     Hive on Tez 冷启动一条聚合查询要 5~25s，默认 60s 的 gunicorn timeout 会直接 502。
  3) 不用 SQLite 存元数据
     SQLite 在并发写入（bootstrap 建图表 + UI 浏览）时会 database is locked，
     所以元数据也放 MySQL，单独一个库 superset_meta。
"""

from __future__ import annotations

import os

# ---------------- 密钥与元数据库 ----------------
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("必须通过环境变量提供 SUPERSET_SECRET_KEY（不要写死在代码里）")

SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SUPERSET_METADATA_URI",
    "mysql+pymysql://superset:superset@mysql:3306/superset_meta?charset=utf8mb4",
)

# ---------------- 行为 ----------------
ROW_LIMIT = 5000
SQLLAB_TIMEOUT = 180
SQLLAB_ASYNC_TIME_LIMIT_SEC = 300
SUPERSET_WEBSERVER_TIMEOUT = 180
VIZ_ROW_LIMIT = 5000
DEFAULT_TIMEZONE = "Asia/Shanghai"
ENABLE_PROXY_FIX = True

# 允许连内网数据库（Hive/MySQL 都在 docker 内网）
PREVENT_UNSAFE_DB_CONNECTIONS = False
PREVENT_UNSAFE_DEFAULT_EXPR = False

# 缓存：单实例小数据量，用内存缓存即可（不引 Redis，减少一个服务）
CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300}
DATA_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 60}
FILTER_STATE_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 3600}
EXPLORE_FORM_DATA_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 3600}

# ---------------- 功能开关 ----------------
# 联动筛选（native filter）与图表交叉筛选（cross filter）都放开
FEATURE_FLAGS = {
    "DASHBOARD_CROSS_FILTERS": True,
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_NATIVE_FILTERS_SET": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "EMBEDDABLE_CHARTS": True,
}

# ---------------- UI ----------------
APP_NAME = "云购生活 · 经营分析"
APP_ICON = "/static/assets/images/superset-logo-horiz.png"
LOGO_TOOLTIP = "云购生活数仓 · 第 4 周可视化"
FAVICONS = [{"href": "/static/assets/images/favicon.png"}]

# 中文界面
BABEL_DEFAULT_LOCALE = "zh"
LANGUAGES = {"zh": {"flag": "cn", "name": "Chinese"}, "en": {"flag": "us", "name": "English"}}

# 关闭示例数据加载（首次 init 不生成 examples 库，加快启动）
SUPERSET_LOAD_EXAMPLES = False

# 关闭告警邮件依赖（本机没有 SMTP，开了会在启动时报错刷屏）
ENABLE_ALERTS = False
ALERT_REPORTS_NOTIFICATION_DRY_RUN = True


# ============================================================================
# 兼容补丁：Hive 4.0.0 不认 SHOW CATALOGS
# ----------------------------------------------------------------------------
# 现象：Superset 保存 Hive 数据源时报 422 "Database could not be created."，
#       服务端日志真正原因是
#       ParseException: cannot recognize input near 'SHOW' 'CATALOGS'
# 原因：Superset 的 HiveEngineSpec 继承自 PrestoEngineSpec，
#       而 Presto 的 get_catalog_names() 会直接执行 SHOW CATALOGS（多目录特性）。
#       Hive 4.0.0 的 HiveServer2 没有这条语法 → 建数据源、同步权限全失败。
# 处理：把 Hive 的目录能力显式关掉（Hive 本来就没有 catalog 概念，
#       只有 database/schema，supports_catalog 本就该是 False）。
# 放在 try 里：万一以后升级 Superset 后类结构变了，也只是补丁失效，不会拖垮启动。
# ============================================================================
try:  # pragma: no cover
    from superset.db_engine_specs.hive import HiveEngineSpec

    HiveEngineSpec.supports_catalog = False

    @classmethod
    def _no_catalogs(cls, database, inspector=None):  # noqa: ANN001, ARG001
        return set()

    HiveEngineSpec.get_catalog_names = _no_catalogs
    print("[superset_config] 已关闭 Hive 的多目录探测（Hive 4.0.0 不支持 SHOW CATALOGS）")
except Exception as _exc:  # noqa: BLE001
    print(f"[superset_config] 模块级补丁未能生效（改用 FLASK_APP_MUTATOR）：{_exc}")


def _patch_hive_catalog(app) -> None:  # noqa: ANN001
    """在 app context 里再补一次。

    为什么不能只在模块顶层做：superset_config 被 import 时还没有 app context，
    而 superset.models.helpers 在 import 期就会读 app.config，
    所以顶层 `from superset.db_engine_specs.hive import ...` 会抛
    "Working outside of application context"（实测）。
    FLASK_APP_MUTATOR 由 Superset 在 init_app_in_ctx() 里调用，此时上下文已就绪。
    """
    try:
        from superset.db_engine_specs.hive import HiveEngineSpec

        HiveEngineSpec.supports_catalog = False
        HiveEngineSpec.get_catalog_names = classmethod(
            lambda cls, database, inspector=None: set()
        )
        print("[superset_config] Hive 目录探测已关闭（app context 内生效）")
    except Exception as exc:  # noqa: BLE001
        print(f"[superset_config] Hive 目录补丁失败：{exc}")


FLASK_APP_MUTATOR = _patch_hive_catalog