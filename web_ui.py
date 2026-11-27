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
    filter_matches,
    parse_espn_events,
)

HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Live Sports Link Aggregator</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --live: #ef4444;
      --accent: #38bdf8;
      --ok: #22c55e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
    }
    .container { max-width: 1100px; margin: 0 auto; }
    h1 { margin: 0 0 6px; font-size: 1.6rem; }
    .subtitle { color: var(--muted); margin-bottom: 20px; font-size: 0.95rem; }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      background: var(--card);
      padding: 14px;
      border-radius: 10px;
      border: 1px solid var(--border);
      margin-bottom: 18px;
      align-items: center;
    }
    select, input[type="text"], button {
      background: #0f172a;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 12px;
      font-size: 0.92rem;
    }
    input[type="text"] { flex: 1; min-width: 180px; }
    button {
      background: var(--accent);
      color: #0f172a;
      font-weight: 600;
      border: none;
      cursor: pointer;
    }
    button:hover { opacity: 0.9; }
    label.toggle {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      font-size: 0.92rem;
    }
    .stats { color: var(--muted); font-size: 0.9rem; margin-bottom: 12px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.82rem;
      color: var(--muted);
    }
    .badge {
      padding: 2px 8px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.75rem;
      text-transform: uppercase;
    }
    .badge.live { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid var(--live); }
    .badge.upcoming { background: rgba(56, 189, 248, 0.15); color: #7dd3fc; }
    .badge.finished { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; }
    .match-title { font-size: 1.05rem; font-weight: 600; }
    .score { font-size: 1.25rem; font-weight: 700; color: var(--ok); }
    .broadcasts { font-size: 0.85rem; color: var(--muted); }
    .links { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
    .links a {
      font-size: 0.82rem;
      color: var(--accent);
      text-decoration: none;
      border: 1px solid var(--border);
      padding: 4px 8px;
      border-radius: 6px;
      background: #0f172a;
    }
    .links a:hover { border-color: var(--accent); }
    .custom-box {
      margin-top: 26px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
    }
    .custom-box h2 { margin: 0 0 10px; font-size: 1.1rem; }
    .custom-row { display: flex; gap: 10px; flex-wrap: wrap; }
    .custom-list { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; font-size: 0.9rem; }
    .custom-list a { color: var(--accent); word-break: break-all; }
    .error { color: #fca5a5; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🏆 Live Sports Link Aggregator</h1>
    <div class="subtitle">Tổng hợp các trận thể thao trực tiếp (Bóng đá, NBA, Tennis, NHL, NFL, UFC...) &amp; đường link công khai</div>

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

    <div class="stats" id="stats">Đang tải...</div>
    <div class="grid" id="grid"></div>

    <div class="custom-box">
      <h2>Quét link công khai từ trang lịch thi đấu tùy chọn</h2>
      <div class="custom-row">
        <input type="text" id="customUrl" placeholder="Nhập URL trang lịch thi đấu công khai (https://...)" />
        <button onclick="scanCustomUrl()">Quét link</button>
      </div>
      <div class="custom-list" id="customList"></div>
    </div>
  </div>

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
        stats.textContent = `Tìm thấy ${data.matches.length} trận (${liveCount} trận đang LIVE)`;
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
            <div class="broadcasts">🕒 ${timeText || 'Chưa rõ giờ'}</div>
            <div class="broadcasts">📺 Kênh: ${m.broadcasts.length ? m.broadcasts.join(', ') : 'Chưa có thông tin kênh'}</div>
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
          `<div>• <a href="${l.url}" target="_blank" rel="noopener noreferrer">${l.label}</a></div>`
        ).join('');
      } catch (err) {
        box.innerHTML = `<span class="error">Lỗi: ${err.message}</span>`;
      }
    }

    document.getElementById('league').addEventListener('change', loadMatches);
    document.getElementById('liveOnly').addEventListener('change', loadMatches);
    document.getElementById('search').addEventListener('keydown', e => { if (e.key === 'Enter') loadMatches(); });
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
