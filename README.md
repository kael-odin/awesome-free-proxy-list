<div align="center">

# 🛰️ Free Proxy List · 免费代理列表

**每日自动验证的免费代理列表** · HTTP / HTTPS / SOCKS4 / SOCKS5 · 含 GeoIP 国家归属与延迟分档

[![Update](https://github.com/kael-odin/awesome-free-proxy-list/actions/workflows/update.yml/badge.svg)](https://github.com/kael-odin/awesome-free-proxy-list/actions/workflows/update.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Proxies](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/kael-odin/awesome-free-proxy-list/main/proxies/summary.json&query=$.counts.all.working&label=working&color=brightgreen)](proxies/summary.json)
[![Last Update](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/kael-odin/awesome-free-proxy-list/main/proxies/summary.json&query=$.updated_utc&label=updated&color=blue)](proxies/summary.json)
[![GitHub stars](https://img.shields.io/github/stars/kael-odin/awesome-free-proxy-list?style=social)](https://github.com/kael-odin/awesome-free-proxy-list/stargazers)

🌐 [在线仪表盘 / Live Dashboard](https://kael-odin.github.io/awesome-free-proxy-list/) · 🔗 [Clash 订阅 / Clash sub](https://kael-odin.github.io/awesome-free-proxy-list/data/clash/all.yaml) · 📦 [全部代理 / All proxies](proxies/all.txt) · 📊 [统计 / Summary](proxies/summary.json)

</div>

---

> [English](#-english) · [中文](#-中文)
>
> 本仓库聚合 10+ 个公开代理来源，由 GitHub Actions **每日自动验证**可用性（HTTP/HTTPS/SOCKS4/SOCKS5），标注国家归属与延迟分档，输出多种格式。**零服务器成本**，开箱即用。

## 🌟 特性

- ⚡ **每日自动验证** — GitHub Actions 定时抓取 + 实测，仅保留可用代理
- 🌍 **GeoIP 国家归属** — 每个代理标注国家与代码（纯 Python 离线 MaxMind GeoLite2，无需 license key）
- 🚦 **延迟分档** — 按延迟排序，分 fast / medium / slow 三档，提供最快子集
- 📦 **多格式输出** — `txt` / `json` / `csv` / 按国家分文件 / 最快子集
- 🖥️ **在线仪表盘** — 纯静态 SPA，搜索 / 筛选 / 排序 / 复制 / 一键下载，中英双语 + 暗色模式
- 🔗 **一键导入客户端** — 预生成 Clash / V2Ray / Surge 订阅链接，粘贴即用，支持按类型/国家分组
- ⚡ **零依赖消费** — 任一 `proxies/*.txt` 都是 `host:port` 一行一个，`curl` 直接用

## 📊 实时统计 / Stats

<!-- STATS:START -->
Last update (UTC): **2026-07-10T12:09:34+00:00**

| Type | Working | Total Candidates |
|---|---:|---:|
| HTTP | 422 | 2000 |
| HTTPS | 259 | 2000 |
| SOCKS4 | 179 | 2000 |
| SOCKS5 | 532 | 2000 |
| ALL | 1058 | 6000 |
<!-- STATS:END -->

> 统计由 `scripts/update.py` 在每次运行后自动注入，无需手工维护。

## 📥 下载使用 / Quick start

所有产物生成在 `proxies/` 目录：

| 文件 | 内容 |
|---|---|
| `proxies/all.txt` | 全部可用代理（按延迟排序去重） |
| `proxies/http.txt` · `https.txt` | HTTP / HTTPS 正向代理 |
| `proxies/socks4.txt` · `socks5.txt` | SOCKS4 / SOCKS5 代理 |
| `proxies/top-http.txt` · `top-https.txt` · `top-socks5.txt` | 最快子集（默认前 100） |
| `proxies/all.csv` | CSV（含国家/延迟/档位/来源），可导入 Excel/pandas |
| `proxies/json/*.json` | 结构化 JSON，每项含 `ip/port/type/country/country_code/latency_ms/tier/source` |
| `proxies/by-country/<CC>.txt` | 按国家代码分文件（如 `US.txt`、`CN.txt`） |
| `proxies/clash/*.yaml` | **Clash/Mihomo 配置**（含 proxy-groups 按类型/国家分组 + AUTO 测速 + rules） |
| `proxies/v2ray/all.txt` | **V2Ray base64 订阅**（一行 base64，包含全部 URL） |
| `proxies/links/*.txt` | **链接列表**（`http://ip:port`、`socks5://ip:port`，通用） |
| `proxies/subscriptions.json` | 订阅清单（所有订阅的 Pages/raw URL + 导入指南） |
| `proxies/summary.json` | 汇总统计（含 `by_tier`/`by_country`/`top_fastest`/`sources`） |

### curl 一行下载

```bash
# 全部可用代理
curl -s https://raw.githubusercontent.com/kael-odin/awesome-free-proxy-list/main/proxies/all.txt | head

# 最快的 HTTP 代理
curl -s https://raw.githubusercontent.com/kael-odin/awesome-free-proxy-list/main/proxies/top-http.txt | head

# 结构化 JSON（含国家/延迟）
curl -s https://raw.githubusercontent.com/kael-odin/awesome-free-proxy-list/main/proxies/json/all.json | head
```

### Python `requests`

```python
import requests

# 从 all.txt 随便取一行
proxy = "http://IP:PORT"
proxies = {"http": proxy, "https": proxy}

resp = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
print(resp.text)
```

### Node.js (`axios` + `https-proxy-agent`)

```js
import axios from "axios";
import { HttpsProxyAgent } from "https-proxy-agent";

const agent = new HttpsProxyAgent("http://IP:PORT");
const { data } = await axios.get("https://httpbin.org/ip", { httpsAgent: agent, timeout: 10000 });
console.log(data);
```

### 在线仪表盘

不想下载？直接用浏览器打开 **[在线仪表盘](https://kael-odin.github.io/awesome-free-proxy-list/)**：
搜索 IP / 国家 / 端口，按类型、国家、延迟档筛选，一键复制或下载当前结果。支持暗色模式与中英双语切换。

### 🔗 一键导入代理软件（Clash Verge / V2RayN / Surge）

本仓库为常见代理客户端预生成订阅文件，**复制链接粘贴即可导入**，无需手动逐条添加：

| 客户端 | 订阅链接 | 格式 |
|---|---|---|
| **Clash Verge / Mihomo** | `https://kael-odin.github.io/awesome-free-proxy-list/data/clash/all.yaml` | Clash YAML（HTTP+SOCKS5） |
| Clash Verge（仅 HTTP） | `https://kael-odin.github.io/awesome-free-proxy-list/data/clash/http.yaml` | Clash YAML |
| **V2RayN / V2Ray** | `https://kael-odin.github.io/awesome-free-proxy-list/data/v2ray/all.txt` | base64 订阅 |
| Surge / 通用链接 | `https://kael-odin.github.io/awesome-free-proxy-list/data/links/http.txt` | `http://ip:port` 列表 |

**导入步骤**：
1. **Clash Verge**：打开 → 配置（订阅）→ 粘贴上面的 Clash YAML 链接 → 更新 → 在代理页选中该配置 → 选「🚀 PROXY」或「♻️ AUTO」分组（AUTO 会自动测速选最快节点）
2. **V2RayN**：订阅 → 订阅设置 → 粘贴 v2ray base64 链接 → 更新（注意勾选 SOCKS5）
3. **Surge**：策略 → 新建外部代理列表 → 粘贴 links/http.txt 链接

> 仪表盘「🔗 一键导入代理软件」区也有全部链接 + 一键复制按钮 + 导入指南。免费代理质量参差，建议用「♻️ AUTO」自动测速组。

## ⚙️ 工作原理

```
sources.txt (10+ 公开来源)
        │  scrape (aiohttp, 并发)
        ▼
候选代理池 (ip:port 去重)
        │  validate (HTTP/HTTPS/SOCKS, 测延迟)
        ▼
可用代理 + 延迟 (ms)
        │  enrich (GeoIP 国家归属)
        ▼
按延迟排序 → txt / json / csv / by-country / top-*
        │  注入 README stats + 同步 docs/data/
        ▼
GitHub Actions commit & deploy Pages (每日)
```

- 来源定义：`scripts/sources.txt`（一行一个 `<url> [http|https|socks4|socks5|mixed]`）
- 核心脚本：`scripts/update.py`（抓取 → 验证 → 富化 → 多格式输出）
- 国家识别：`scripts/geoip_lookup.py`（`geoip2` + 社区镜像 GeoLite2-Country.mmdb，免 license key，懒加载 + 7 天缓存 + 失败降级）
- 单代理诊断：`scripts/check.py IP:PORT`（连通性 / 延迟 / 出口 IP / 匿名性 / HTTPS CONNECT）
- 快速烟测：`python scripts/test_proxies.py --type http --limit 5`

## 🖥️ 本地运行

```bash
git clone https://github.com/kael-odin/awesome-free-proxy-list.git
cd awesome-free-proxy-list
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash  # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python scripts/update.py         # 全量；小规模试跑可设环境变量（见下）
```

环境变量（均为可选）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `PROXY_TIMEOUT_SEC` | `8` | 单代理测试超时（秒） |
| `PROXY_CONCURRENCY` | `200` | 最大并发验证数 |
| `PROXY_MAX_PER_TYPE` | `2000` | 每类型候选上限 |
| `PROXY_TOP_HTTP_LIMIT` | `100` | 最快 HTTP 子集大小 |
| `PROXY_GEOIP_ENABLE` | `1` | `0`/`false` 关闭 GeoIP |
| `PROXY_GEOIP_DB` | （缓存） | 指定本地 `.mmdb` 路径，跳过下载 |

小规模试跑示例：

```bash
PROXY_MAX_PER_TYPE=50 PROXY_CONCURRENCY=50 python scripts/update.py
```

### 本地预览仪表盘

```bash
# 方式 1：Python 内置静态服务器
cd docs && python -m http.server 8088   # 浏览器打开 http://localhost:8088

# 方式 2：用 .claude/launch.json 的 fpl-preview 配置（如使用 Claude Code 预览工具）
```

## 🌐 启用 GitHub Pages 仪表盘

仪表盘代码在 `docs/`，数据在 `docs/data/`（由 `update.py` 自动同步）。部署只需一次设置：

1. 仓库 **Settings → Pages → Build and deployment → Source** 选 **GitHub Actions**
2. 下次 `update.yml` 运行会自动部署 `docs/` 到 `https://<user>.github.io/awesome-free-proxy-list/`

> workflow 已配置 `deploy-pages` job，无需额外 action。

## ❓ FAQ

- **为什么 `socks4.txt` / `socks5.txt` 有时是空的？**
  公共 SOCKS 代理极不稳定。脚本只发布**真实通过** HTTP/HTTPS 请求的代理，所以某些时段 SOCKS 为 0 属正常。

- **`https.txt` 为何在严格 HTTPS 验证下非空？**
  `https.txt` 里每个代理至少通过了 HTTP 测试。多数 HTTP 正向代理也能通过 CONNECT 处理 HTTPS；当没有任何代理显式通过 HTTPS 测试时，HTTP 验证列表会作为 HTTPS 候选暴露，避免空文件的同时保持合理质量门槛。

- **在系统代理 / VPN（如 Clash / TUN 模式）下能用吗？**
  可以，但流量会先过系统代理/VPN，再过免费代理（代理链）。若你的系统代理/VPN 出口 IP 被某些公共代理或 `httpbin.org` 封禁，失败率会上升。更纯净的测试可临时关闭系统代理。

- **GeoIP 国家数据准确吗？**
  使用 MaxMind GeoLite2-Country（社区镜像，每周刷新）。免费 IP 库有滞后，但作为代理地理分布参考足够。可设 `PROXY_GEOIP_ENABLE=0` 关闭。

- **如何贡献新代理来源？**
  编辑 `scripts/sources.txt`，加一行 `<raw_url> <type>`，提 PR。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## ⚠️ 免责声明

免费代理通常不稳定，且可能被第三方滥用。**请勿用于敏感流量**（登录、支付、隐私数据）。使用风险自负。本仓库仅聚合公开来源，不运营任何代理服务器。

## 🤝 贡献

欢迎提 PR 新增来源、改进验证逻辑或完善仪表盘。请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。⭐ Star 是对项目最好的支持！

## 📄 License

[MIT](LICENSE) © kael-odin

---

## 🇬🇧 English

A **free proxy list** that is **automatically verified daily** via GitHub Actions (zero server cost). Aggregates 10+ public sources, validates HTTP / HTTPS / SOCKS4 / SOCKS5, tags each proxy with GeoIP country and a latency tier, and ships multiple output formats.

### Quick start

```bash
# All working proxies (sorted by latency, deduped)
curl -s https://raw.githubusercontent.com/kael-odin/awesome-free-proxy-list/main/proxies/all.txt | head

# Structured JSON (country + latency + tier + source)
curl -s https://raw.githubusercontent.com/kael-odin/awesome-free-proxy-list/main/proxies/json/all.json | head
```

```python
import requests
proxy = "http://IP:PORT"  # one line from all.txt
proxies = {"http": proxy, "https": proxy}
print(requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10).text)
```

### Outputs

Plain `txt` (one `host:port` per line), `json` (structured with country/latency/tier), `csv`, per-country split, and fastest subsets — see the table in the Chinese section above. The [live dashboard](https://kael-odin.github.io/awesome-free-proxy-list/) lets you search, filter, copy and download without leaving the browser.

### Run locally

```bash
git clone https://github.com/kael-odin/awesome-free-proxy-list.git
cd awesome-free-proxy-list
python -m venv .venv && source .venv/bin/activate   # Windows: source .venv/Scripts/activate
pip install -r requirements.txt
python scripts/update.py
```

### Disclaimer

Free proxies are unstable and may be abused. **Do not use for sensitive traffic.** Use at your own risk. This repo only aggregates public sources; it does not operate any proxy server.

License: [MIT](LICENSE) © kael-odin
