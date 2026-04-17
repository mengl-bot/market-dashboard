# 美股指数专业看板 V3

## 全市场宽度

宽度模块已从占位卡片升级为成分股级别 A/D：

- 标普500涨跌比：从 Wikipedia 获取 S&P 500 成分股，使用 yfinance 批量下载最近 2 个交易日收盘价，计算上涨/下跌/持平家数。
- 纳指100涨跌比：从 Wikipedia 获取 Nasdaq-100 成分股，使用同一套接口计算 A/D；若来源短期不可用，会降级到最近缓存。
- 成分股列表缓存 86400 秒。
- 宽度行情结果使用 `CACHE_TTL_QUOTE`，并限制在 300 到 900 秒之间。
- 实时获取失败时，页面显示“使用缓存数据”；没有缓存时仅该卡片显示暂无数据，不影响其他模块。

本地快速验证：

```powershell
python -m compileall app.py data_repository providers services ui utils
streamlit run app.py
```

本项目是一个本地可运行的 Python Streamlit 专业看板，用于跟踪 NASDAQ Composite、S&P 500、宏观风险指标、七巨头表现、市场宽度和盘后决策信号。

## V3 重点

- 顶部终端状态栏：ET 时间、LIVE/MOCK、Risk ON/OFF、VIX、10Y、Breadth 快速状态。
- 图表增强：十字准星、双指数差值 hover、近期高低点、面积图切换、回撤阴影。
- 七巨头升级：强弱排名、权重贡献、热力图颜色。
- 市场判断升级：趋势、宽度、波动、驱动、风险五维结论。
- AI 盘后简报格式：Summary / Driver / Watchlist。
- UI 风格：更接近 Bloomberg Terminal / institutional dashboard。

## 本地运行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Render 部署

仓库已包含 Render Blueprint 配置：

- `render.yaml`
- `runtime.txt`
- `requirements.txt`

在 Render 中选择 Blueprint 部署，或创建 Web Service 后使用以下配置：

```bash
Build Command:
pip install --upgrade pip && pip install -r requirements.txt

Start Command:
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true --browser.gatherUsageStats false
```

默认环境变量已在 `render.yaml` 中配置：

- `MARKET_DATA_PROVIDER=yfinance`
- `CACHE_DIR=/tmp/us_index_dashboard_cache`
- `LOG_DIR=/tmp/us_index_dashboard_logs`
- `CACHE_TTL_QUOTE=300`
- `CACHE_TTL_MACRO=900`
- `CACHE_TTL_STATS=86400`

如需 Alpha Vantage 备用数据源，在 Render 控制台中设置：

```text
ALPHA_VANTAGE_API_KEY=你的 Key
```

Render 的 `/tmp` 是实例本地临时存储，适合当前缓存和日志用途；服务重启后会重新生成缓存。

PowerShell 示例：

```powershell
$env:MARKET_DATA_PROVIDER="yfinance"
$env:ALPHA_VANTAGE_API_KEY="你的 Alpha Vantage API Key"
streamlit run app.py
```

强制使用 mock：

```powershell
$env:MARKET_DATA_PROVIDER="mock"
streamlit run app.py
```

## 数据源稳定性设计

数据层已收敛到 `data_repository/`。UI 入口只调用 `DataRepository.load_market_data()`，provider 调用不散落在 service 或 UI 中。

当前策略：

- Primary：Yahoo Finance / yfinance。
- Secondary：Alpha Vantage。仅在配置 `ALPHA_VANTAGE_API_KEY` 或 `MARKET_API_KEY` 后启用。
- Fallback：Mock Data。
- 支持部分成功：单个 symbol 失败不会导致整页直接切到全 mock。
- 同一轮页面渲染共享同一份原始数据：图表、指标、摘要都使用 repository 返回的 `datasets`。
- Yahoo 请求使用 `yf.download(..., tickers=[...])` 批量下载，降低逐个 `Ticker.history()` 触发限流的概率。
- UI 顶部只显示简洁状态，例如“实时数据部分可用”“部分标的获取失败，已使用缓存或降级数据”“当前使用 mock 数据的模块列表”。
- 技术细节写入 `logs/app.log`，不直接倾倒到页面。

## 缓存机制说明

缓存为双层结构：

- 内存缓存：当前 Python 进程内有效。
- 磁盘缓存：保存到项目 `cache/` 目录，默认使用 pickle 文件。

支持环境变量：

```powershell
$env:CACHE_DIR="cache"
$env:CACHE_TTL_QUOTE="300"
$env:CACHE_TTL_MACRO="900"
$env:CACHE_TTL_STATS="86400"
```

默认 TTL：

- 实时行情类：300 秒。
- 债券收益率和 VIX 等宏观类：900 秒。
- 统计类历史数据兜底：86400 秒。

当实时行情缓存过期且真实 provider 失败时，repository 会尝试读取统计级缓存，保证 52 周区间、3 月均量、20 日波动等历史统计尽量保留。若仍没有缓存，才对失败 symbol 使用 mock。

## 日志

日志文件：

```text
logs/app.log
```

记录内容包括：

- provider 请求。
- provider 批量失败或单 symbol 失败。
- 缓存命中、过期、写入。
- Alpha Vantage fallback。
- mock fallback。

## Debug 开关

页面左侧 sidebar 提供 `Data debug` 开关。

也可以用环境变量默认打开：

```powershell
$env:DEBUG_DATA="1"
streamlit run app.py
```

Debug 面板会展示：

- 当前 provider 偏好。
- cache 目录。
- quote / macro / stats TTL。
- 每个模块、symbol、provider、数据状态、缓存层、行数。

状态字段含义：

- `live`：本轮从真实 provider 获取。
- `cache`：从有效缓存获取。
- `stale_cache`：真实 provider 失败后使用过期缓存兜底。
- `mock`：真实 provider 和缓存均不可用后使用 mock。

## 本地测试方法

语法检查：

```powershell
python -m compileall app.py data_repository providers services ui utils
```

强制 mock 验证页面稳定性：

```powershell
$env:MARKET_DATA_PROVIDER="mock"
python -c "from data_repository import DataRepository; r=DataRepository().load_market_data(); print(r.source_name, len(r.datasets), r.warning)"
```

验证缓存读写：

```powershell
python -c "import pandas as pd; from utils.config import load_config; from utils.logging_config import setup_logging; from data_repository.cache import MarketDataCache; c=load_config(); cache=MarketDataCache(c.cache_dir, setup_logging(c.log_dir)); cache.set('debug-cache-test', pd.DataFrame({'date':[pd.Timestamp.today()],'close':[1.0]}), 'test'); print(cache.get('debug-cache-test', 300)[1])"
```

输出 `memory` 或 `disk` 表示缓存命中。真实 provider 成功获取的数据会写入行情缓存；mock fallback 默认不写入真实行情缓存，避免污染后续 live 数据。

## 结构说明

- `data_repository/`：统一数据入口、双层缓存、TTL、fallback、debug 诊断。
- `providers/`：Yahoo、Alpha Vantage、Mock 数据源适配和标准化。
- `services/analytics.py`：收益率、波动、宏观、七巨头和宽度计算。
- `services/summary.py`：中文交易员简报生成。
- `ui/`：Streamlit 组件、Plotly 图表和样式。
- `utils/`：配置读取和日志初始化。
