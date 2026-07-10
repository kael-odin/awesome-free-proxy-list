"""
Daily free proxy list pipeline.

Scrape public proxy sources → validate (HTTP/HTTPS/SOCKS4/SOCKS5) with latency
measurement → enrich with GeoIP country → write multiple output formats.

Backward compatible: the original plain-text lists (proxies/*.txt) and
summary.json keep their existing schema/fields; new formats are additive.

Configuration via environment variables (all optional):
  PROXY_TIMEOUT_SEC          per-proxy test timeout (default 8)
  PROXY_CONCURRENCY          max concurrent validations (default 200)
  PROXY_MAX_PER_TYPE         cap candidates per protocol (default 2000)
  PROXY_TOP_HTTP_LIMIT       size of the fastest-HTTP subset (default 100)
  PROXY_TOP_LIMIT            size of the fastest subset for other types (default 100)
  PROXY_TEST_URL_HTTP        HTTP validation target
  PROXY_TEST_URL_HTTPS       HTTPS validation target
  PROXY_GEOIP_ENABLE         "0"/"false" to disable country lookups (default enabled)
  PROXY_GEOIP_DB             override path to a local GeoLite2-Country.mmdb
"""

import asyncio
import csv
import json
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

import aiohttp
from aiohttp_socks import ProxyConnector

from geoip_lookup import GeoIP

ProxyType = Literal["http", "https", "socks4", "socks5"]

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "scripts" / "sources.txt"
OUT_DIR = ROOT / "proxies"
JSON_DIR = OUT_DIR / "json"
BY_COUNTRY_DIR = OUT_DIR / "by-country"
README = ROOT / "README.md"

DEFAULT_TIMEOUT_SEC = float(os.getenv("PROXY_TIMEOUT_SEC", "8"))
CONCURRENCY = int(os.getenv("PROXY_CONCURRENCY", "200"))
MAX_PER_TYPE = int(os.getenv("PROXY_MAX_PER_TYPE", "2000"))
TOP_HTTP_LIMIT = int(os.getenv("PROXY_TOP_HTTP_LIMIT", "100"))
TOP_LIMIT = int(os.getenv("PROXY_TOP_LIMIT", "100"))

# Latency tiers (milliseconds).
TIER_FAST_MS = 500
TIER_MEDIUM_MS = 2000

TEST_URL_HTTPS = os.getenv("PROXY_TEST_URL_HTTPS", "https://api.ipify.org?format=json")
TEST_URL_HTTP = os.getenv("PROXY_TEST_URL_HTTP", "http://api.ipify.org?format=json")

PROXY_RE = re.compile(r"^\s*(?P<host>\d{1,3}(?:\.\d{1,3}){3})\s*:\s*(?P<port>\d{2,5})\s*$")


@dataclass(frozen=True)
class Proxy:
    type: ProxyType
    host: str
    port: int
    # Enrichment (filled in after validation). Defaults keep the dataclass safe.
    latency_ms: float | None = None
    country: str = ""
    country_code: str = ""
    source: str = ""

    @property
    def hostport(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def url(self) -> str:
        if self.type in ("http", "https"):
            return f"http://{self.host}:{self.port}"
        if self.type == "socks4":
            return f"socks4://{self.host}:{self.port}"
        return f"socks5://{self.host}:{self.port}"

    @property
    def tier(self) -> str:
        return tier_of(self.latency_ms)

    def to_dict(self, updated_utc: str) -> dict:
        return {
            "ip": self.host,
            "port": self.port,
            "type": self.type,
            "country": self.country,
            "country_code": self.country_code,
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "tier": self.tier,
            "source": self.source,
            "updated_utc": updated_utc,
        }


def tier_of(ms: float | None) -> str:
    """Map a latency in milliseconds to a human-friendly tier label."""
    if ms is None:
        return "unknown"
    if ms < TIER_FAST_MS:
        return "fast"
    if ms < TIER_MEDIUM_MS:
        return "medium"
    return "slow"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_sources(path: Path) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        url = parts[0]
        typ = parts[1].lower() if len(parts) > 1 else "mixed"
        items.append((url, typ))
    return items


def parse_candidates(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Some sources pad with whitespace or quote marks; strip common wrappers.
        line = line.strip("'\"")
        m = PROXY_RE.match(line)
        if not m:
            continue
        host = m.group("host")
        port = int(m.group("port"))
        if 1 <= port <= 65535:
            out.append(f"{host}:{port}")
    return out


async def fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(
        url,
        headers={"User-Agent": "free-proxy-list-bot/1.0"},
        allow_redirects=True,
    ) as resp:
        resp.raise_for_status()
        return await resp.text(errors="ignore")


async def scrape_all_sources() -> tuple[dict[str, dict[str, str]], dict[str, int]]:
    """Scrape every source. Returns (candidates_by_bucket, source_counts).

    candidates_by_bucket maps each bucket ("forward" / "socks4" / "socks5") to a
    dict of {hostport: source_url}. We keep the originating source URL per
    hostport so each validated proxy can report where it came from.
    """
    sources = read_sources(SOURCES_FILE)
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(ssl=False, limit=20)
    buckets: dict[str, dict[str, str]] = {"forward": {}, "socks4": {}, "socks5": {}}
    counts: dict[str, int] = defaultdict(int)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector, trust_env=True) as session:
        tasks = []
        for url, typ in sources:
            tasks.append((url, typ, asyncio.create_task(fetch_text(session, url))))

        for url, typ, task in tasks:
            try:
                text = await task
            except Exception:
                continue
            candidates = parse_candidates(text)
            counts[url] = len(candidates)
            bucket = "forward" if typ in ("http", "https", "mixed") else typ
            if bucket not in buckets:
                continue
            for hp in candidates:
                # First source to provide a hostport wins; keeps it stable across runs.
                buckets[bucket].setdefault(hp, url)
    return buckets, dict(counts)


async def _check_via_proxy(
    session: aiohttp.ClientSession,
    *,
    url: str,
    proxy_url: str | None,
) -> bool:
    async with session.get(url, proxy=proxy_url) as resp:
        if resp.status >= 400:
            return False
        await resp.read()
        return True


async def check_forward_proxy(proxy: Proxy, timeout_s: float) -> tuple[float | None, float | None]:
    """
    Returns (http_ms, https_ms). Either can be None if that protocol test fails.
    """
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector, trust_env=True) as session:
        http_ms: float | None = None
        https_ms: float | None = None

        start = time.perf_counter()
        try:
            ok = await _check_via_proxy(session, url=TEST_URL_HTTP, proxy_url=proxy.url)
            if ok:
                http_ms = (time.perf_counter() - start) * 1000.0
        except Exception:
            pass

        start = time.perf_counter()
        try:
            ok = await _check_via_proxy(session, url=TEST_URL_HTTPS, proxy_url=proxy.url)
            if ok:
                https_ms = (time.perf_counter() - start) * 1000.0
        except Exception:
            pass

        return http_ms, https_ms


async def check_socks(proxy: Proxy, timeout_s: float) -> float | None:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    connector = ProxyConnector.from_url(proxy.url, rdns=True)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector, trust_env=True) as session:
        start = time.perf_counter()
        for url in (TEST_URL_HTTPS, TEST_URL_HTTP):
            try:
                async with session.get(url) as resp:
                    if resp.status >= 400:
                        continue
                    await resp.read()
                    return (time.perf_counter() - start) * 1000.0
            except Exception:
                continue
    return None


async def validate_socks(
    proxies: Iterable[Proxy], timeout_s: float, concurrency: int
) -> list[tuple[Proxy, float]]:
    sem = asyncio.Semaphore(concurrency)
    ok: list[tuple[Proxy, float]] = []

    async def run_one(p: Proxy) -> None:
        async with sem:
            ms = await check_socks(p, timeout_s)
            if ms is not None:
                ok.append((p, ms))

    await asyncio.gather(*(run_one(p) for p in proxies))
    ok.sort(key=lambda x: x[1])
    return ok


async def validate_forward(
    proxies: Iterable[Proxy], timeout_s: float, concurrency: int
) -> tuple[list[tuple[Proxy, float, float | None]], set[str]]:
    """
    Returns (ok_list, https_pass_set).

    ok_list: (proxy, http_ms, https_ms) for proxies that passed the HTTP test,
             sorted by HTTP latency ascending. https_ms may be None.
    https_pass_set: hostports that explicitly passed the HTTPS test.
    """
    sem = asyncio.Semaphore(concurrency)
    http_ok: list[tuple[Proxy, float, float | None]] = []
    https_pass: set[str] = set()

    async def run_one(p: Proxy) -> None:
        async with sem:
            http_ms, https_ms = await check_forward_proxy(p, timeout_s)
            if http_ms is not None:
                http_ok.append((p, http_ms, https_ms))
            if https_ms is not None:
                https_pass.add(p.hostport)

    await asyncio.gather(*(run_one(p) for p in proxies))
    http_ok.sort(key=lambda x: x[1])
    return http_ok, https_pass


def to_proxies(proxy_type: ProxyType, hostports_with_source: dict[str, str]) -> list[Proxy]:
    out: list[Proxy] = []
    for hp, src in hostports_with_source.items():
        host, port_s = hp.split(":", 1)
        out.append(Proxy(type=proxy_type, host=host, port=int(port_s), source=src))
    return out


def rebuild_with_enrichment(proxies: list[Proxy], geoip: GeoIP) -> list[Proxy]:
    """Return a new list of Proxy objects with country filled in (best-effort)."""
    have_geoip = geoip.available
    out: list[Proxy] = []
    for p in proxies:
        country, code = (geoip.lookup(p.host) if have_geoip else ("", ""))
        out.append(
            Proxy(
                type=p.type,
                host=p.host,
                port=p.port,
                latency_ms=p.latency_ms,
                country=country,
                country_code=code,
                source=p.source,
            )
        )
    return out


def write_txt(path: Path, hostports: list[str]) -> None:
    path.write_text("\n".join(hostports) + ("\n" if hostports else ""), encoding="utf-8")


def write_json(path: Path, items: list[dict]) -> None:
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, items: list[dict]) -> None:
    fieldnames = ["ip", "port", "type", "country", "country_code", "latency_ms", "tier", "source", "updated_utc"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in items:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def write_by_country(proxies: list[Proxy]) -> dict[str, int]:
    """Write one txt file per country code. Returns {country_code: count}."""
    BY_COUNTRY_DIR.mkdir(parents=True, exist_ok=True)
    for old in BY_COUNTRY_DIR.glob("*.txt"):
        old.unlink()

    grouped: dict[str, list[str]] = defaultdict(list)
    for p in proxies:
        cc = p.country_code or "UNKNOWN"
        grouped[cc].append(p.hostport)

    counts: dict[str, int] = {}
    for cc, hostports in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        seen: list[str] = []
        s: set[str] = set()
        for hp in hostports:
            if hp not in s:
                s.add(hp)
                seen.append(hp)
        write_txt(BY_COUNTRY_DIR / f"{cc}.txt", seen)
        counts[cc] = len(seen)
    return counts


def update_readme_stats(stats: dict) -> None:
    if not README.exists():
        return
    text = README.read_text(encoding="utf-8")
    start = "<!-- STATS:START -->"
    end = "<!-- STATS:END -->"
    if start not in text or end not in text:
        return

    c = stats["counts"]
    block = (
        f"{start}\n"
        f"Last update (UTC): **{stats['updated_utc']}**\n\n"
        f"| Type | Working | Total Candidates |\n"
        f"|---|---:|---:|\n"
        f"| HTTP | {c['http']['working']} | {c['http']['candidates']} |\n"
        f"| HTTPS | {c['https']['working']} | {c['https']['candidates']} |\n"
        f"| SOCKS4 | {c['socks4']['working']} | {c['socks4']['candidates']} |\n"
        f"| SOCKS5 | {c['socks5']['working']} | {c['socks5']['candidates']} |\n"
        f"| ALL | {c['all']['working']} | {c['all']['candidates']} |\n"
        f"{end}"
    )

    pre = text.split(start, 1)[0]
    post = text.split(end, 1)[1]
    README.write_text(pre + block + post, encoding="utf-8")


async def main() -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    updated_utc = utc_now_iso()

    geoip = GeoIP()

    scraped, source_counts = await scrape_all_sources()

    # Cap candidates to keep runtime stable. Sort for deterministic ordering.
    forward_candidates = dict(sorted(scraped["forward"].items())[:MAX_PER_TYPE])
    socks4_candidates = dict(sorted(scraped["socks4"].items())[:MAX_PER_TYPE])
    socks5_candidates = dict(sorted(scraped["socks5"].items())[:MAX_PER_TYPE])

    forward_proxies = to_proxies("http", forward_candidates)
    socks4_proxies = to_proxies("socks4", socks4_candidates)
    socks5_proxies = to_proxies("socks5", socks5_candidates)

    forward_ok, _https_pass = await validate_forward(
        forward_proxies, DEFAULT_TIMEOUT_SEC, CONCURRENCY
    )
    socks4_ok = await validate_socks(socks4_proxies, DEFAULT_TIMEOUT_SEC, CONCURRENCY)
    socks5_ok = await validate_socks(socks5_proxies, DEFAULT_TIMEOUT_SEC, CONCURRENCY)

    # Build validated Proxy lists with latency, sorted fastest-first.
    http_proxies: list[Proxy] = [
        Proxy(type="http", host=p.host, port=p.port, latency_ms=http_ms, source=p.source)
        for p, http_ms, _https_ms in forward_ok
    ]
    # HTTPS list = forward proxies that explicitly passed the HTTPS test.
    https_proxies: list[Proxy] = [
        Proxy(type="https", host=p.host, port=p.port, latency_ms=https_ms, source=p.source)
        for p, _http_ms, https_ms in forward_ok
        if https_ms is not None
    ]
    # Fallback: expose HTTP list as HTTPS candidates when none passed HTTPS test,
    # since most HTTP forward proxies support HTTPS via CONNECT. Avoids empty https.txt.
    if not https_proxies and http_proxies:
        https_proxies = [
            Proxy(type="https", host=p.host, port=p.port, latency_ms=p.latency_ms, source=p.source)
            for p in http_proxies
        ]

    socks4_proxies_ok: list[Proxy] = [
        Proxy(type="socks4", host=p.host, port=p.port, latency_ms=ms, source=p.source)
        for p, ms in socks4_ok
    ]
    socks5_proxies_ok: list[Proxy] = [
        Proxy(type="socks5", host=p.host, port=p.port, latency_ms=ms, source=p.source)
        for p, ms in socks5_ok
    ]

    # Enrich all working proxies with GeoIP country.
    geoip_on = geoip.available
    http_proxies = rebuild_with_enrichment(http_proxies, geoip)
    https_proxies = rebuild_with_enrichment(https_proxies, geoip)
    socks4_proxies_ok = rebuild_with_enrichment(socks4_proxies_ok, geoip)
    socks5_proxies_ok = rebuild_with_enrichment(socks5_proxies_ok, geoip)

    # Plain-text outputs (backward compatible) — host:port only.
    http_hostports = [p.hostport for p in http_proxies]
    https_hostports = [p.hostport for p in https_proxies]
    socks4_hostports = [p.hostport for p in socks4_proxies_ok]
    socks5_hostports = [p.hostport for p in socks5_proxies_ok]

    # Global list, fastest-first, deduped by hostport.
    all_sorted = sorted(
        http_proxies + https_proxies + socks4_proxies_ok + socks5_proxies_ok,
        key=lambda p: (p.latency_ms if p.latency_ms is not None else 9_999_999, p.hostport),
    )
    seen_hp: set[str] = set()
    all_proxies: list[Proxy] = []
    for p in all_sorted:
        if p.hostport in seen_hp:
            continue
        seen_hp.add(p.hostport)
        all_proxies.append(p)
    all_hostports = [p.hostport for p in all_proxies]

    write_txt(OUT_DIR / "http.txt", http_hostports)
    write_txt(OUT_DIR / "https.txt", https_hostports)
    write_txt(OUT_DIR / "socks4.txt", socks4_hostports)
    write_txt(OUT_DIR / "socks5.txt", socks5_hostports)
    write_txt(OUT_DIR / "all.txt", all_hostports)

    # Fastest subsets.
    write_txt(OUT_DIR / "top-http.txt", http_hostports[:TOP_HTTP_LIMIT])
    write_txt(OUT_DIR / "top-https.txt", https_hostports[:TOP_LIMIT])
    write_txt(OUT_DIR / "top-socks5.txt", socks5_hostports[:TOP_LIMIT])

    # Structured JSON outputs.
    write_json(JSON_DIR / "http.json", [p.to_dict(updated_utc) for p in http_proxies])
    write_json(JSON_DIR / "https.json", [p.to_dict(updated_utc) for p in https_proxies])
    write_json(JSON_DIR / "socks4.json", [p.to_dict(updated_utc) for p in socks4_proxies_ok])
    write_json(JSON_DIR / "socks5.json", [p.to_dict(updated_utc) for p in socks5_proxies_ok])
    write_json(JSON_DIR / "all.json", [p.to_dict(updated_utc) for p in all_proxies])

    # CSV (combined, all types).
    write_csv(OUT_DIR / "all.csv", [p.to_dict(updated_utc) for p in all_proxies])

    # By-country split.
    by_country = write_by_country(all_proxies)

    def tier_counts(proxies: list[Proxy]) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for p in proxies:
            out[p.tier] += 1
        return dict(out)

    top_country_counts = dict(sorted(by_country.items(), key=lambda kv: -kv[1])[:15])

    stats = {
        "updated_utc": updated_utc,
        "config": {
            "timeout_sec": DEFAULT_TIMEOUT_SEC,
            "concurrency": CONCURRENCY,
            "max_per_type": MAX_PER_TYPE,
            "test_url_https": TEST_URL_HTTPS,
            "test_url_http": TEST_URL_HTTP,
            "geoip_enabled": geoip_on,
            "tier_thresholds_ms": {"fast": TIER_FAST_MS, "medium": TIER_MEDIUM_MS},
        },
        "sources": {
            "count": len(source_counts),
            "per_source_candidates": dict(
                sorted(source_counts.items(), key=lambda kv: -kv[1])
            ),
        },
        "counts": {
            "http": {"candidates": len(forward_candidates), "working": len(http_proxies)},
            "https": {"candidates": len(forward_candidates), "working": len(https_proxies)},
            "socks4": {"candidates": len(socks4_candidates), "working": len(socks4_proxies_ok)},
            "socks5": {"candidates": len(socks5_candidates), "working": len(socks5_proxies_ok)},
            "all": {
                "candidates": len(forward_candidates)
                + len(socks4_candidates)
                + len(socks5_candidates),
                "working": len(all_proxies),
            },
        },
        "by_tier": {
            "all": tier_counts(all_proxies),
            "http": tier_counts(http_proxies),
            "https": tier_counts(https_proxies),
            "socks4": tier_counts(socks4_proxies_ok),
            "socks5": tier_counts(socks5_proxies_ok),
        },
        "by_country": {
            "all": top_country_counts,
        },
        "top_fastest": [p.to_dict(updated_utc) for p in all_proxies[:10]],
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    update_readme_stats(stats)

    geoip.close()

    print(
        f"Done. http={len(http_proxies)} https={len(https_proxies)} "
        f"socks4={len(socks4_proxies_ok)} socks5={len(socks5_proxies_ok)} "
        f"all={len(all_proxies)} geoip={'on' if geoip_on else 'off'}"
    )


if __name__ == "__main__":
    asyncio.run(main())
