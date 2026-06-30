# OKX AI Trader

这是一个面向 GitHub Codespaces 的 Python 3.12+ 自动交易项目骨架，默认启用模拟盘，支持通过 OKX_FLAG 切换到实盘模式。项目采用模块化结构，包含配置、行情、策略、风控、下单、数据库、日志、Telegram 通知和每日复盘。

## ⚠️ 风险提示

**本项目涉及真实资金交易，使用前请务必：**
- 先在模拟盘中充分验证策略与代码逻辑
- 确认理解所有风控配置与其含义
- 不要在无充分测试的情况下启用实盘
- 默认模式为模拟盘，任何自动下单功能都需要显式开启
- 实盘下单需同时满足：`OKX_FLAG=0` 且 `AUTO_TRADE_ENABLED=true` 且 API Key 已填
- 账户存在被清空的风险，请定期备份配置与日志

## 1. 环境准备

```bash
python3 --version
pip install -r requirements.txt
```

## 2. 配置环境变量

复制示例文件：

```bash
cp .env.example .env
```

然后根据需要编辑 .env：

- OKX_API_KEY：OKX API Key
- OKX_SECRET_KEY：OKX Secret Key
- OKX_PASSPHRASE：OKX Passphrase
- OKX_FLAG：默认 1 表示模拟盘，实盘请改为 0
- AUTO_TRADE_ENABLED：只有显式开启后才允许自动下单
- INITIAL_BALANCE：默认 15 表示初始可用资金（USDT）
- MAX_TRADE_PCT：单笔最大可用资金占比，默认 0.15 表示 15%
- TELEGRAM_ENABLED：是否启用 Telegram 通知
- TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID：Telegram 机器人配置

## 3. 运行方式

### 模拟盘

先将 .env 中改为 `OKX_FLAG=1`：

```bash
python3 main.py
```

### 实盘

请先确认：

```bash
OKX_FLAG=0
AUTO_TRADE_ENABLED=true
OKX_API_KEY=<your api key>
OKX_SECRET_KEY=<your secret key>
OKX_PASSPHRASE=<your passphrase>
```

然后运行：

```bash
python3 main.py
```

### 独立交易脚本（便于迁移）

使用 `standalone_trader.py` 可直接移到其他账户使用：

```bash
cp standalone_trader.py /path/to/new_account/
cp .env /path/to/new_account/
cd /path/to/new_account/
# 编辑 .env 填入新账户的 API Key
python3 standalone_trader.py
```

## 4. 项目结构

- config/config.py：统一配置
- core/market.py：行情获取与 WebSocket 订阅
- core/signal.py：信号生成
- core/strategy.py：做空策略
- core/order.py：订单与持仓管理
- core/executor.py：安全下单执行器
- core/risk.py：风控逻辑
- core/reports.py：每日交易复盘与报告
- core/database/sqlite.py：SQLite 持久化
- core/notification/telegram.py：Telegram 通知
- core/okx_client.py：OKX 客户端包装
- core/utils/logger.py：日志工具
- main.py：程序入口（模块化版）
- standalone_trader.py：独立交易脚本（单文件）

## 5. 核心功能

### 行情与信号
- 实时获取 BTC-USDT-SWAP 5 分钟 K 线
- WebSocket 自动重连与断线恢复（可选）
- 做空策略：基于涨幅、成交量、K 线结构评分
- 评分系统（0-100）：>90 允许，80-90 轻仓，<80 放弃

### 风控
- 逐仓、10 倍杠杆、6 USDT 每笔保证金（默认）
- 最大 2 单持仓
- 止损 2%、止盈 4%
- 连续亏损 3 单暂停 2 小时
- 当日亏损超 10 USDT 停止交易
- 单笔占账户资金 15% 上限（可配置）

### 下单
- 支持模拟盘与实盘自动切换
- 所有订单自动设置止损与止盈
- 按保证金与杠杆自动计算仓位
- 市价/限价下单支持（扩展）

### 日志与数据库
- 记录时间、币种、方向、开仓价、止盈、止损、盈亏
- 保存到 SQLite 数据库
- 同时输出到 logs/ 日志文件
- 每日自动生成交易复盘报告

### Telegram 通知
- 发现做空机会通知
- 下单成功/失败通知
- 每日复盘报告通知
- 机器人启动/停止通知

### 每日复盘
- 自动统计当日交易数、胜率、总盈亏
- 保存到数据库 `daily_reports` 表
- 生成月度总结报告
- 自动通过 Telegram 发送报告

## 6. 常见错误与排查

- ModuleNotFoundError：执行 `pip install -r requirements.txt`
- OKX_FLAG=0 但未设置 AUTO_TRADE_ENABLED=true：会被安全拦截
- 网络异常：系统会自动使用兜底数据继续运行
- Telegram 收不到消息：检查 TELEGRAM_BOT_TOKEN 与 TELEGRAM_CHAT_ID

## 7. 日志与调试

查看实时日志：

```bash
tail -f logs/main.log
tail -f logs/telegram.log
tail -f logs/report.log
```

查看数据库：

```bash
sqlite3 logs/trading.db "SELECT * FROM trades;"
sqlite3 logs/trading.db "SELECT * FROM daily_reports;"
```

## 8. 代码要求

- 使用 Python 3.12+
- 面向对象设计
- 模块化开发
- 所有代码包含中文注释
- 所有异常都有处理
- 所有配置集中在 config
- 默认启用模拟盘，实盘需要显式开启

## 9. 最终提示

本项目包含两种运行方式：
1. **模块化项目** (`main.py`)：便于维护、测试与扩展，推荐用于开发
2. **独立脚本** (`standalone_trader.py`)：单文件，便于快速部署与迁移到其他账户

选择哪种方式取决于你的需求。建议先用模块化版本在模拟盘充分测试，再用独立脚本快速移植。
