"""第 3 周 · 时间序列分析与未来 7 天 GMV 预测

流程：
  1. 从 Hive 的 ydsh_ads.ads_sales_daily 取每日 GMV 序列（366 天）
  2. 趋势分解：7 日 / 30 日移动平均、月度汇总、星期效应、环比
  3. 特征工程：lag_1 / lag_7 / ma_7 / ma_14 / 星期 / 月份
  4. 时序切分：前 336 天训练，最后 30 天测试（绝不打乱顺序）
  5. 两个模型：线性回归 + 梯度提升树（sklearn 的 GBR，等价于 XGBoost 的
     "树提升"思路；本机未装 xgboost，报告里已说明这一替换）
  6. 评估：MAE / RMSE / MAPE，并与"昨天=今天"的朴素基线对比
  7. 用表现更好的模型递归预测未来 7 天
  8. 输出：指标 JSON + 图表 PNG

用法：
  python forecast_gmv.py
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 无界面环境必须用 Agg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

from hive_client import query_df

warnings.filterwarnings("ignore")

# ---- 路径 ----
ROOT = Path(__file__).resolve().parent.parent          # 第3周
IMG_DIR = ROOT / "docs" / "images"
EVID_DIR = ROOT / "evidence"
IMG_DIR.mkdir(parents=True, exist_ok=True)
EVID_DIR.mkdir(parents=True, exist_ok=True)

# ---- 中文字体（Windows 自带）----
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

FEATURES = ["lag_1", "lag_7", "ma_7", "ma_14", "dow", "is_weekend", "month", "day"]


def load_series() -> pd.DataFrame:
    """取每日销售序列并补齐星期/月份等时间特征。"""
    sql = """
        select order_date, gmv, valid_gmv, order_cnt, buyer_cnt, item_qty, aov, is_weekend
        from ydsh_ads.ads_sales_daily
        order by order_date
    """
    df = query_df(sql)
    df["order_date"] = pd.to_datetime(df["order_date"])
    df = df.sort_values("order_date").reset_index(drop=True)
    # pyhive 可能把数值列读成 Decimal，统一成 float
    for col in ["gmv", "valid_gmv", "aov"]:
        df[col] = df[col].astype(float)
    for col in ["order_cnt", "buyer_cnt", "item_qty", "is_weekend"]:
        df[col] = df[col].astype(int)
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """构造滞后与滑动平均特征。

    关键点：所有滚动特征都先 shift(1)，只用"昨天及更早"的信息，
    否则会把当天的 GMV 泄漏进特征，模型评估会虚高。
    """
    out = df.copy()
    out["lag_1"] = out["gmv"].shift(1)
    out["lag_7"] = out["gmv"].shift(7)
    out["ma_7"] = out["gmv"].shift(1).rolling(7).mean()
    out["ma_14"] = out["gmv"].shift(1).rolling(14).mean()
    out["dow"] = out["order_date"].dt.dayofweek          # 周一=0
    out["month"] = out["order_date"].dt.month
    out["day"] = out["order_date"].dt.day
    return out


def ma_forecast(values: list[float], model, last_date: pd.Timestamp, horizon: int = 7):
    """递归预测：每预测一天，把它当成"已知"继续预测下一天。"""
    hist = list(values)
    rows = []
    for step in range(1, horizon + 1):
        cur = last_date + pd.Timedelta(days=step)
        feat = {
            "lag_1": hist[-1],
            "lag_7": hist[-7],
            "ma_7": float(np.mean(hist[-7:])),
            "ma_14": float(np.mean(hist[-14:])),
            "dow": cur.dayofweek,
            "is_weekend": 1 if cur.dayofweek >= 5 else 0,
            "month": cur.month,
            "day": cur.day,
        }
        X = pd.DataFrame([[feat[f] for f in FEATURES]], columns=FEATURES)
        yhat = float(model.predict(X)[0])
        yhat = max(yhat, 0.0)
        hist.append(yhat)
        rows.append({"order_date": cur.strftime("%Y-%m-%d"), "pred_gmv": round(yhat, 2), "step": step})
    return pd.DataFrame(rows)


def rolling_backtest(feat_df: pd.DataFrame, factories: dict, n_folds: int = 6,
                     fold_size: int = 30) -> pd.DataFrame:
    """滚动起点回测（rolling-origin），比单次 30 天切分稳得多。

    做法：把最后 n_folds*fold_size 天切成 n_folds 个连续测试块，
    第 k 折用"该块之前的全部数据"训练、预测该块，各折不重叠。

    注意：这里是**一步预测**（特征里的 lag 用真实值），比第 7 节的递归多步预测乐观，
    只能用来横向比较模型，不能直接当作上线精度。
    """
    n = len(feat_df)
    rows = []
    for k in range(n_folds):
        end = n - (n_folds - 1 - k) * fold_size
        start = end - fold_size
        tr, te = feat_df.iloc[:start], feat_df.iloc[start:end]
        y_true = te["gmv"].values
        for name, make in factories.items():
            model = make()
            model.fit(tr[FEATURES], tr["gmv"])
            y_hat = model.predict(te[FEATURES])
            rows.append({
                "fold": k + 1,
                "test_start": str(te["order_date"].min().date()),
                "test_end": str(te["order_date"].max().date()),
                "model": name,
                "MAE": float(mean_absolute_error(y_true, y_hat)),
                "MAPE": float(np.mean(np.abs((y_true - y_hat) / y_true)) * 100),
            })
    return pd.DataFrame(rows)


def main() -> None:
    print("[1/6] 从 Hive 取每日 GMV 序列 ...")
    df = load_series()
    print(f"      取到 {len(df)} 天：{df['order_date'].min().date()} ~ {df['order_date'].max().date()}")

    # ---------------- 趋势分解 ----------------
    print("[2/6] 趋势分解（移动平均 / 月度 / 星期效应）...")
    df["ma7"] = df["gmv"].rolling(7).mean()
    df["ma30"] = df["gmv"].rolling(30).mean()

    monthly = (
        df.groupby(df["order_date"].dt.to_period("M"))
        .agg(gmv=("gmv", "sum"), orders=("order_cnt", "sum"), days=("gmv", "size"))
        .reset_index()
    )
    monthly["month"] = monthly["order_date"].astype(str)
    monthly["gmv_mom"] = monthly["gmv"].pct_change()

    weekday = df.groupby("order_date").agg(gmv=("gmv", "sum")).reset_index()
    weekday["dow"] = weekday["order_date"].dt.dayofweek
    weekday_effect = weekday.groupby("dow")["gmv"].mean()
    weekday_name = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    print(f"      全年日均 GMV：{df['gmv'].mean():,.2f}")
    print(f"      月均 GMV：{monthly['gmv'].mean():,.2f}")
    print("      星期效应（日均 GMV）：")
    for i, v in weekday_effect.items():
        print(f"        {weekday_name[i]}  {v:,.2f}")

    # ---------------- 建模 ----------------
    print("[3/6] 特征工程 + 时序切分 ...")
    # 只对建模特征列判空：ma7 / ma30 是画图用的，若一并参与 dropna
    # 会白扔掉开头 29 天（ma30 需要 30 天窗口），训练集无辜缩水 15 天。
    feat_df = add_features(df).dropna(subset=FEATURES).reset_index(drop=True)
    test_size = 30
    train = feat_df.iloc[:-test_size]
    test = feat_df.iloc[-test_size:]
    print(f"      训练集 {len(train)} 天 {train['order_date'].min().date()} ~ "
          f"{train['order_date'].max().date()}，测试集 {len(test)} 天 "
          f"{test['order_date'].min().date()} ~ {test['order_date'].max().date()}（不打乱）")

    X_train, y_train = train[FEATURES], train["gmv"]
    X_test, y_test = test[FEATURES], test["gmv"]

    print("[4/6] 训练两个模型 ...")
    models = {
        "线性回归": LinearRegression(),
        "梯度提升树(GBR)": GradientBoostingRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=3, random_state=42
        ),
    }
    results, preds = {}, {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mape = float(np.mean(np.abs((y_test - y_pred) / y_test)) * 100)
        # MBE 平均偏差：正数=系统性低估。MAPE 是绝对值，看不出方向性偏差，必须一起报。
        mbe = float(np.mean(y_test - y_pred))
        results[name] = {"MAE": round(mae, 2), "RMSE": round(rmse, 2),
                         "MAPE": round(mape, 2), "MBE": round(mbe, 2)}
        preds[name] = y_pred
        print(f"      {name}: MAE={mae:,.2f}  RMSE={rmse:,.2f}  MAPE={mape:.2f}%  MBE={mbe:+,.2f}")

    # 朴素基线：用昨天的值预测今天
    naive_mae = mean_absolute_error(y_test, test["lag_1"])
    naive_mape = float(np.mean(np.abs((y_test - test["lag_1"]) / y_test)) * 100)
    results["朴素基线(昨日=今日)"] = {
        "MAE": round(naive_mae, 2),
        "RMSE": round(float(np.sqrt(mean_squared_error(y_test, test["lag_1"]))), 2),
        "MAPE": round(naive_mape, 2),
        "MBE": round(float(np.mean(y_test - test["lag_1"])), 2),
    }
    print(f"      朴素基线: MAE={naive_mae:,.2f}  MAPE={naive_mape:.2f}%")

    # 常数基线：一律预测训练集的日均值。用来回答"模型是不是只学会了均值"
    train_mean = float(y_train.mean())
    y_mean = np.full(len(y_test), train_mean)
    mean_mae = mean_absolute_error(y_test, y_mean)
    mean_mape = float(np.mean(np.abs((y_test - y_mean) / y_test)) * 100)
    results["常数基线(历史均值)"] = {
        "MAE": round(mean_mae, 2),
        "RMSE": round(float(np.sqrt(mean_squared_error(y_test, y_mean))), 2),
        "MAPE": round(mean_mape, 2),
        "MBE": round(float(np.mean(y_test - y_mean)), 2),
    }
    print(f"      常数基线: MAE={mean_mae:,.2f}  MAPE={mean_mape:.2f}%（训练集均值 {train_mean:,.2f}）")

    # 择优：只在"真正拟合过的模型"里选——常数基线没有可递推的参数，
    # 没法用于 7 天递归预测，只能作为评估参照。
    best_name = min(models, key=lambda k: results[k]["MAPE"])
    best_model = models[best_name]
    print(f"      拟合模型中最优：{best_name}（MAPE {results[best_name]['MAPE']}%）")
    best_overall = min(results, key=lambda k: results[k]["MAPE"])
    if best_overall != best_name:
        print(f"      ⚠ 但全部候选里 {best_overall} 的 MAPE 更低"
              f"（{results[best_overall]['MAPE']}%）——说明模型没跑赢基线，见报告第 8 节。")

    # ---------------- 预测未来 7 天 ----------------
    print("[5/6] 预测未来 7 天 ...")
    future = ma_forecast(df["gmv"].tolist(), best_model, df["order_date"].max(), horizon=7)
    print(future.to_string(index=False))

    # ---------------- 滚动回测 ----------------
    print("[5b/6] 滚动起点回测（6 折 × 30 天，一步预测）...")
    factories = {
        "线性回归": lambda: LinearRegression(),
        "梯度提升树(GBR)": lambda: GradientBoostingRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=3, random_state=42
        ),
    }
    bt = rolling_backtest(feat_df, factories)
    # 常数基线也纳入回测（每折用该折训练集均值）
    n = len(feat_df)
    for k in range(6):
        end = n - (5 - k) * 30
        start = end - 30
        tr, te = feat_df.iloc[:start], feat_df.iloc[start:end]
        y_true = te["gmv"].values
        y_hat = np.full(len(y_true), float(tr["gmv"].mean()))
        bt.loc[len(bt)] = {
            "fold": k + 1,
            "test_start": str(te["order_date"].min().date()),
            "test_end": str(te["order_date"].max().date()),
            "model": "常数基线(历史均值)",
            "MAE": float(mean_absolute_error(y_true, y_hat)),
            "MAPE": float(np.mean(np.abs((y_true - y_hat) / y_true)) * 100),
        }
    bt_summary = (
        bt.groupby("model")
        .agg(MAE均值=("MAE", "mean"), MAPE均值=("MAPE", "mean"), MAPE标准差=("MAPE", "std"))
        .sort_values("MAPE均值")
        .reset_index()
    )
    print(bt_summary.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    # ---------------- 出图 ----------------
    print("[6/6] 出图 ...")
    # 图 1 趋势与移动平均
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(df["order_date"], df["gmv"], lw=0.7, alpha=0.45, label="日 GMV")
    ax.plot(df["order_date"], df["ma7"], lw=1.6, label="7 日移动平均")
    ax.plot(df["order_date"], df["ma30"], lw=2.2, label="30 日移动平均")
    ax.set_title("2024 年日 GMV 与移动平均趋势")
    ax.set_ylabel("GMV（元）")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMG_DIR / "fig_01_gmv_trend.png", dpi=150)
    plt.close(fig)

    # 图 2 星期效应
    fig, ax = plt.subplots(figsize=(7, 4))
    vals = [weekday_effect.get(i, 0) for i in range(7)]
    bars = ax.bar(weekday_name, vals, color="#4C72B0")
    ax.set_title("星期效应：各星期日均 GMV")
    ax.set_ylabel("日均 GMV（元）")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v/10000:.1f}万",
                ha="center", va="bottom", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMG_DIR / "fig_02_weekday_effect.png", dpi=150)
    plt.close(fig)

    # 图 3 测试集：真实 vs 预测
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(test["order_date"], y_test, marker="o", ms=3, lw=1.4, label="真实 GMV")
    for name, yp in preds.items():
        ax.plot(test["order_date"], yp, marker=".", ms=3, lw=1.2,
                label=f"{name} (MAPE {results[name]['MAPE']}%)")
    ax.set_title("测试集最后 30 天：真实值与模型预测对比")
    ax.set_ylabel("GMV（元）")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMG_DIR / "fig_03_actual_vs_pred.png", dpi=150)
    plt.close(fig)

    # 图 4 未来 7 天预测
    tail = df.tail(60)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(tail["order_date"], tail["gmv"], lw=1.2, label="历史 GMV")
    fut_dates = pd.to_datetime(future["order_date"])
    ax.plot(fut_dates, future["pred_gmv"], marker="o", ms=4, lw=1.8,
            color="#C44E52", label=f"{best_name} 未来 7 天预测")
    ax.axvline(df["order_date"].max(), color="gray", ls="--", lw=1)
    ax.set_title("未来 7 天 GMV 预测（虚线右侧）")
    ax.set_ylabel("GMV（元）")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(IMG_DIR / "fig_04_forecast_7d.png", dpi=150)
    plt.close(fig)

    # ---------------- 落盘 ----------------
    summary = {
        "data_range": [df["order_date"].min().strftime("%Y-%m-%d"),
                       df["order_date"].max().strftime("%Y-%m-%d")],
        "days": int(len(df)),
        "daily_avg_gmv": round(float(df["gmv"].mean()), 2),
        "train_days": int(len(train)),
        "test_days": int(len(test)),
        "models": results,
        "best_model": best_name,
        "backtest": {
            "folds": 6,
            "fold_size_days": 30,
            "note": "一步预测（lag 用真实值），比递归多步预测乐观，仅用于横向比较",
            "summary": [
                {"model": r["model"], "MAE_mean": round(float(r["MAE均值"]), 2),
                 "MAPE_mean": round(float(r["MAPE均值"]), 2),
                 "MAPE_std": round(float(r["MAPE标准差"]), 2)}
                for _, r in bt_summary.iterrows()
            ],
            "per_fold": bt.to_dict(orient="records"),
        },
        "forecast_7d": future.to_dict(orient="records"),
        "forecast_7d_total": round(float(future["pred_gmv"].sum()), 2),
        "forecast_7d_avg": round(float(future["pred_gmv"].mean()), 2),
        "weekday_avg": {weekday_name[i]: round(float(v), 2) for i, v in weekday_effect.items()},
        "monthly": [
            {"month": m, "gmv": round(float(g), 2),
             "gmv_mom": None if pd.isna(mo) else round(float(mo), 4)}
            for m, g, mo in zip(monthly["month"], monthly["gmv"], monthly["gmv_mom"])
        ],
    }
    with open(EVID_DIR / "forecast_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    future.to_csv(EVID_DIR / "forecast_7d.csv", index=False, encoding="utf-8-sig")

    # 人眼可读的指标表
    lines = ["模型评估（测试集 = 最后 30 天，2024-12-02 ~ 2024-12-31）", "=" * 66,
             f"{'模型':<22}{'MAE':>12}{'RMSE':>12}{'MAPE':>9}{'MBE':>13}"]
    for k, v in results.items():
        lines.append(f"{k:<22}{v['MAE']:>12,.2f}{v['RMSE']:>12,.2f}"
                     f"{v['MAPE']:>8.2f}%{v['MBE']:>+13,.2f}")
    lines += ["", f"最优拟合模型：{best_name}", "",
              "滚动回测（6 折 × 30 天，一步预测，越小越好）", "=" * 66,
              f"{'模型':<22}{'MAE均值':>12}{'MAPE均值':>11}{'MAPE标准差':>12}"]
    for _, r in bt_summary.iterrows():
        lines.append(f"{r['model']:<22}{r['MAE均值']:>12,.2f}{r['MAPE均值']:>10.2f}%"
                     f"{r['MAPE标准差']:>12.2f}")
    lines += ["", "未来 7 天预测", "=" * 44]
    for r in summary["forecast_7d"]:
        lines.append(f"{r['order_date']}   {r['pred_gmv']:>12,.2f}")
    lines += ["", f"7 天合计：{summary['forecast_7d_total']:,.2f}",
              f"7 天日均：{summary['forecast_7d_avg']:,.2f}"]
    text = "\n".join(lines)
    (EVID_DIR / "forecast_metrics.txt").write_text(text, encoding="utf-8")
    print("\n" + text)
    print(f"\n图表已写入 {IMG_DIR}")
    print(f"指标已写入 {EVID_DIR / 'forecast_metrics.json'}")


if __name__ == "__main__":
    main()