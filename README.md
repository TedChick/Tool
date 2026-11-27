# Live Football Link Aggregator

Tool tổng hợp các trận bóng đá đang diễn ra trực tiếp (trong nước & quốc tế) kèm kênh phát sóng chính thức và đường link công khai.

## Yêu cầu
- Python 3.10+ (không cần cài thêm thư viện ngoài).

## Cách sử dụng

### 1. Chạy giao diện Web local
```bash
python main.py --web
```
Mở trình duyệt tại `http://127.0.0.1:8080`.

### 2. Chạy trên Terminal (CLI)
- Xem tất cả trận hôm nay:
  ```bash
  python main.py
  ```
- Chỉ xem các trận **đang đá trực tiếp (LIVE)**:
  ```bash
  python main.py --live
  ```
- Lọc theo đội bóng, giải đấu hoặc kênh phát sóng (ví dụ `Vietnam`, `Premier League`, `VTV`):
  ```bash
  python main.py --search "Vietnam"
  ```
- Xuất kết quả ra file JSON hoặc CSV:
  ```bash
  python main.py --live --export live_matches.json
  python main.py --live --export live_matches.csv
  ```
- Quét nhanh các link bóng đá/trực tiếp công khai từ một trang lịch thi đấu bất kỳ:
  ```bash
  python main.py --scan-url "https://example.com/lich-thi-dau"
  ```

## Chạy trên Cloud 24/7 miễn phí (Render.com)
1. Tạo 1 repository trên GitHub và đẩy toàn bộ thư mục `C:\DuLieu\Tool` lên đó.
2. Đăng nhập [Render.com](https://render.com), chọn **New + -> Blueprint** (hoặc **Web Service**), kết nối tới repository vừa tạo.
3. Render sẽ tự đọc file `render.yaml` và chạy lệnh `python main.py --web`. Sau vài chục giây bạn sẽ có link `https://...onrender.com` để xem trên cả điện thoại và máy tính mà không cần bật PC.

## Chạy kiểm thử
```bash
python -m unittest discover -s tests -v
```
