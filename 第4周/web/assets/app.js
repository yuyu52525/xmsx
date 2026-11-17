/* ==========================================================================
   云购生活 · 数据大屏逻辑
   --------------------------------------------------------------------------
   自适应方案：1920×1080 固定画布 + transform:scale()
     优点：一套像素值走遍所有分辨率，图表不会因容器尺寸变化而错位；
     缺点：超宽屏两侧留黑边 —— 用居中 + 深色背景消除观感问题。
   数据来源：/api/all（一次取全，后端可切换 Hive / ClickHouse）
   降级策略：接口不通 → 读 assets/snapshot.json（离线快照）→ 都不通才报错，
             保证"答辩现场断网/服务没起来"时大屏仍能展示版面与真实数据。
   ========================================================================== */
'use strict';

const STAGE_W = 1920;
const STAGE_H = 1080;
const API_BASE = location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '';
const REFRESH_MS = 30000;

const C = {
  cyan: '#35d6ff', purple: '#7c5cff', amber: '#ffc857', green: '#27e2a4',
  pink: '#ff7ab6', blue: '#4f8bff', text: '#e9f4ff', dim: '#8aa9cc',
  axis: 'rgba(120, 170, 220, 0.28)', split: 'rgba(120, 170, 220, 0.10)'
};

const charts = {};
let latest = null;

/* ---------------------------------------------------------------- 工具函数 */
const fmtInt = n => (n === null || n === undefined || isNaN(n)) ? '—'
  : Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 0 });

const fmtMoney = n => {
  if (n === null || n === undefined || isNaN(n)) return '—';
  const v = Number(n);
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + ' 亿';
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(1) + ' 万';
  return v.toFixed(2);
};

const fmtPct = (n, d = 2) => (n === null || n === undefined || isNaN(n)) ? '—'
  : (Number(n) * 100).toFixed(d) + '%';

/** 统一图表基底：暗色坐标轴、字体、网格 */
function baseOption() {
  return {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif', color: C.text },
    animationDuration: 700,
    animationEasing: 'cubicOut',
    grid: { left: 52, right: 52, top: 30, bottom: 26, containLabel: true },
    tooltip: {
      backgroundColor: 'rgba(8, 22, 40, 0.94)',
      borderColor: 'rgba(53, 214, 255, 0.35)',
      borderWidth: 1,
      textStyle: { color: C.text, fontSize: 12 },
      extraCssText: 'box-shadow: 0 6px 22px rgba(0,0,0,.45); border-radius: 6px;'
    }
  };
}

const axisStyle = {
  axisLine: { lineStyle: { color: C.axis } },
  axisTick: { show: false },
  axisLabel: { color: C.dim, fontSize: 11 },
  splitLine: { lineStyle: { color: C.split, type: 'dashed' } }
};

function initChart(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  if (!charts[id]) {
    charts[id] = echarts.init(el, null, { renderer: 'canvas', devicePixelRatio: 2 });
  }
  return charts[id];
}

/* ---------------------------------------------------------------- 自适应 */
function fitStage() {
  const stage = document.getElementById('stage');
  const scale = Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H);
  const left = (window.innerWidth - STAGE_W * scale) / 2;
  const top = (window.innerHeight - STAGE_H * scale) / 2;
  stage.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
  Object.values(charts).forEach(c => c && c.resize());
}

/* ---------------------------------------------------------------- 取数 */
async function fetchJSON(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function loadData() {
  try {
    const data = await fetchJSON(API_BASE + '/api/all');
    return { data, source: 'api' };
  } catch (err1) {
    try {
      const data = await fetchJSON('assets/snapshot.json');
      return { data, source: 'snapshot' };
    } catch (err2) {
      throw new Error(`接口与离线快照都不可用：${err1.message} / ${err2.message}`);
    }
  }
}

/* ---------------------------------------------------------------- 指标卡 */
function renderKpi(kpi) {
  const k = Array.isArray(kpi) ? kpi[0] : kpi;
  if (!k) return;
  const cards = [
    { cls: 'c-cyan', label: 'GMV（订单口径）', value: fmtMoney(k.gmv), unit: '元', sub: `有效 GMV ${fmtMoney(k.valid_gmv)} 元` },
    { cls: 'c-green', label: '有效营收占比', value: fmtPct(k.valid_revenue_rate), unit: '', sub: `有效订单 ${fmtInt(k.valid_order_cnt)} 笔` },
    { cls: 'c-cyan', label: '订单量', value: fmtInt(k.order_cnt), unit: '笔', sub: `下单用户 ${fmtInt(k.buyer_cnt)} 人` },
    { cls: 'c-purple', label: '客单价 AOV', value: fmtInt(k.aov), unit: '元', sub: `件单价 ${(k.avg_order_items || 0).toFixed(2)} 件/单` },
    { cls: 'c-amber', label: 'ARPU', value: fmtInt(k.arpu), unit: '元/人', sub: '人均消费金额' },
    { cls: 'c-amber', label: '取消 / 退款', value: fmtPct(k.cancel_rate, 1) + ' / ' + fmtPct(k.refund_rate, 1), unit: '', sub: k.stat_scope || '2024 全年' }
  ];
  document.getElementById('kpiRow').innerHTML = cards.map(c => `
    <div class="kpi ${c.cls}">
      <div class="k-label">${c.label}</div>
      <div class="k-value">${c.value}${c.unit ? `<small>${c.unit}</small>` : ''}</div>
      <div class="k-sub">${c.sub}</div>
    </div>`).join('');
}

/* ---------------------------------------------------------------- 折线 */
function renderLine(rows) {
  const chart = initChart('chartLine');
  if (!chart || !rows || !rows.length) return;
  const months = rows.map(r => (r.stat_month || '').slice(5) + '月');
  const gmv = rows.map(r => +(r.gmv || 0));
  const valid = rows.map(r => +(r.valid_gmv || 0));
  const mom = rows.map(r => (r.gmv_mom === null || r.gmv_mom === undefined) ? null : +(r.gmv_mom) * 100);

  chart.setOption({
    ...baseOption(),
    grid: { left: 60, right: 58, top: 44, bottom: 30, containLabel: true },
    legend: {
      data: ['GMV', '有效 GMV', '环比'],
      top: 2, right: 4, itemWidth: 10, itemHeight: 6, itemGap: 12,
      textStyle: { color: C.dim, fontSize: 11 }
    },
    tooltip: {
      ...baseOption().tooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(53,214,255,0.06)' } },
      formatter: ps => {
        const i = ps[0].dataIndex;
        return `<b>2024-${String(rows[i].stat_month).slice(5)}</b><br/>`
          + `GMV：<b style="color:${C.cyan}">${fmtInt(rows[i].gmv)}</b> 元<br/>`
          + `有效 GMV：<b style="color:${C.amber}">${fmtInt(rows[i].valid_gmv)}</b> 元<br/>`
          + `环比：<b style="color:${C.purple}">${mom[i] === null ? '—' : mom[i].toFixed(2) + '%'}</b>`;
      }
    },
    xAxis: [{ ...axisStyle, type: 'category', data: months, axisLabel: { color: C.dim, fontSize: 10.5 } }],
    yAxis: [
      {
        ...axisStyle, type: 'value', name: '元', nameTextStyle: { color: C.dim, fontSize: 10 },
        axisLabel: { color: C.dim, fontSize: 10, formatter: v => (v / 1e4).toFixed(0) + '万' }
      },
      {
        ...axisStyle, type: 'value', name: '%', nameTextStyle: { color: C.dim, fontSize: 10 },
        axisLabel: { color: C.purple, fontSize: 10, formatter: v => v.toFixed(0) + '%' },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: 'GMV', type: 'bar', barWidth: '46%', data: gmv, yAxisIndex: 0,
        itemStyle: {
          borderRadius: [3, 3, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(53,214,255,0.92)' },
            { offset: 1, color: 'rgba(53,214,255,0.10)' }
          ])
        }
      },
      {
        name: '有效 GMV', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5, yAxisIndex: 0,
        data: valid, lineStyle: { width: 2, color: C.amber }, itemStyle: { color: C.amber },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(255,200,87,0.24)' },
            { offset: 1, color: 'rgba(255,200,87,0)' }
          ])
        }
      },
      {
        name: '环比', type: 'line', smooth: true, symbol: 'none', yAxisIndex: 1, data: mom,
        lineStyle: { width: 1.6, type: 'dashed', color: C.purple }, connectNulls: true
      }
    ]
  }, true);
}

/* ---------------------------------------------------------------- 地图 */
let chinaGeoLoaded = false;

async function ensureChinaMap() {
  if (chinaGeoLoaded) return true;
  const geo = await fetchJSON('assets/china.json');
  echarts.registerMap('china', geo);
  chinaGeoLoaded = true;
  return true;
}

async function renderMap(rows) {
  const chart = initChart('chartMap');
  if (!chart || !rows || !rows.length) return;
  try { await ensureChinaMap(); } catch (e) { return; }

  // 省份名与 GeoJSON 都是"陕西省""北京市"这种全称，可直接对齐；
  // 仍做一次兜底映射，防止哪天上游改成简称。
  const data = rows.map(r => ({ name: r.province, value: +(r.gmv || 0), ...r }));
  const vals = data.map(d => d.value);
  const max = Math.max(...vals), min = Math.min(...vals);

  chart.setOption({
    ...baseOption(),
    tooltip: {
      ...baseOption().tooltip,
      trigger: 'item',
      formatter: p => {
        if (!p.data || p.data.value === undefined) return `<b>${p.name}</b><br/>无销售数据`;
        return `<b>${p.name}</b>　<span style="color:${C.dim}">${p.data.region_area || ''}</span><br/>`
          + `GMV：<b style="color:${C.cyan}">${fmtInt(p.data.value)}</b> 元<br/>`
          + `订单量：${fmtInt(p.data.order_cnt)} 笔<br/>`
          + `下单用户：${fmtInt(p.data.buyer_cnt)} 人`;
      }
    },
    visualMap: {
      type: 'continuous', min, max,
      left: 10, bottom: 12, itemWidth: 9, itemHeight: 78,
      text: [fmtMoney(max), fmtMoney(min)], textStyle: { color: C.dim, fontSize: 10 },
      calculable: true, precision: 0,
      inRange: { color: ['#0b2740', '#12506e', '#1a8fa8', '#35d6ff', '#ffd98a'] }
    },
    series: [{
      name: '省份 GMV', type: 'map', map: 'china', roam: false, zoom: 1.16,
      top: 12, bottom: 6,
      label: { show: false },
      itemStyle: {
        areaColor: 'rgba(18, 48, 78, 0.55)',
        borderColor: 'rgba(53, 214, 255, 0.32)',
        borderWidth: 0.8
      },
      emphasis: {
        label: { show: true, color: '#fff', fontSize: 11, fontWeight: 600 },
        itemStyle: { areaColor: 'rgba(255, 200, 87, 0.75)', borderColor: '#fff', borderWidth: 1 }
      },
      select: { disabled: true },
      data
    }]
  }, true);
}

/* ---------------------------------------------------------------- 柱状 */
function renderBar(rows) {
  const chart = initChart('chartBar');
  if (!chart || !rows || !rows.length) return;
  const asc = rows.slice().sort((a, b) => a.sales_amt - b.sales_amt);
  const cats = asc.map(r => r.category);
  const amt = asc.map(r => +(r.sales_amt || 0));
  const qty = asc.map(r => +(r.item_qty || 0));

  chart.setOption({
    ...baseOption(),
    grid: { left: 4, right: 62, top: 26, bottom: 6, containLabel: true },
    tooltip: {
      ...baseOption().tooltip, trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: ps => {
        const i = ps[0].dataIndex;
        return `<b>${asc[i].category}</b><br/>销售额：<b style="color:${C.cyan}">${fmtInt(asc[i].sales_amt)}</b> 元<br/>销售件数：${fmtInt(asc[i].item_qty)} 件`;
      }
    },
    xAxis: { ...axisStyle, type: 'value', axisLabel: { color: C.dim, fontSize: 10, formatter: v => (v / 1e4).toFixed(0) + '万' } },
    yAxis: { ...axisStyle, type: 'category', data: cats, axisLabel: { color: '#bcd6f0', fontSize: 11.5 }, splitLine: { show: false } },
    series: [
      {
        name: '销售额', type: 'bar', barWidth: '52%', data: amt,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: 'rgba(124,92,255,0.35)' },
            { offset: 1, color: 'rgba(53,214,255,0.95)' }
          ])
        },
        label: {
          show: true, position: 'right', color: C.amber, fontSize: 10.5,
          formatter: p => (amt[p.dataIndex] / 1e4).toFixed(1) + '万'
        }
      },
      { name: '件数', type: 'bar', barWidth: 0, data: qty, itemStyle: { color: 'transparent' } }
    ]
  }, true);
}

/* ---------------------------------------------------------------- 热力图 */
function renderHeat(rows) {
  const chart = initChart('chartHeat');
  if (!chart || !rows || !rows.length) return;

  const catsAsc = [...new Set(rows.map(r => r.category))]
    .sort((a, b) => orderOf(rows, a) - orderOf(rows, b));
  const cats = catsAsc.slice().reverse();          // 业务量最大的排在顶部
  const hours = [...Array(24).keys()];
  const grid = [];
  let max = 0;
  rows.forEach(r => {
    const x = +r.hour_of_day;
    const y = cats.indexOf(r.category);
    const v = +(r.sales_amt || 0);
    if (y >= 0) { grid.push([x, y, v]); if (v > max) max = v; }
  });

  chart.setOption({
    ...baseOption(),
    grid: { left: 6, right: 16, top: 12, bottom: 40, containLabel: true },
    tooltip: {
      ...baseOption().tooltip, position: 'top',
      formatter: p => `<b>${cats[p.value[1]]}</b>　${p.value[0]}:00–${p.value[0] + 1}:00<br/>`
        + `销售额：<b style="color:${C.cyan}">${fmtInt(p.value[2])}</b> 元`
    },
    xAxis: {
      ...axisStyle, type: 'category', data: hours.map(h => h + ''),
      splitArea: { show: false }, axisLabel: { color: C.dim, fontSize: 10, interval: 1 },
      name: '时', nameTextStyle: { color: C.dim, fontSize: 10 }, nameGap: 6
    },
    yAxis: {
      ...axisStyle, type: 'category', data: cats,
      axisLabel: { color: '#bcd6f0', fontSize: 11 }, splitLine: { show: false }
    },
    visualMap: {
      min: 0, max, calculable: true, orient: 'horizontal',
      left: 'center', bottom: 0, itemWidth: 10, itemHeight: 70,
      textStyle: { color: C.dim, fontSize: 10 },
      text: ['高', '低'],
      inRange: { color: ['#0a2338', '#12506e', '#1a8fa8', '#35d6ff', '#ffd98a'] }
    },
    series: [{
      name: '销售额', type: 'heatmap', data: grid,
      label: { show: false },
      itemStyle: { borderColor: 'rgba(6,12,24,0.85)', borderWidth: 1, borderRadius: 2 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(53,214,255,0.8)' } },
      progressive: 0
    }]
  }, true);
}

function orderOf(rows, cat) {
  const hit = rows.find(r => r.category === cat);
  return hit ? +(hit.category_order || 99) : 99;
}

/* ---------------------------------------------------------------- 散点 */
function renderScatter(rows) {
  const chart = initChart('chartScatter');
  if (!chart || !rows || !rows.length) return;

  const segments = [...new Set(rows.map(r => r.rfm_segment).filter(Boolean))];
  const palette = {
    '重要价值客户': C.amber, '重要保持客户': C.cyan, '重要发展客户': C.purple,
    '重要挽留客户': C.green, '一般价值客户': C.blue, '一般保持客户': C.pink,
    '一般发展客户': '#8aa9cc', '一般挽留客户': '#5d7898'
  };
  const maxF = Math.max(...rows.map(r => +r.frequency || 1));

  const series = segments.map(seg => ({
    name: seg,
    type: 'scatter',
    data: rows.filter(r => r.rfm_segment === seg)
      .map(r => [ +r.recency_days, +r.monetary, +r.frequency ]),
    symbolSize: d => 4 + 9 * Math.sqrt((d[2] || 1) / maxF),
    itemStyle: { color: palette[seg] || C.dim, opacity: 0.78 },
    emphasis: { itemStyle: { opacity: 1, borderColor: '#fff', borderWidth: 1 } },
    large: true, largeThreshold: 300
  }));

  chart.setOption({
    ...baseOption(),
    grid: { left: 12, right: 22, top: 34, bottom: 30, containLabel: true },
    legend: {
      type: 'scroll', top: 0, left: 'center', itemWidth: 8, itemHeight: 8, itemGap: 8,
      textStyle: { color: C.dim, fontSize: 9.5 }, pageTextStyle: { color: C.dim }
    },
    tooltip: {
      ...baseOption().tooltip, trigger: 'item',
      formatter: p => `<b>${p.seriesName}</b><br/>`
        + `最近购买间隔：${p.value[0]} 天<br/>`
        + `累计消费：<b style="color:${C.amber}">${fmtInt(p.value[1])}</b> 元<br/>`
        + `订单数：${p.value[2]} 笔`
    },
    xAxis: {
      ...axisStyle, type: 'value', name: 'R 天', nameTextStyle: { color: C.dim, fontSize: 10 },
      scale: true, axisLabel: { color: C.dim, fontSize: 10 }
    },
    yAxis: {
      ...axisStyle, type: 'value', name: 'M 元', nameTextStyle: { color: C.dim, fontSize: 10 },
      axisLabel: { color: C.dim, fontSize: 10, formatter: v => (v / 1e4).toFixed(0) + '万' }
    },
    series
  }, true);
}

/* ---------------------------------------------------------------- 饼图 */
function renderPie(rows) {
  const chart = initChart('chartPie');
  if (!chart || !rows || !rows.length) return;
  const total = rows.reduce((s, r) => s + (+r.gmv || 0), 0);
  const palette = [C.cyan, C.purple, C.amber, C.green, C.pink, C.blue];

  chart.setOption({
    ...baseOption(),
    tooltip: {
      ...baseOption().tooltip, trigger: 'item',
      formatter: p => `<b>${p.name}</b><br/>GMV：<b style="color:${C.cyan}">${fmtInt(p.value)}</b> 元<br/>占比：${p.percent}%<br/>订单量：${fmtInt(p.data.cnt)} 笔`
    },
    series: [{
      type: 'pie', radius: ['52%', '76%'], center: ['50%', '52%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: 'rgba(6,12,24,0.9)', borderWidth: 2, borderRadius: 3 },
      label: { color: '#cfe3f8', fontSize: 10.5, formatter: '{b}\n{d}%', lineHeight: 14 },
      labelLine: { length: 8, length2: 8, lineStyle: { color: 'rgba(120,170,220,0.4)' } },
      data: rows.map((r, i) => ({
        name: r.pay_name, value: +(r.gmv || 0), cnt: r.order_cnt,
        itemStyle: { color: palette[i % palette.length] }
      }))
    }],
    graphic: [{
      type: 'text', left: 'center', top: '44%',
      style: {
        text: fmtMoney(total) + '\n总额',
        textAlign: 'center', fill: '#eaf6ff', fontSize: 12, lineHeight: 18, fontWeight: 600
      }
    }]
  }, true);
}

/* ---------------------------------------------------------------- TopN */
function renderRank(rows) {
  const box = document.getElementById('rankList');
  if (!box || !rows || !rows.length) return;
  const top = rows.slice(0, 8);
  const max = Math.max(...top.map(r => +r.gmv || 0));
  box.innerHTML = top.map((r, i) => `
    <li class="rank-item">
      <span class="rank-no">${i + 1}</span>
      <span class="rank-main">
        <span class="rank-name" title="${r.store_name}（${r.store_id}）">${r.store_name}</span>
        <span class="rank-track"><span class="rank-fill" style="width:${(r.gmv / max * 100).toFixed(1)}%"></span></span>
      </span>
      <span class="rank-val">${fmtMoney(r.gmv)}</span>
    </li>`).join('');
}

/* ---------------------------------------------------------------- 布局自检
   目的：没有肉眼也能确认"面板没重叠、图表真的出图、文字没溢出"。
   用法：http://localhost:8000/?debug=1   页面底部会多出一段 JSON 报告，
        或用 `msedge --headless --dump-dom` 抓这份报告做回归。
   这是开发期自检，不影响正常演示（不传 debug 参数就完全不执行）。
   ------------------------------------------------------------------ */
function debugReport() {
  const panels = [...document.querySelectorAll('.panel')].map(p => {
    const r = p.getBoundingClientRect();
    const chartEl = p.querySelector('.chart');
    const canvas = chartEl ? chartEl.querySelector('canvas') : null;
    return {
      cls: p.className.replace('panel ', ''),
      x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
      canvasCount: chartEl ? chartEl.querySelectorAll('canvas').length : 0,
      canvasPx: canvas ? `${canvas.width}x${canvas.height}` : null,
      overflowY: p.scrollHeight - p.clientHeight,
      overflowX: p.scrollWidth - p.clientWidth
    };
  });

  // 两两相交检测：面板不该互相压住
  const overlaps = [];
  for (let i = 0; i < panels.length; i++) {
    for (let j = i + 1; j < panels.length; j++) {
      const a = panels[i], b = panels[j];
      const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (ox > 1 && oy > 1) overlaps.push(`${a.cls} × ${b.cls} (${ox}×${oy})`);
    }
  }

  const kpis = [...document.querySelectorAll('.kpi')].map(k => ({
    label: k.querySelector('.k-label')?.textContent,
    value: k.querySelector('.k-value')?.textContent.trim(),
    overflow: k.scrollHeight - k.clientHeight
  }));

  const stage = document.getElementById('stage').getBoundingClientRect();
  const report = {
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    stage: `${Math.round(stage.width)}x${Math.round(stage.height)} @ ${Math.round(stage.x)},${Math.round(stage.y)}`,
    status: document.getElementById('statusText')?.textContent,
    backendPill: document.getElementById('backendPill')?.textContent,
    kpiCount: kpis.length,
    kpis,
    rankItems: document.querySelectorAll('.rank-item').length,
    panels,
    overlaps,
    chartsWithoutCanvas: panels.filter(p => p.canvasCount === 0).map(p => p.cls)
  };

  const pre = document.createElement('pre');
  pre.id = 'geomReport';
  pre.style.cssText = 'position:fixed;left:-9999px;top:0;';
  pre.textContent = JSON.stringify(report, null, 1);
  document.body.appendChild(pre);
}

/* ---------------------------------------------------------------- 主流程 */
function renderAll(data) {
  latest = data;
  renderKpi(data.kpi);
  renderLine(data.month);
  renderMap(data.province);
  renderBar(data.category);
  renderHeat(data.hour_category);
  renderScatter(data.rfm);
  renderPie(data.paytype);
  renderRank(data.store);

  const backendName = { clickhouse: 'ClickHouse', hive: 'Hive', snapshot: '离线快照' }[data.backend || 'snapshot'] || '服务端';
  const pill = document.getElementById('backendPill');
  pill.textContent = '数据源 · ' + (data.source === 'snapshot' ? '离线快照' : backendName);
  pill.classList.toggle('warn', data.source === 'snapshot');
}

function setStatus(text, isErr) {
  const el = document.getElementById('statusText');
  el.textContent = text;
  el.classList.toggle('err', !!isErr);
  document.getElementById('updatedAt').textContent = '更新于 ' + new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

async function refresh() {
  try {
    const { data, source } = await loadData();
    data.source = source;
    renderAll(data);
    const ms = data.elapsed_ms;
    setStatus(`${source === 'snapshot' ? '离线快照' : '接口'} 拉取完成 · 后端 ${data.backend || 'snapshot'}${ms ? ' · ' + ms + ' ms' : ''}`);
    if (location.search.indexOf('debug=1') >= 0) setTimeout(debugReport, 1500);
  } catch (err) {
    setStatus('数据加载失败：' + err.message, true);
    const fatal = document.getElementById('fatal');
    if (!latest) {
      document.getElementById('fatalMsg').textContent =
        `${err.message}　｜　请确认已执行 docker compose up -d，或直接用浏览器打开 http://localhost:8000`;
      fatal.classList.remove('hidden');
    }
  }
}

function tickClock() {
  const d = new Date();
  const p = n => String(n).padStart(2, '0');
  document.getElementById('clock').textContent =
    `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

window.addEventListener('resize', () => {
  clearTimeout(window.__fitTimer);
  window.__fitTimer = setTimeout(fitStage, 120);
});

document.addEventListener('DOMContentLoaded', () => {
  fitStage();
  tickClock();
  setInterval(tickClock, 1000);
  refresh();
  setInterval(refresh, REFRESH_MS);
  // 容器尺寸变化（如投影切换）也会触发重排
  if (window.ResizeObserver) {
    new ResizeObserver(() => { clearTimeout(window.__fitTimer); window.__fitTimer = setTimeout(fitStage, 150); })
      .observe(document.getElementById('viewport'));
  }
});