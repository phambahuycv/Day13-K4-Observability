# Dashboard runtime — Role 3 CP2

Dashboard được triển khai bằng Streamlit tại `scripts/dashboard_app.py`. Nguồn dữ liệu chuẩn là `data/logs.jsonl`; dashboard không lấy số liệu từ state trong bộ nhớ của API.

## Chạy dashboard

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --env-file .env
streamlit run scripts/dashboard_app.py
```

Mặc định API chạy tại `http://127.0.0.1:8000` và Streamlit tại `http://localhost:8501`. Nếu cổng 8000 đang được Docker/WSL sử dụng, có thể chạy API với `--port 8001`; khi tạo load test cần trỏ script tới cùng cổng.

Dashboard dùng cửa sổ trượt **60 phút gần nhất** theo timestamp UTC `ts` và tự refresh mỗi **30 giây**. Dòng JSON không hợp lệ hoặc không có timestamp hợp lệ được bỏ qua để dashboard vẫn tiếp tục hoạt động.

## Sáu panel và công thức

| Panel | Event/field | Công thức hiển thị | Đơn vị | Threshold/SLO |
|---|---|---|---|---|
| Latency | `response_sent.latency_ms` | P50, P95, P99 | ms | P95 ≤ 3.000 ms |
| Traffic | `request_received` | tổng request; `count / max(observed_minutes, 1)` | requests/minute | ≥ 1 request/phút |
| Errors | `request_received`, `request_failed`, `error_type` | `request_failed / request_received * 100`; count theo `error_type` | % | ≤ 2% |
| Cost | `response_sent.cost_usd` | sum theo phút; tổng trong cửa sổ | USD | tổng ≤ 2,5 USD |
| Tokens | `response_sent.tokens_in`, `tokens_out` | tổng riêng input/output và tổng chung | tokens | tổng ≤ 50.000 tokens |
| Quality | `response_sent.quality_score` | trung bình cộng | score 0–1 | ≥ 0,75 |

Mỗi panel hiển thị tên, đơn vị, threshold và trạng thái đạt/vi phạm. Các biểu đồ latency, traffic và cost có đường hoặc cột SLO tham chiếu.

## Kết quả kiểm chứng ngày 2026-08-11

### Baseline

Chạy `python scripts/load_test.py --concurrency 5` và đo trong cửa sổ 60 phút:

- Traffic: 40 request, 1,62 requests/minute.
- Latency: P50 150 ms, P95 151 ms, P99 151 ms.
- Error rate: 0%, không có error breakdown.
- Total cost: 0,08172 USD.
- Tokens: 1.320 input, 5.184 output, 6.504 tổng.
- Quality average: 0,88.

Evidence: [dashboard-6-panels.png](../submission/evidence/dashboard-6-panels.png).

### Incident `rag_slow`

Sau khi bật `rag_slow` và chạy cùng load test, P95 tăng rõ rệt từ **151 ms lên 2.652 ms**. Traffic vẫn được ghi nhận ở 1,64 requests/minute và dashboard đọc được log mới sau refresh. Incident đã được tắt sau khi chụp evidence.

Evidence: [dashboard-rag-slow.png](../submission/evidence/dashboard-rag-slow.png).

### Incident `tool_fail`

Sau khi bật `tool_fail`, 10 request trả HTTP 500. Dashboard ghi nhận:

- Error rate: **16,67%**.
- Error breakdown: **RuntimeError = 10**.
- Tổng request trong cửa sổ: 60.

Incident đã được tắt sau khi chụp evidence.

Evidence: [dashboard-errors.png](../submission/evidence/dashboard-errors.png).

## Contract và evidence

```powershell
python scripts/validate_dashboard.py
```

Kết quả: `HỢP LỆ: 6/6 panel có trong dashboard contract.`

Evidence: [dashboard-validator.png](../submission/evidence/dashboard-validator.png).

`config/dashboard.yaml` vẫn là contract chấm điểm và không bị thay đổi trong CP2 này. Các file của Role 4 (`config/slo.yaml`, `config/alert_rules.yaml`, `docs/alerts.md`) cũng không bị chỉnh sửa.
