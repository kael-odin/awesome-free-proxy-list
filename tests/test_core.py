"""Unit tests for pure functions in scripts/update.py and scripts/subscription.py.

Run: pytest tests/ -v
"""

import base64
import sys
from pathlib import Path

import pytest

# Make scripts/ importable.
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import subscription  # noqa: E402
from geoip_lookup import classify_ip_type  # noqa: E402
from subscription import flag_emoji  # noqa: E402
from update import (  # noqa: E402
    Proxy,
    build_history,
    classify_anonymity,
    fair_slice,
    format_hostport,
    parse_candidates,
    split_hostport,
    stable_hostports,
    tier_of,
)


# ---------- tier_of ----------
class TestTierOf:
    def test_none_is_unknown(self):
        assert tier_of(None) == "unknown"

    def test_fast(self):
        assert tier_of(100) == "fast"
        assert tier_of(499) == "fast"

    def test_medium(self):
        assert tier_of(500) == "medium"
        assert tier_of(1999) == "medium"

    def test_slow(self):
        assert tier_of(2000) == "slow"
        assert tier_of(10000) == "slow"


# ---------- classify_anonymity ----------
class TestClassifyAnonymity:
    def test_none_response_is_unknown(self):
        assert classify_anonymity(None, "1.2.3.4") == "unknown"

    def test_empty_is_unknown(self):
        assert classify_anonymity({}, "1.2.3.4") == "unknown"

    def test_no_headers_key_is_unknown(self):
        assert classify_anonymity({"foo": "bar"}, "1.2.3.4") == "unknown"

    def test_transparent_real_ip_in_xff(self):
        resp = {"headers": {"X-Forwarded-For": "1.2.3.4"}}
        assert classify_anonymity(resp, "1.2.3.4") == "transparent"

    def test_anonymous_via_present_no_real_ip(self):
        resp = {"headers": {"Via": "1.1 proxy"}}
        assert classify_anonymity(resp, "9.9.9.9") == "anonymous"

    def test_anonymous_xff_without_real_ip(self):
        resp = {"headers": {"X-Forwarded-For": "5.5.5.5"}}
        assert classify_anonymity(resp, "9.9.9.9") == "anonymous"

    def test_elite_no_proxy_headers(self):
        resp = {"headers": {"Host": "httpbin.org", "Accept": "*/*"}}
        assert classify_anonymity(resp, "9.9.9.9") == "elite"

    def test_case_insensitive_headers(self):
        resp = {"headers": {"x-forwarded-for": "1.2.3.4"}}
        assert classify_anonymity(resp, "1.2.3.4") == "transparent"


# ---------- flag_emoji ----------
class TestFlagEmoji:
    def test_us(self):
        assert flag_emoji("US") == "🇺🇸"

    def test_case_insensitive(self):
        assert flag_emoji("us") == "🇺🇸"

    def test_unknown_country(self):
        assert flag_emoji("UNKNOWN") == "🏳️"

    def test_empty(self):
        assert flag_emoji("") == "🏳️"

    def test_non_iso(self):
        assert flag_emoji("XX") == "🇽🇽"


# ---------- clash_proxy_name ----------
class TestClashProxyName:
    def test_name_has_flag_type_host_tier(self):
        p = Proxy(type="http", host="1.2.3.4", port=8080, latency_ms=100, country_code="US")
        name = subscription.clash_proxy_name(p, 1)
        assert "🇺🇸" in name
        assert "HTTP" in name
        assert "1.2.3.4:8080" in name
        assert "F" in name  # fast tier initial

    def test_unknown_country_uses_placeholder(self):
        p = Proxy(type="socks5", host="5.6.7.8", port=1080, latency_ms=2000)
        name = subscription.clash_proxy_name(p, 2)
        # Empty country_code falls back to "??"; flag_emoji("??") produces a flag-ish pair.
        assert "SOCKS5" in name
        assert "5.6.7.8:1080" in name


# ---------- _yaml_dump ----------
class TestYamlDump:
    def test_simple_dict(self):
        out = subscription._yaml_dump({"a": 1, "b": "hi"})
        assert "a: 1" in out
        assert "b: hi" in out

    def test_string_with_colon_quoted(self):
        out = subscription._yaml_dump({"k": "http://x:8080"})
        # Should be double-quoted because it contains colons.
        assert '"http://x:8080"' in out

    def test_bool_lowercase(self):
        out = subscription._yaml_dump({"udp": False})
        assert "udp: false" in out

    def test_list_of_strings(self):
        out = subscription._yaml_dump({"rules": ["MATCH,PROXY", "DIRECT"]})
        assert "- MATCH,PROXY" in out or '- "MATCH,PROXY"' in out
        assert "- DIRECT" in out or '- "DIRECT"' in out

    def test_list_of_dicts_block_style(self):
        out = subscription._yaml_dump({"proxies": [{"name": "p1", "type": "http", "server": "1.1.1.1", "port": 80}]})
        assert "- name: " in out
        assert "type: http" in out
        assert "server: 1.1.1.1" in out
        assert "port: 80" in out

    def test_empty_list(self):
        out = subscription._yaml_dump({"items": []})
        assert "items: []" in out

    def test_none_value(self):
        out = subscription._yaml_dump({"k": None})
        assert "k:" in out and "k: " not in out

    def test_produces_parseable_yaml(self):
        # Round-trip: the dumped YAML must parse back to the same structure.
        try:
            import yaml  # PyYAML
        except ImportError:
            pytest.skip("PyYAML not installed")
        obj = {
            "mixed-port": 7890,
            "proxies": [
                {"name": "🚀 P", "type": "http", "server": "1.2.3.4", "port": 8080, "udp": False},
                {"name": "n2", "type": "socks5", "server": "5.6.7.8", "port": 1080, "udp": True},
            ],
            "rules": ["MATCH,PROXY", "GEOIP,CN,DIRECT"],
            "allow-lan": False,
        }
        out = subscription._yaml_dump(obj)
        parsed = yaml.safe_load(out)
        assert parsed["mixed-port"] == 7890
        assert len(parsed["proxies"]) == 2
        assert parsed["proxies"][0]["server"] == "1.2.3.4"
        assert parsed["proxies"][1]["udp"] is True
        assert parsed["rules"] == ["MATCH,PROXY", "GEOIP,CN,DIRECT"]


# ---------- build_links / build_v2ray_sub ----------
class TestSubscriptionBuilders:
    def _proxy(self, **kw):
        defaults = {
            "type": "http",
            "host": "1.2.3.4",
            "port": 8080,
            "latency_ms": 100,
            "country": "United States",
            "country_code": "US",
            "source": "test",
        }
        defaults.update(kw)
        return Proxy(**defaults)

    def test_build_links_http(self):
        proxies = [self._proxy(host=f"1.2.3.{i}") for i in range(3)]
        out = subscription.build_links(proxies, "http")
        assert "http://1.2.3.0:8080" in out
        assert "http://1.2.3.1:8080" in out
        assert "http://1.2.3.2:8080" in out

    def test_build_links_socks5(self):
        proxies = [self._proxy(type="socks5", host="5.6.7.0", port=1080)]
        out = subscription.build_links(proxies, "socks5")
        assert "socks5://5.6.7.0:1080" in out

    def test_build_links_dedup(self):
        proxies = [self._proxy(), self._proxy()]  # same hostport
        out = subscription.build_links(proxies)
        assert out.count("1.2.3.4:8080") == 1

    def test_build_v2ray_base64_decodes(self):
        proxies = [
            self._proxy(type="http", host="1.2.3.4", port=8080),
            self._proxy(type="socks5", host="5.6.7.8", port=1080),
        ]
        b64 = subscription.build_v2ray_sub(proxies)
        decoded = base64.b64decode(b64).decode("utf-8")
        assert "http://1.2.3.4:8080" in decoded
        assert "socks5://5.6.7.8:1080" in decoded

    def test_build_v2ray_empty(self):
        b64 = subscription.build_v2ray_sub([])
        decoded = base64.b64decode(b64).decode("utf-8")
        assert decoded == ""


# ---------- classify_ip_type (ASN-based datacenter/residential inference) ----------
class TestClassifyIpType:
    def test_empty_is_unknown(self):
        assert classify_ip_type("") == "unknown"

    def test_datacenter_cloud_providers(self):
        for org in [
            "Amazon.com Inc.",
            "Google LLC",
            "Microsoft Corporation",
            "DigitalOcean LLC",
            "Cloudflare, Inc.",
            "OVH SAS",
            "Hetzner Online GmbH",
            "Alibaba (US) Technology Co., Ltd.",
            "Tencent Building",
            "Huawei Cloud",
        ]:
            assert classify_ip_type(org) == "datacenter", f"{org!r} should be datacenter"

    def test_residential_isps(self):
        for org in [
            "Comcast Cable Communications",
            "AT&T Services Inc.",
            "China Telecom Group",
            "Vodafone Group",
            "Verizon Business",
        ]:
            assert classify_ip_type(org) == "residential", f"{org!r} should be residential"

    def test_unknown_for_unlisted_org(self):
        assert classify_ip_type("Some Random Small ISP Co.") == "unknown"

    def test_case_insensitive(self):
        assert classify_ip_type("AMAZON.COM INC.") == "datacenter"
        assert classify_ip_type("comcast cable") == "residential"


# ---------- hostport helpers (IPv4 + bracketed IPv6) ----------
class TestHostportHelpers:
    def test_format_ipv4(self):
        assert format_hostport("1.2.3.4", 8080) == "1.2.3.4:8080"

    def test_format_ipv6_bracketed(self):
        assert format_hostport("2001:db8::1", 8080) == "[2001:db8::1]:8080"

    def test_split_ipv4(self):
        assert split_hostport("1.2.3.4:8080") == ("1.2.3.4", 8080)

    def test_split_ipv6(self):
        assert split_hostport("[2001:db8::1]:8080") == ("2001:db8::1", 8080)

    def test_roundtrip_both_families(self):
        for hp in ("1.2.3.4:8080", "[2001:db8::1]:8080"):
            host, port = split_hostport(hp)
            assert format_hostport(host, port) == hp

    def test_proxy_url_ipv4_unchanged(self):
        p = Proxy(type="http", host="1.2.3.4", port=8080)
        assert p.hostport == "1.2.3.4:8080"
        assert p.url == "http://1.2.3.4:8080"

    def test_proxy_url_https_uses_http_scheme(self):
        p = Proxy(type="https", host="1.2.3.4", port=8080)
        assert p.url == "http://1.2.3.4:8080"

    def test_proxy_url_ipv6_brackets(self):
        p = Proxy(type="socks5", host="2001:db8::1", port=1080)
        assert p.hostport == "[2001:db8::1]:1080"
        assert p.url == "socks5://[2001:db8::1]:1080"


# ---------- parse_candidates ----------
class TestParseCandidates:
    def test_ipv4_basic(self):
        assert parse_candidates("1.2.3.4:8080\n5.6.7.8:3128\n") == ["1.2.3.4:8080", "5.6.7.8:3128"]

    def test_ipv6_bracketed_accepted(self):
        assert parse_candidates("[2001:db8::1]:8080\n") == ["[2001:db8::1]:8080"]

    def test_ipv6_invalid_rejected(self):
        assert parse_candidates("[gg::notahex]:8080\n") == []

    def test_bare_ipv6_rejected_as_ambiguous(self):
        # "2001:db8::1:8080" — trailing group could be the port or part of the
        # address; unparseable unambiguously, so it must be skipped.
        assert parse_candidates("2001:db8::1:8080\n") == []

    def test_garbage_lines_skipped(self):
        assert parse_candidates("hello\n# comment\n\n1.2.3.4\n1.2.3.4:99999\n") == []


# ---------- fair_slice (fair candidate capping) ----------
class TestFairSlice:
    @staticmethod
    def _candidates(big=100, small=3):
        cands = {}
        for i in range(big):
            cands[f"10.{i // 250}.{i % 250}.1:1080"] = "http://big.example/list"
        for i in range(small):
            cands[f"9.9.{i}.1:1080"] = "http://small.example/list"
        return cands

    def test_small_source_not_starved(self):
        picked = fair_slice(self._candidates(), cap=10)
        sources = set(picked.values())
        assert "http://small.example/list" in sources
        assert "http://big.example/list" in sources

    def test_all_of_small_source_included_when_cap_allows(self):
        picked = fair_slice(self._candidates(big=100, small=3), cap=10)
        small = [hp for hp, src in picked.items() if src.endswith("small.example/list")]
        assert len(small) == 3

    def test_cap_respected(self):
        assert len(fair_slice(self._candidates(), cap=10)) == 10

    def test_deterministic(self):
        assert fair_slice(self._candidates(), 10) == fair_slice(self._candidates(), 10)

    def test_under_cap_returns_all(self):
        assert len(fair_slice(self._candidates(big=5, small=3), cap=100)) == 8

    def test_empty(self):
        assert fair_slice({}, 10) == {}


# ---------- build_history / stable_hostports (streak grace window) ----------
class TestBuildHistory:
    @staticmethod
    def _proxy(hp):
        host, port = split_hostport(hp)
        return Proxy(type="http", host=host, port=port, country_code="US", anonymity="elite")

    def test_new_proxy_streak_one(self):
        h = build_history({}, [self._proxy("1.1.1.1:80")], "2026-10-29")
        assert h["1.1.1.1:80"]["streak"] == 1

    def test_streak_increments_next_day(self):
        prev = {"1.1.1.1:80": {"streak": 5, "last_seen": "2026-10-28"}}
        h = build_history(prev, [self._proxy("1.1.1.1:80")], "2026-10-29")
        assert h["1.1.1.1:80"]["streak"] == 6

    def test_same_day_rerun_keeps_streak(self):
        prev = {"1.1.1.1:80": {"streak": 6, "last_seen": "2026-10-29"}}
        h = build_history(prev, [self._proxy("1.1.1.1:80")], "2026-10-29")
        assert h["1.1.1.1:80"]["streak"] == 6

    def test_one_missed_day_carries_streak_frozen(self):
        prev = {"1.1.1.1:80": {"streak": 30, "last_seen": "2026-10-28", "type": "http"}}
        h = build_history(prev, [], "2026-10-29")
        assert h["1.1.1.1:80"]["streak"] == 30

    def test_two_missed_days_dropped(self):
        prev = {"1.1.1.1:80": {"streak": 30, "last_seen": "2026-10-27"}}
        h = build_history(prev, [], "2026-10-29")
        assert "1.1.1.1:80" not in h

    def test_recovered_proxy_resumes_streak(self):
        prev = {"1.1.1.1:80": {"streak": 30, "last_seen": "2026-10-28"}}
        h = build_history(prev, [self._proxy("1.1.1.1:80")], "2026-10-29")
        assert h["1.1.1.1:80"]["streak"] == 31


class TestStableHostports:
    def test_requires_seen_today(self):
        history = {
            "2.2.2.2:80": {"streak": 9, "last_seen": "2026-10-28"},  # grace-carried, absent today
            "1.1.1.1:80": {"streak": 5, "last_seen": "2026-10-29"},
            "3.3.3.3:80": {"streak": 1, "last_seen": "2026-10-29"},  # below threshold
        }
        assert stable_hostports(history, "2026-10-29", 2) == ["1.1.1.1:80"]

    def test_sorted_by_streak_desc(self):
        history = {
            "1.1.1.1:80": {"streak": 5, "last_seen": "2026-10-29"},
            "2.2.2.2:80": {"streak": 9, "last_seen": "2026-10-29"},
        }
        assert stable_hostports(history, "2026-10-29", 2) == ["2.2.2.2:80", "1.1.1.1:80"]


# ---------- classify_ip_type keyword-table regression ----------
class TestClassifyIpTypeEdgeCases:
    def test_leaseweb_with_space_still_datacenter(self):
        assert classify_ip_type("Leaseweb USA, Inc.") == "datacenter"

    def test_path_net_datacenter(self):
        assert classify_ip_type("path.net, LLC") == "datacenter"

    def test_generic_path_no_longer_mismatches(self):
        # "path" was too generic — a residential ISP whose org merely contains
        # "path" used to be classified datacenter before the datacenter table.
        assert classify_ip_type("Compath Mobile Networks") == "unknown"
