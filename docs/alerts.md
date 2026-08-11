# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1: High Latency (P95 > 3s)

- Tên: high_latency_p95
- Severity: warning
- SLI/SLO liên quan: latency_p95_ms (Objective: 3000ms, Target: 99.5%)
- Điều kiện và thời gian duy trì: latency_p95 > 3000ms kéo dài trong 5 phút.
- Ảnh hưởng tới người dùng: Trải nghiệm chờ đợi phản hồi AI cực kỳ chậm, nguy cơ timeout ở Client.
- Ba bước kiểm tra đầu tiên:
  1. Click vào link tự động đi kèm Alert: `[Grafana Latency Dashboard (Time Range: {{alert_time}})]`
  2. Click vào link: `[Langfuse Traces (>3000ms filters)]` để kiểm tra Waterfall span (tìm xem span `retrieve` hay `generate` đang bị nghẽn).
  3. Kiểm tra log hệ thống: Lọc các correlation_id có thời gian chạy cao để đọc log stack trace.
- Mitigation tạm thời: Dập lửa bằng cách hạ tải hoặc tắt RAG tạm thời thông qua API Feature Flag.
  ```bash
  curl -X POST http://localhost:8000/incidents/disable_rag/enable
  ```
- Owner: on-call-engineer

## Alert 2: Elevated Error Rate (> 5%)

- Tên: elevated_error_rate
- Severity: critical
- SLI/SLO liên quan: error_rate_pct (Objective: 2%, Target: 99.0%)
- Điều kiện và thời gian duy trì: error_rate_pct > 5% kéo dài trong 3 phút.
- Ảnh hưởng tới người dùng: Toàn bộ luồng chat gián đoạn, người dùng liên tục nhận mã lỗi.
- Ba bước kiểm tra đầu tiên:
  1. Click vào link: `[Grafana Error Breakdown (Time Range: {{alert_time}})]` để khoanh vùng error_type.
  2. Lấy 3 `correlation_id` của request lỗi. Click vào `[Langfuse Trace by ID: {{correlation_id}}]` để xem.
  3. Đọc log của 3 request lỗi đó để tìm nguyên nhân gốc.
- Mitigation tạm thời: Chuyển đổi sang API/Model dự phòng (Fallback) ngay lập tức nếu lỗi đến từ LLM Provider.
  ```bash
  curl -X POST http://localhost:8000/incidents/fallback_model/enable
  ```
- Owner: on-call-engineer

## Alert 3 & 4: Cost Budget & Burn-Rate Spike

- Tên: cost_burn_rate_spike & cost_budget_exceeded
- Severity: critical / warning
- SLI/SLO liên quan: daily_cost_usd
- Điều kiện và thời gian duy trì: Tốc độ tiêu tiền tăng > 300% trong 15 phút HOẶC chạm ngưỡng $2.5/ngày.
- Ảnh hưởng tới người dùng: Không ảnh hưởng người dùng nhưng đe dọa ngân sách công ty do bị Bot Spam hoặc ddos tokens.
- Ba bước kiểm tra đầu tiên:
  1. Click vào link: `[Dashboard Traffic & Tokens (Time Range: {{alert_time}})]` - Xem cột traffic và `tokens_in` xem cái nào tăng vọt.
  2. Truy cập Langfuse: Kiểm tra Input Tokens của RAG xem có đang kéo về quá nhiều text rác không.
  3. Kiểm tra Logs để khoanh vùng IP hoặc user_id_hash đang gọi liên tục.
- Mitigation tạm thời: Khóa max_tokens lại mức cực thấp hoặc bật Rate Limiting gắt gao.
  ```bash
  curl -X POST http://localhost:8000/incidents/rate_limit_hard/enable
  ```
- Owner: team-lead / on-call-engineer
