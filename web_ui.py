"""Local web dashboard for viewing live football matches and public links."""

from __future__ import annotations

import json
import os
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from scraper import (
    SPORT_SOURCES,
    fetch_all_sports_matches,
    fetch_espn_scoreboard,
    fetch_public_page_links,
    fetch_youtube_live_streams,
    filter_matches,
    parse_espn_events,
)

HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Live Sports Hub</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <style>
    :root {
      --bg: #050d1a;
      --bg-grad:
        radial-gradient(ellipse 80% 50% at 20% -10%, rgba(16, 185, 129, 0.28), transparent 60%),
        radial-gradient(ellipse 70% 50% at 85% 5%, rgba(56, 189, 248, 0.25), transparent 55%),
        radial-gradient(ellipse 60% 45% at 50% 100%, rgba(99, 102, 241, 0.22), transparent 60%);
      --surface: rgba(13, 24, 42, 0.72);
      --card: rgba(19, 34, 58, 0.78);
      --card-hover: rgba(26, 46, 78, 0.92);
      --border: rgba(148, 163, 184, 0.2);
      --text: #f8fafc;
      --muted: #cbd5e1;
      --live: #ef4444;
      --accent: #38bdf8;
      --accent-2: #10b981;
      --ok: #34d399;
      --radius: 16px;
    }
    body.theme-neon {
      --bg: #0b0618;
      --bg-grad:
        radial-gradient(ellipse 80% 50% at 15% 0%, rgba(236, 72, 153, 0.28), transparent 60%),
        radial-gradient(ellipse 70% 50% at 85% 10%, rgba(139, 92, 246, 0.30), transparent 55%),
        radial-gradient(ellipse 60% 45% at 50% 100%, rgba(56, 189, 248, 0.22), transparent 60%);
      --surface: rgba(22, 14, 42, 0.75);
      --card: rgba(31, 20, 58, 0.80);
      --card-hover: rgba(43, 28, 79, 0.94);
      --accent: #f472b6;
      --accent-2: #a855f7;
    }
    body.theme-light {
      --bg: #eef4ff;
      --bg-grad:
        radial-gradient(ellipse 80% 50% at 15% 0%, rgba(56, 189, 248, 0.28), transparent 60%),
        radial-gradient(ellipse 70% 50% at 85% 10%, rgba(16, 185, 129, 0.22), transparent 55%),
        radial-gradient(ellipse 60% 45% at 50% 100%, rgba(99, 102, 241, 0.16), transparent 60%);
      --surface: rgba(255, 255, 255, 0.82);
      --card: rgba(255, 255, 255, 0.94);
      --card-hover: #ffffff;
      --border: rgba(15, 23, 42, 0.12);
      --text: #0f172a;
      --muted: #475569;
      --accent: #0284c7;
      --accent-2: #059669;
      --ok: #059669;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background-color: var(--bg);
      background-image: var(--bg-grad);
      background-attachment: fixed;
      color: var(--text);
      line-height: 1.5;
      min-height: 100vh;
      position: relative;
      transition: background-color 0.3s ease, color 0.3s ease;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: -1;
      opacity: 0.28;
      background-image:
        linear-gradient(to right, rgba(255,255,255,0.06) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255,255,255,0.06) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: radial-gradient(ellipse at center, black 40%, transparent 85%);
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 30;
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      background: rgba(7, 11, 20, 0.82);
      border-bottom: 1px solid var(--border);
    }
    .topbar-inner {
      max-width: 1200px;
      margin: 0 auto;
      padding: 14px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .brand-icon {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      display: grid;
      place-items: center;
      font-size: 1.2rem;
      box-shadow: 0 6px 20px rgba(56, 189, 248, 0.25);
    }
    .brand h1 { margin: 0; font-size: 1.15rem; font-weight: 800; letter-spacing: -0.02em; }
    .brand p { margin: 0; font-size: 0.78rem; color: var(--muted); }
    .nav-pills {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .nav-pills a {
      text-decoration: none;
      color: var(--muted);
      font-size: 0.85rem;
      font-weight: 600;
      padding: 7px 12px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--surface);
      transition: all 0.2s ease;
    }
    .nav-pills a:hover { color: var(--text); border-color: var(--accent); }
    .theme-switch {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .theme-btn {
      padding: 6px 10px;
      font-size: 0.78rem;
      border-radius: 999px;
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      box-shadow: none;
    }
    .theme-btn:hover { border-color: var(--accent); }

    .hero {
      background: linear-gradient(125deg, rgba(16, 185, 129, 0.22), rgba(56, 189, 248, 0.22), rgba(99, 102, 241, 0.22));
      border: 1px solid rgba(56, 189, 248, 0.32);
      border-radius: 18px;
      padding: 24px 26px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 18px;
      flex-wrap: wrap;
      backdrop-filter: blur(12px);
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.25);
    }
    .hero h2 { margin: 0 0 6px; font-size: 1.45rem; font-weight: 800; letter-spacing: -0.02em; }
    .hero p { margin: 0; color: var(--muted); font-size: 0.94rem; max-width: 620px; }
    .hero-badges { display: flex; gap: 10px; flex-wrap: wrap; }
    .hero-pill {
      padding: 8px 14px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 700;
      background: rgba(15, 23, 42, 0.55);
      color: #f8fafc;
      border: 1px solid rgba(255, 255, 255, 0.16);
    }

    .container { max-width: 1200px; margin: 0 auto; padding: 24px 20px 60px; }

    .section {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
      margin-bottom: 24px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28);
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }
    .section-head h2 {
      margin: 0;
      font-size: 1.15rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .stats {
      color: var(--muted);
      font-size: 0.85rem;
      font-weight: 500;
      background: rgba(15, 23, 42, 0.7);
      padding: 5px 12px;
      border-radius: 999px;
      border: 1px solid var(--border);
    }

    .controls, .custom-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 14px;
    }
    select, input[type="text"] {
      background: rgba(10, 15, 28, 0.9);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 0.9rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s ease;
    }
    select:focus, input[type="text"]:focus { border-color: var(--accent); }
    input[type="text"] { flex: 1; min-width: 200px; }

    button {
      background: linear-gradient(135deg, var(--accent), #0ea5e9);
      color: #06121f;
      font-weight: 700;
      font-family: inherit;
      border: none;
      border-radius: 10px;
      padding: 10px 16px;
      font-size: 0.9rem;
      cursor: pointer;
      transition: transform 0.15s ease, opacity 0.2s ease, box-shadow 0.2s ease;
      box-shadow: 0 4px 14px rgba(56, 189, 248, 0.22);
    }
    button:hover { opacity: 0.94; transform: translateY(-1px); }
    button:active { transform: translateY(0); }

    label.toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 0.88rem;
      font-weight: 600;
      padding: 9px 14px;
      border-radius: 10px;
      background: rgba(10, 15, 28, 0.7);
      border: 1px solid var(--border);
      user-select: none;
    }
    label.toggle input { accent-color: var(--live); width: 16px; height: 16px; }

    .yt-presets { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
    .yt-presets button {
      background: rgba(15, 23, 42, 0.85);
      color: var(--text);
      border: 1px solid var(--border);
      box-shadow: none;
      font-weight: 600;
      font-size: 0.83rem;
      padding: 7px 12px;
      border-radius: 999px;
    }
    .yt-presets button:hover {
      border-color: var(--accent);
      color: var(--accent);
      background: rgba(56, 189, 248, 0.08);
    }

    .player-wrap {
      display: none;
      margin-bottom: 18px;
      background: #000;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid rgba(56, 189, 248, 0.4);
      box-shadow: 0 14px 36px rgba(0, 0, 0, 0.55);
    }
    .player-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 14px;
      background: #0f172a;
      font-size: 0.9rem;
      font-weight: 600;
      gap: 10px;
    }
    .player-ratio { position: relative; width: 100%; padding-top: 56.25%; }
    .player-ratio iframe {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      border: 0;
    }

    .yt-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(265px, 1fr));
      gap: 14px;
    }
    .yt-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
    }
    .yt-card:hover {
      transform: translateY(-3px);
      border-color: rgba(56, 189, 248, 0.45);
      background: var(--card-hover);
    }
    .thumb-wrap { position: relative; }
    .thumb-wrap img { width: 100%; height: 152px; object-fit: cover; display: block; }
    .live-pill {
      position: absolute;
      top: 10px;
      left: 10px;
      background: rgba(239, 68, 68, 0.92);
      color: #fff;
      font-size: 0.72rem;
      font-weight: 800;
      padding: 3px 8px;
      border-radius: 6px;
      letter-spacing: 0.04em;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #fff;
      animation: pulse 1.3s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.75); }
    }
    .yt-body { padding: 12px; display: flex; flex-direction: column; gap: 7px; flex: 1; }
    .yt-title {
      font-size: 0.92rem;
      font-weight: 700;
      line-height: 1.35;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .yt-meta { font-size: 0.8rem; color: var(--muted); }
    .yt-actions { display: flex; gap: 8px; margin-top: auto; padding-top: 8px; }
    .yt-actions button { flex: 1; padding: 8px 10px; font-size: 0.83rem; }
    .yt-actions a {
      padding: 8px 12px;
      font-size: 0.83rem;
      font-weight: 600;
      color: var(--accent);
      border: 1px solid var(--border);
      border-radius: 10px;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
    }
    .yt-actions a:hover { border-color: var(--accent); background: rgba(56, 189, 248, 0.08); }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 15px;
      display: flex;
      flex-direction: column;
      gap: 9px;
      transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .card:hover { transform: translateY(-2px); border-color: rgba(56, 189, 248, 0.4); }
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      font-size: 0.78rem;
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .badge {
      padding: 3px 9px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 0.72rem;
      white-space: nowrap;
    }
    .badge.live { background: rgba(239, 68, 68, 0.18); color: #fca5a5; border: 1px solid var(--live); }
    .badge.upcoming { background: rgba(56, 189, 248, 0.14); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.3); }
    .badge.finished { background: rgba(148, 163, 184, 0.14); color: #cbd5e1; }
    .match-title { font-size: 1.02rem; font-weight: 700; line-height: 1.35; }
    .score {
      font-size: 1.3rem;
      font-weight: 800;
      color: var(--ok);
      letter-spacing: 0.03em;
    }
    .meta-line { font-size: 0.83rem; color: var(--muted); display: flex; align-items: center; gap: 6px; }
    .links { display: flex; flex-wrap: wrap; gap: 6px; margin-top: auto; padding-top: 4px; }
    .links a {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--accent);
      text-decoration: none;
      border: 1px solid var(--border);
      padding: 5px 10px;
      border-radius: 8px;
      background: rgba(10, 15, 28, 0.8);
      transition: all 0.15s ease;
    }
    .links a:hover { border-color: var(--accent); background: rgba(56, 189, 248, 0.1); }

    .custom-list { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; font-size: 0.88rem; }
    .custom-list div {
      padding: 8px 12px;
      border-radius: 8px;
      background: rgba(10, 15, 28, 0.7);
      border: 1px solid var(--border);
    }
    .custom-list a { color: var(--accent); word-break: break-all; text-decoration: none; }
    .custom-list a:hover { text-decoration: underline; }
    .error { color: #fca5a5; }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <div class="brand-icon">🏆</div>
        <div>
          <h1>Live Sports Hub</h1>
          <p>Thể thao trực tiếp toàn cầu &amp; kênh phát sóng miễn phí</p>
        </div>
      </div>
      <nav class="nav-pills">
        <a href="#live-video">📺 Xem Live</a>
        <a href="#scoreboard">⚽ Lịch &amp; Tỷ số</a>
        <a href="#scanner">🔎 Quét Link</a>
      </nav>
      <div class="theme-switch">
        <button class="theme-btn" onclick="setTheme('')">🏟️ Sân cỏ</button>
        <button class="theme-btn" onclick="setTheme('theme-neon')">⚡ Neon</button>
        <button class="theme-btn" onclick="setTheme('theme-light')">☀️ Sáng</button>
      </div>
    </div>
  </header>

  <main class="container">
    <section class="hero">
      <div>
        <h2>🔥 Trung Tâm Thể Thao Trực Tiếp Toàn Cầu</h2>
        <p>Theo dõi tỷ số trực tiếp, lịch thi đấu các giải lớn và mở ngay các kênh thể thao đang phát Live miễn phí trên một màn hình.</p>
      </div>
      <div class="hero-badges">
        <span class="hero-pill">🌍 Toàn thế giới</span>
        <span class="hero-pill">📺 YouTube Live 1 chạm</span>
        <span class="hero-pill">⚡ Cập nhật Real-time</span>
      </div>
    </section>
    <section class="section" id="live-video">
      <div class="section-head">
        <h2>📺 Kênh Thể Thao Đang Live Miễn Phí</h2>
        <div class="stats" id="ytStats">Đang tìm các kênh đang Live...</div>
      </div>

      <div class="yt-presets">
        <button onclick="setYtQuery('trực tiếp bóng đá')">⚽ Bóng đá Live</button>
        <button onclick="setYtQuery('live sports stream')">🏆 Thể thao Live</button>
        <button onclick="setYtQuery('badminton live')">🏸 Cầu lông Live</button>
        <button onclick="setYtQuery('bóng chuyền trực tiếp')">🏐 Bóng chuyền Live</button>
        <button onclick="setYtQuery('esports live tournament')">🎮 Esports Live</button>
      </div>

      <div class="custom-row">
        <input type="text" id="ytQuery" value="live sports stream" placeholder="Nhập từ khóa tìm kênh đang Live miễn phí (tiếng Việt hoặc tiếng Anh)..." />
        <button onclick="loadYouTubeLive()">Tìm kênh Live</button>
      </div>

      <div class="player-wrap" id="playerWrap">
        <div class="player-bar">
          <span id="playerTitle">Đang phát...</span>
          <button onclick="closePlayer()" style="padding:6px 12px;font-size:0.8rem;">✕ Đóng trình phát</button>
        </div>
        <div class="player-ratio">
          <iframe id="ytPlayer" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>
        </div>
      </div>

      <div class="yt-grid" id="ytGrid"></div>
    </section>

    <section class="section" id="scoreboard">
      <div class="section-head">
        <h2>⚽ Lịch Thi Đấu &amp; Tỷ Số Toàn Cầu</h2>
        <div class="stats" id="stats">Đang tải...</div>
      </div>

      <div class="controls">
        <select id="league">
          __LEAGUE_OPTIONS__
        </select>
        <input type="text" id="search" placeholder="Tìm đội bóng, giải đấu, kênh phát sóng..." />
        <label class="toggle">
          <input type="checkbox" id="liveOnly" />
          Chỉ trận đang đá (LIVE)
        </label>
        <button onclick="loadMatches()">Làm mới</button>
      </div>

      <div class="grid" id="grid"></div>
    </section>

    <section class="section" id="scanner">
      <div class="section-head">
        <h2>🔎 Quét Link Công Khai Từ Trang Lịch Thi Đấu</h2>
      </div>
      <div class="custom-row" style="margin-bottom:0;">
        <input type="text" id="customUrl" placeholder="Nhập URL trang lịch thi đấu công khai (vd: https://bongdaplus.vn)" />
        <button onclick="scanCustomUrl()">Quét link</button>
      </div>
      <div class="custom-list" id="customList"></div>
    </section>
  </main>

  <script>
    async function loadMatches() {
      const league = document.getElementById('league').value;
      const q = document.getElementById('search').value;
      const live = document.getElementById('liveOnly').checked ? '1' : '0';
      const stats = document.getElementById('stats');
      const grid = document.getElementById('grid');
      stats.textContent = 'Đang lấy dữ liệu...';
      try {
        const params = new URLSearchParams({ league, q, live });
        const res = await fetch('/api/matches?' + params.toString());
        const data = await res.json();
        if (data.error) {
          stats.innerHTML = `<span class="error">Lỗi: ${data.error}</span>`;
          grid.innerHTML = '';
          return;
        }
        const liveCount = data.matches.filter(m => m.status === 'live').length;
        stats.textContent = `${data.matches.length} trận (${liveCount} đang LIVE)`;
        if (!data.matches.length) {
          grid.innerHTML = '<div style="color:#94a3b8">Không có trận nào khớp bộ lọc.</div>';
          return;
        }
        grid.innerHTML = data.matches.map(m => {
          const timeText = m.start_time ? new Date(m.start_time).toLocaleString('vi-VN') : '';
          return `
          <div class="card">
            <div class="card-top">
              <span>${m.league}</span>
              <span class="badge ${m.status}">${m.status === 'live' ? '● LIVE ' + m.status_detail : m.status_detail || m.status}</span>
            </div>
            <div class="match-title">${m.name}</div>
            <div class="score">${m.score}</div>
            <div class="meta-line">🕒 ${timeText || 'Chưa rõ giờ'}</div>
            <div class="meta-line">📺 Kênh: ${m.broadcasts.length ? m.broadcasts.join(', ') : 'Chưa có thông tin kênh'}</div>
            <div class="links">
              ${m.links.map(l => `<a href="${l.url}" target="_blank" rel="noopener noreferrer">🔗 ${l.label}</a>`).join('')}
            </div>
          </div>
        `;
        }).join('');
      } catch (err) {
        stats.innerHTML = `<span class="error">Lỗi kết nối: ${err.message}</span>`;
      }
    }

    async function scanCustomUrl() {
      const url = document.getElementById('customUrl').value.trim();
      const box = document.getElementById('customList');
      if (!url) return;
      box.textContent = 'Đang quét...';
      try {
        const res = await fetch('/api/scan?url=' + encodeURIComponent(url));
        const data = await res.json();
        if (data.error) {
          box.innerHTML = `<span class="error">Lỗi: ${data.error}</span>`;
          return;
        }
        if (!data.links.length) {
          box.textContent = 'Không tìm thấy link bóng đá/trực tiếp nào trên trang này.';
          return;
        }
        box.innerHTML = data.links.map(l =>
          `<div>🔗 <a href="${l.url}" target="_blank" rel="noopener noreferrer">${l.label}</a></div>`
        ).join('');
      } catch (err) {
        box.innerHTML = `<span class="error">Lỗi: ${err.message}</span>`;
      }
    }

    document.getElementById('league').addEventListener('change', loadMatches);
    document.getElementById('liveOnly').addEventListener('change', loadMatches);
    document.getElementById('search').addEventListener('keydown', e => { if (e.key === 'Enter') loadMatches(); });
    document.getElementById('ytQuery').addEventListener('keydown', e => { if (e.key === 'Enter') loadYouTubeLive(); });

    function setYtQuery(q) {
      document.getElementById('ytQuery').value = q;
      function setTheme(name) {
      document.body.className = name;
      try { localStorage.setItem('sports_theme', name); } catch (e) {}
    }
    try {
      const savedTheme = localStorage.getItem('sports_theme');
      if (savedTheme) document.body.className = savedTheme;
    } catch (e) {}

    loadYouTubeLive();
    }

    function playStream(embedUrl, title) {
      const wrap = document.getElementById('playerWrap');
      document.getElementById('playerTitle').textContent = title;
      document.getElementById('ytPlayer').src = embedUrl;
      wrap.style.display = 'block';
      wrap.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function closePlayer() {
      document.getElementById('ytPlayer').src = '';
      document.getElementById('playerWrap').style.display = 'none';
    }

    async function loadYouTubeLive() {
      const q = document.getElementById('ytQuery').value.trim() || 'live sports stream';
      const stats = document.getElementById('ytStats');
      const grid = document.getElementById('ytGrid');
      stats.textContent = 'Đang tìm kênh YouTube đang Live...';
      try {
        const res = await fetch('/api/youtube-live?q=' + encodeURIComponent(q));
        const data = await res.json();
        if (data.error) {
          stats.innerHTML = `<span class="error">Lỗi: ${data.error}</span>`;
          grid.innerHTML = '';
          return;
        }
        stats.textContent = `${data.streams.length} luồng đang phát Live`;
        if (!data.streams.length) {
          grid.innerHTML = '<div style="color:#94a3b8">Không tìm thấy luồng Live nào với từ khóa này.</div>';
          return;
        }
        grid.innerHTML = data.streams.map(s => `
          <div class="yt-card">
            <div class="thumb-wrap">
              <img src="${s.thumbnail}" alt="" loading="lazy" />
              <div class="live-pill"><span class="pulse-dot"></span> LIVE</div>
            </div>
            <div class="yt-body">
              <div class="yt-title">${s.title}</div>
              <div class="yt-meta">📺 ${s.channel} · ${s.viewers}</div>
              <div class="yt-actions">
                <button onclick='playStream(${JSON.stringify(s.embed_url)}, ${JSON.stringify(s.title)})'>▶ Xem ngay</button>
                <a href="${s.watch_url}" target="_blank" rel="noopener noreferrer">YouTube</a>
              </div>
            </div>
          </div>
        `).join('');
      } catch (err) {
        stats.innerHTML = `<span class="error">Lỗi kết nối: ${err.message}</span>`;
      }
    }

    function setTheme(name) {
      document.body.className = name;
      try { localStorage.setItem('sports_theme', name); } catch (e) {}
    }
    try {
      const savedTheme = localStorage.getItem('sports_theme');
      if (savedTheme) document.body.className = savedTheme;
    } catch (e) {}

    loadYouTubeLive();
    loadMatches();
  </script>
</body>
</html>
"""


def _build_html() -> bytes:
    options = "\n".join(
        f'<option value="{slug}">{label}</option>' for slug, label in SPORT_SOURCES
    )
    return HTML_PAGE.replace("__LEAGUE_OPTIONS__", options).encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the local dashboard and JSON API."""

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/":
            body = _build_html()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/matches":
            league = params.get("league", ["all_sports"])[0]
            query = params.get("q", [""])[0]
            live_only = params.get("live", ["0"])[0] == "1"
            try:
                if league == "all_sports":
                    matches = fetch_all_sports_matches()
                else:
                    raw = fetch_espn_scoreboard(league=league)
                    matches = parse_espn_events(raw)
                filtered = filter_matches(matches, live_only=live_only, query=query)
                self._send_json({"matches": [m.to_dict() for m in filtered]})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc), "matches": []}, status=HTTPStatus.BAD_GATEWAY)
            return

        if parsed.path == "/api/youtube-live":
            query = params.get("q", ["live sports stream"])[0]
            try:
                streams = fetch_youtube_live_streams(query=query)
                self._send_json({"streams": streams})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc), "streams": []}, status=HTTPStatus.BAD_GATEWAY)
            return

        if parsed.path == "/api/scan":
            target_url = params.get("url", [""])[0].strip()
            if not target_url.startswith(("http://", "https://")):
                self._send_json({"error": "URL phải bắt đầu bằng http:// hoặc https://"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                links = fetch_public_page_links(target_url)
                self._send_json({"links": links})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc), "links": []}, status=HTTPStatus.BAD_GATEWAY)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, format: str, *args: Any) -> None:
        # Keep terminal clean
        return


def run_server(host: str | None = None, port: int | None = None) -> None:
    """Start the local or cloud web dashboard."""
    env_port = os.environ.get("PORT")
    resolved_port = port if port is not None else (int(env_port) if env_port else 8080)
    resolved_host = host if host is not None else ("0.0.0.0" if env_port else "127.0.0.1")

    server = ThreadingHTTPServer((resolved_host, resolved_port), DashboardHandler)
    print(f"Dashboard đang chạy tại: http://{resolved_host}:{resolved_port}")
    print("Nhấn Ctrl+C để dừng.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng server.")
    finally:
        server.server_close()
