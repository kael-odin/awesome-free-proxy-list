/* ===== Free Proxy List Dashboard — app.js ===== */
/* Pure vanilla JS. No dependencies. Data is served as static JSON from ./data/. */
(() => {
  "use strict";

  // ----- Config -----
  const DATA_BASE = "data";
  const TYPES = ["http", "https", "socks4", "socks5"];
  const PAGE_SIZE = 50;
  const MAX_LATENCY_FOR_BAR = 3000; // ms — saturates the latency bar at 100%

  // Country code -> flag emoji (covers all ISO 3166-1 alpha-2).
  const flagEmoji = (cc) => {
    if (!cc || cc === "UNKNOWN" || cc.length !== 2) return "🏳️";
    const cp = [...cc.toUpperCase()].map((c) => 0x1f1e6 + (c.charCodeAt(0) - 65));
    return String.fromCodePoint(...cp);
  };

  // ----- i18n -----
  const I18N = {
    zh: {
      skip: "跳到主内容 / Skip to content",
      brand_sub: "每日自动验证 · 免费代理",
      hero_title: "免费代理列表 · 每日自动验证",
      hero_desc: "聚合 10+ 公开来源，自动验证 HTTP / HTTPS / SOCKS4 / SOCKS5 可用性，标注国家归属与延迟分档。一键搜索、筛选、复制、下载。",
      search_ph: "搜索 IP / 国家 / 端口…",
      type: "类型", country: "国家", tier: "延迟档", sort: "排序",
      all_types: "全部",
      sort_latency: "延迟（快→慢）", sort_type: "类型", sort_country: "国家",
      copy_all: "复制结果", download: "下载结果",
      th_proxy: "代理 (IP:Port)", th_type: "类型", th_country: "国家",
      th_latency: "延迟", th_tier: "档位", th_actions: "操作",
      loading: "加载中…",
      prev: "上一页", next: "下一页",
      sources_title: "来源构成",
      footer_data: "数据由 GitHub Actions 每日自动验证生成",
      disclaimer_short: "免费代理不稳定且可能被滥用，请勿用于敏感流量。",
      stat_all: "全部可用", stat_updated: "最后更新",
      result_count: (n, t) => `共 ${n.toLocaleString()} 条结果（总 ${t.toLocaleString()}）`,
      no_results: "没有匹配的代理。试试调整筛选条件。",
      load_failed: "数据加载失败。请稍后刷新或访问 GitHub raw 文件。",
      copied_one: "已复制：", copied_all: (n) => `已复制 ${n} 条到剪贴板`,
      downloaded: (n) => `已下载 ${n} 条`,
      page_of: (a, b) => `${a} / ${b}`,
    },
    en: {
      skip: "Skip to content",
      brand_sub: "Daily auto-verified · Free proxies",
      hero_title: "Free Proxy List · Daily Verified",
      hero_desc: "Aggregates 10+ public sources, auto-verifies HTTP / HTTPS / SOCKS4 / SOCKS5 availability, with GeoIP country and latency tiers. Search, filter, copy, download.",
      search_ph: "Search IP / country / port…",
      type: "Type", country: "Country", tier: "Latency", sort: "Sort",
      all_types: "All",
      sort_latency: "Latency (fast→slow)", sort_type: "Type", sort_country: "Country",
      copy_all: "Copy results", download: "Download",
      th_proxy: "Proxy (IP:Port)", th_type: "Type", th_country: "Country",
      th_latency: "Latency", th_tier: "Tier", th_actions: "Actions",
      loading: "Loading…",
      prev: "Prev", next: "Next",
      sources_title: "Source breakdown",
      footer_data: "Data is auto-verified daily by GitHub Actions",
      disclaimer_short: "Free proxies are unstable and may be abused. Do not use for sensitive traffic.",
      stat_all: "Working", stat_updated: "Last update",
      result_count: (n, t) => `${n.toLocaleString()} of ${t.toLocaleString()} proxies`,
      no_results: "No matching proxies. Try adjusting the filters.",
      load_failed: "Failed to load data. Please refresh later or use the GitHub raw files.",
      copied_one: "Copied: ", copied_all: (n) => `Copied ${n} proxies to clipboard`,
      downloaded: (n) => `Downloaded ${n} proxies`,
      page_of: (a, b) => `${a} / ${b}`,
    },
  };

  // ----- State -----
  let allProxies = [];
  let filtered = [];
  let summary = null;
  let countries = [];
  let page = 1;
  let lang = localStorage.getItem("fpl-lang") || (navigator.language.startsWith("zh") ? "zh" : "en");
  let theme = localStorage.getItem("fpl-theme") || "dark";

  // ----- DOM refs -----
  const $ = (sel) => document.querySelector(sel);
  const el = {
    html: document.documentElement,
    body: document.body,
    search: $("#search"),
    typeFilter: $("#typeFilter"),
    countryFilter: $("#countryFilter"),
    tierFilter: $("#tierFilter"),
    sortBy: $("#sortBy"),
    copyBtn: $("#copyBtn"),
    downloadBtn: $("#downloadBtn"),
    body: $("#proxyBody"),
    loadingCell: $("#loadingCell"),
    resultCount: $("#resultCount"),
    pagination: $("#pagination"),
    prevBtn: $("#prevBtn"),
    nextBtn: $("#nextBtn"),
    pageInfo: $("#pageInfo"),
    heroStats: $("#heroStats"),
    lastUpdate: $("#lastUpdate"),
    sourcesSection: $("#sourcesSection"),
    sourceBars: $("#sourceBars"),
    toast: $("#toast"),
    langToggle: $("#langToggle"),
    langLabel: $("#langLabel"),
    themeToggle: $("#themeToggle"),
    themeIcon: $("#themeIcon"),
  };

  // ----- i18n apply -----
  function t(key, ...args) {
    const v = I18N[lang][key];
    return typeof v === "function" ? v(...args) : v;
  }
  function applyI18n() {
    el.html.setAttribute("data-lang", lang);
    el.html.lang = lang === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      const key = node.getAttribute("data-i18n");
      const val = I18N[lang][key];
      if (typeof val === "string") node.textContent = val;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
      const key = node.getAttribute("data-i18n-placeholder");
      const val = I18N[lang][key];
      if (typeof val === "string") node.setAttribute("placeholder", val);
    });
    el.langLabel.textContent = lang === "zh" ? "EN" : "中";
    el.themeIcon.textContent = theme === "dark" ? "☀️" : "🌙";
    // Re-render dynamic text (count etc.)
    renderCount();
    if (summary) renderHero();
  }

  // ----- Theme -----
  function applyTheme() {
    el.html.setAttribute("data-theme", theme);
    el.themeIcon.textContent = theme === "dark" ? "☀️" : "🌙";
    localStorage.setItem("fpl-theme", theme);
  }

  // ----- Toast -----
  let toastTimer;
  function toast(msg) {
    el.toast.textContent = msg;
    el.toast.hidden = false;
    requestAnimationFrame(() => el.toast.classList.add("show"));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.toast.classList.remove("show");
      setTimeout(() => { el.toast.hidden = true; }, 200);
    }, 2200);
  }

  // ----- Data loading -----
  async function fetchJSON(path) {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) throw new Error(`${path} -> ${r.status}`);
    return r.json();
  }

  async function load() {
    try {
      summary = await fetchJSON(`${DATA_BASE}/summary.json`);
      // Load all types in parallel.
      const data = await Promise.all(
        TYPES.map((tp) => fetchJSON(`${DATA_BASE}/${tp}.json`).catch(() => []))
      );
      allProxies = [];
      TYPES.forEach((tp, i) => {
        (data[i] || []).forEach((p) => allProxies.push({ ...p, type: p.type || tp }));
      });
      // Build country list from loaded data.
      const ccSet = new Set();
      allProxies.forEach((p) => ccSet.add(p.country_code || "UNKNOWN"));
      countries = [...ccSet].sort();
      renderHero();
      renderCountryFilter();
      renderSources();
      applyFilters();
    } catch (e) {
      console.error(e);
      el.body.innerHTML = `<tr class="empty-row"><td colspan="7">${t("load_failed")}</td></tr>`;
    }
  }

  // ----- Render: hero stats -----
  function renderHero() {
    if (!summary) return;
    const c = summary.counts || {};
    el.lastUpdate.textContent = `${t("stat_updated")}: ${formatDate(summary.updated_utc)}`;
    const cards = [
      { cls: "is-all", num: (c.all && c.all.working) || 0, lbl: t("stat_all") },
      { cls: "is-http", num: (c.http && c.http.working) || 0, lbl: "HTTP" },
      { cls: "is-https", num: (c.https && c.https.working) || 0, lbl: "HTTPS" },
      { cls: "is-socks4", num: (c.socks4 && c.socks4.working) || 0, lbl: "SOCKS4" },
      { cls: "is-socks5", num: (c.socks5 && c.socks5.working) || 0, lbl: "SOCKS5" },
    ];
    el.heroStats.innerHTML = cards
      .map((s) => `<div class="stat-card ${s.cls}"><div class="num">${s.num.toLocaleString()}</div><span class="lbl">${s.lbl}</span></div>`)
      .join("");
  }

  function renderCountryFilter() {
    const cur = el.countryFilter.value || "all";
    const opts = [`<option value="all">${t("all_types")}</option>`]
      .concat(
        countries
          .filter((cc) => cc !== "UNKNOWN")
          .map((cc) => `<option value="${cc}">${flagEmoji(cc)} ${cc}</option>`)
      )
      .concat(countries.includes("UNKNOWN") ? [`<option value="UNKNOWN">🏳️ ?</option>`] : []);
    el.countryFilter.innerHTML = opts.join("");
    el.countryFilter.value = cur;
  }

  // ----- Render: source breakdown -----
  function renderSources() {
    if (!summary || !summary.sources || !summary.sources.per_source_candidates) {
      el.sourcesSection.hidden = true;
      return;
    }
    const entries = Object.entries(summary.sources.per_source_candidates);
    if (!entries.length) { el.sourcesSection.hidden = true; return; }
    el.sourcesSection.hidden = false;
    const max = Math.max(...entries.map(([, n]) => n), 1);
    el.sourceBars.innerHTML = entries
      .map(([url, n]) => {
        const pct = Math.max(2, Math.round((n / max) * 100));
        const short = url.replace("https://raw.githubusercontent.com/", "");
        return `<div class="source-row">
          <div class="source-bar-track">
            <div class="source-bar-fill" style="width:${pct}%"></div>
            <span class="src-label" title="${url}">${short}</span>
          </div>
          <span class="src-count">${n.toLocaleString()}</span>
        </div>`;
      })
      .join("");
  }

  // ----- Filtering / sorting -----
  function applyFilters() {
    const q = el.search.value.trim().toLowerCase();
    const type = el.typeFilter.value;
    const cc = el.countryFilter.value;
    const tier = el.tierFilter.value;
    const sort = el.sortBy.value;

    filtered = allProxies.filter((p) => {
      if (type !== "all" && p.type !== type) return false;
      if (cc !== "all" && (p.country_code || "UNKNOWN") !== cc) return false;
      if (tier !== "all" && tierOf(p) !== tier) return false;
      if (q) {
        const hay = `${p.ip}:${p.port} ${p.country || ""} ${p.country_code || ""} ${p.type}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    const tierRank = { fast: 0, medium: 1, slow: 2, unknown: 3 };
    if (sort === "latency") {
      filtered.sort((a, b) => (a.latency_ms ?? 1e9) - (b.latency_ms ?? 1e9));
    } else if (sort === "type") {
      filtered.sort((a, b) => a.type.localeCompare(b.type) || (a.latency_ms ?? 1e9) - (b.latency_ms ?? 1e9));
    } else if (sort === "country") {
      filtered.sort((a, b) => (a.country_code || "ZZ").localeCompare(b.country_code || "ZZ") || (a.latency_ms ?? 1e9) - (b.latency_ms ?? 1e9));
    }
    page = 1;
    renderTable();
  }

  function tierOf(p) {
    if (p.latency_ms == null) return "unknown";
    if (p.latency_ms < 500) return "fast";
    if (p.latency_ms < 2000) return "medium";
    return "slow";
  }

  // ----- Render: table -----
  function renderTable() {
    renderCount();
    if (!filtered.length) {
      el.body.innerHTML = `<tr class="empty-row"><td colspan="7">${t("no_results")}</td></tr>`;
      el.pagination.hidden = true;
      return;
    }
    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    if (page > totalPages) page = totalPages;
    const start = (page - 1) * PAGE_SIZE;
    const slice = filtered.slice(start, start + PAGE_SIZE);

    el.body.innerHTML = slice
      .map((p, i) => {
        const idx = start + i + 1;
        const hp = `${p.ip}:${p.port}`;
        const tier = tierOf(p);
        const lat = p.latency_ms != null ? `${Math.round(p.latency_ms)}ms` : "—";
        const barPct = p.latency_ms != null ? Math.min(100, (p.latency_ms / MAX_LATENCY_FOR_BAR) * 100) : 0;
        const barColor = tier === "fast" ? "var(--fast)" : tier === "medium" ? "var(--medium)" : tier === "slow" ? "var(--slow)" : "var(--unknown)";
        const cc = p.country_code || "UNKNOWN";
        const cname = p.country || (cc === "UNKNOWN" ? "?" : cc);
        const copyStr = escapeAttr(hp);
        return `<tr>
          <td class="idx">${idx}</td>
          <td class="hp">${hp}</td>
          <td><span class="badge badge-${p.type}">${p.type.toUpperCase()}</span></td>
          <td><span class="country"><span class="flag">${flagEmoji(cc)}</span>${escapeHtml(cname)}</span></td>
          <td><span class="latency">${lat}<span class="latency-bar"><i style="width:${barPct}%;background:${barColor}"></i></span></span></td>
          <td><span class="tier-dot tier-${tier}">${tier}</span></td>
          <td><button class="copy-one" data-copy="${copyStr}" type="button">📋</button></td>
        </tr>`;
      })
      .join("");

    // Pagination state
    el.pagination.hidden = totalPages <= 1;
    el.pageInfo.textContent = t("page_of", page, totalPages);
    el.prevBtn.disabled = page <= 1;
    el.nextBtn.disabled = page >= totalPages;
  }

  function renderCount() {
    el.resultCount.textContent = t("result_count", filtered.length, allProxies.length);
  }

  // ----- Helpers -----
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function escapeAttr(s) { return escapeHtml(s); }
  function formatDate(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString(lang === "zh" ? "zh-CN" : "en-US", { dateStyle: "medium", timeStyle: "short" });
    } catch { return iso; }
  }

  // ----- Actions -----
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; }
    catch {
      // Fallback for non-secure contexts
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch {}
      document.body.removeChild(ta);
      return true;
    }
  }

  function filteredHostports() {
    return filtered.map((p) => `${p.ip}:${p.port}`).join("\n");
  }

  async function onCopyAll() {
    if (!filtered.length) return;
    const ok = await copyText(filteredHostports());
    if (ok) toast(t("copied_all", filtered.length));
  }

  function onDownload() {
    if (!filtered.length) return;
    const lines = filteredHostports();
    const blob = new Blob([lines + "\n"], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `proxies-${Date.now()}.txt`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast(t("downloaded", filtered.length));
  }

  async function onCopyOne(e) {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    const val = btn.getAttribute("data-copy");
    const ok = await copyText(val);
    if (ok) toast(t("copied_one") + val);
  }

  // ----- Event wiring -----
  function bind() {
    el.search.addEventListener("input", debounce(applyFilters, 150));
    el.typeFilter.addEventListener("change", applyFilters);
    el.countryFilter.addEventListener("change", applyFilters);
    el.tierFilter.addEventListener("change", applyFilters);
    el.sortBy.addEventListener("change", applyFilters);
    el.copyBtn.addEventListener("click", onCopyAll);
    el.downloadBtn.addEventListener("click", onDownload);
    el.body.addEventListener("click", onCopyOne);
    el.prevBtn.addEventListener("click", () => { if (page > 1) { page--; renderTable(); } });
    el.nextBtn.addEventListener("click", () => {
      const total = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
      if (page < total) { page++; renderTable(); }
    });
    el.langToggle.addEventListener("click", () => {
      lang = lang === "zh" ? "en" : "zh";
      localStorage.setItem("fpl-lang", lang);
      applyI18n();
      renderCountryFilter();
    });
    el.themeToggle.addEventListener("click", () => {
      theme = theme === "dark" ? "light" : "dark";
      applyTheme();
    });
    // Keyboard: "/" focuses search, "Esc" clears it.
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement !== el.search) {
        e.preventDefault(); el.search.focus();
      } else if (e.key === "Escape" && document.activeElement === el.search) {
        el.search.value = ""; applyFilters(); el.search.blur();
      }
    });
  }

  function debounce(fn, ms) {
    let id;
    return (...args) => { clearTimeout(id); id = setTimeout(() => fn(...args), ms); };
  }

  // ----- Init -----
  function init() {
    applyTheme();
    applyI18n();
    bind();
    load();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
