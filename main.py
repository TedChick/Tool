"""CLI entry point for the Live Football Link Aggregator."""

from __future__ import annotations

import argparse
import sys

from scraper import (
    export_csv,
    export_json,
    fetch_all_sports_matches,
    fetch_espn_scoreboard,
    fetch_public_page_links,
    filter_matches,
    parse_espn_events,
)
from web_ui import run_server


def _print_matches(matches) -> None:
    if not matches:
        print("Không tìm thấy trận đấu nào khớp bộ lọc.")
        return

    for idx, m in enumerate(matches, start=1):
        badge = "LIVE" if m.status == "live" else m.status.upper()
        detail = f" ({m.status_detail})" if m.status_detail else ""
        print(f"[{idx}] [{badge}{detail}] {m.league} | {m.name} | Tỷ số: {m.score}")
        if m.broadcasts:
            print(f"    Kênh phát sóng: {', '.join(m.broadcasts)}")
        for link in m.links:
            print(f"    -> {link['label']}: {link['url']}")
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tool tổng hợp trận bóng đá trực tiếp & link công khai/chính thức."
    )
    parser.add_argument(
        "--league",
        default="all_sports",
        help="Mã bộ môn/giải ESPN (mặc định: all_sports; ví dụ: soccer/all, basketball/nba, tennis/atp)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Chỉ hiển thị các trận đang đá trực tiếp",
    )
    parser.add_argument(
        "--search",
        default="",
        help="Lọc theo tên đội, giải đấu hoặc kênh phát sóng",
    )
    parser.add_argument(
        "--export",
        default="",
        help="Xuất kết quả ra file (.json hoặc .csv)",
    )
    parser.add_argument(
        "--scan-url",
        default="",
        help="Quét các link bóng đá/trực tiếp công khai từ một URL trang web cụ thể",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Mở giao diện web local",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Cổng chạy web UI (mặc định: biến môi trường PORT hoặc 8080)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.web:
        run_server(port=args.port)
        return 0

    if args.scan_url:
        try:
            links = fetch_public_page_links(args.scan_url)
        except Exception as exc:  # noqa: BLE001
            print(f"Lỗi khi quét URL: {exc}", file=sys.stderr)
            return 1
        if not links:
            print("Không tìm thấy link phù hợp.")
            return 0
        for item in links:
            print(f"- {item['label']}: {item['url']}")
        return 0

    try:
        if args.league == "all_sports":
            matches = fetch_all_sports_matches()
        else:
            raw = fetch_espn_scoreboard(league=args.league)
            matches = parse_espn_events(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"Lỗi khi lấy dữ liệu: {exc}", file=sys.stderr)
        return 1

    filtered = filter_matches(matches, live_only=args.live, query=args.search)
    _print_matches(filtered)

    if args.export:
        if args.export.lower().endswith(".csv"):
            out = export_csv(filtered, args.export)
        else:
            out = export_json(filtered, args.export)
        print(f"Đã xuất {len(filtered)} trận ra: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
