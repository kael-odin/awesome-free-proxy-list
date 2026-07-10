"""
Offline GeoIP country lookup for the proxy list pipeline.

Uses MaxMind's free GeoLite2-Country database (via the community mirror at
P3TERX/GeoLite.mmdb, which requires no license key) together with the pure-Python
``geoip2`` reader. The database is downloaded lazily on first use and cached
locally for reuse across runs.

Design goals:
- Zero license-key requirement (works out of the box in GitHub Actions).
- Pure-Python runtime (no compiled libmaxminddb dependency needed).
- Graceful degradation: if the database is unavailable, lookups return empty
  strings instead of raising, so the main pipeline never breaks because of GeoIP.

Environment variables:
- PROXY_GEOIP_ENABLE: "0"/"false" disables GeoIP entirely (default: enabled).
- PROXY_GEOIP_DB: override path to a local .mmdb file (skips download).
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "scripts" / "data" / "GeoLite2-Country.mmdb"

# Community mirror of MaxMind GeoLite2-Country. No license key required.
# `git.io` is a stable short link that follows the "latest" release tag.
GEOIP_DB_URL = os.getenv(
    "PROXY_GEOIP_DB_URL",
    "https://git.io/GeoLite2-Country.mmdb",
)

# Re-download if the cached DB is older than this many days.
GEOIP_REFRESH_DAYS = int(os.getenv("PROXY_GEOIP_REFRESH_DAYS", "7"))


def is_enabled() -> bool:
    val = os.getenv("PROXY_GEOIP_ENABLE", "1").strip().lower()
    return val not in ("0", "false", "no", "off")


def _db_path() -> Path:
    override = os.getenv("PROXY_GEOIP_DB")
    return Path(override) if override else DEFAULT_DB_PATH


def _needs_download(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        return True
    import time

    age_days = (time.time() - path.stat().st_mtime) / 86400
    return age_days > GEOIP_REFRESH_DAYS


def download_db(dest: Path | None = None) -> Optional[Path]:
    """Download the GeoLite2-Country mmdb to ``dest`` (default cache path).

    Returns the path on success, or None if the download failed after retries.
    """
    import time

    dest = dest or _db_path()
    dest.parent.mkdir(parents=True, exist_ok=True)

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                GEOIP_DB_URL,
                headers={"User-Agent": "free-proxy-list-bot/1.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — trusted mirror
                data = resp.read()
            if len(data) < 1024:
                last_err = ValueError("downloaded file too small")
                continue
            dest.write_bytes(data)
            return dest
        except Exception as e:
            last_err = e
            # Brief backoff before retrying.
            time.sleep(1.0 * (attempt + 1))
    return None


def ensure_db() -> Optional[Path]:
    """Make sure a usable mmdb exists locally; download if missing/stale."""
    if not is_enabled():
        return None
    path = _db_path()
    if not _needs_download(path):
        return path
    return download_db(path)


class GeoIP:
    """Lazy-loading GeoIP country resolver with safe fallbacks."""

    def __init__(self) -> None:
        self._reader = None  # type: ignore[assignment]
        self._db_path: Path | None = None
        self._load_attempts = 0
        self._max_load_attempts = 3

    def _load(self) -> bool:
        # If we already loaded a reader successfully, keep using it.
        if self._reader is not None:
            return True
        # Allow a few retries: the first attempt may fail if the mmdb download
        # is slow or the network blips. We do NOT permanently give up.
        if self._load_attempts >= self._max_load_attempts:
            return False
        self._load_attempts += 1
        if not is_enabled():
            return False
        path = ensure_db()
        if path is None:
            return False
        try:
            import geoip2.database  # type: ignore

            self._reader = geoip2.database.Reader(str(path))
            self._db_path = path
            return True
        except Exception:
            self._reader = None
            return False

    @property
    def available(self) -> bool:
        return self._load()

    def lookup(self, ip: str) -> tuple[str, str]:
        """Return (country_name, country_code). Empty strings on any failure."""
        if not self._load() or self._reader is None:
            return ("", "")
        try:
            resp = self._reader.country(ip)
            name = resp.country.name or ""
            code = resp.country.iso_code or ""
            return (name, code)
        except Exception:
            return ("", "")

    def close(self) -> None:
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:
                pass
            self._reader = None
