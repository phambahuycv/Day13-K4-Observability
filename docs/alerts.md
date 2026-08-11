# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1: High Latency (P95 > 3s)

- Tên: high_latency_p95
- Severity: warning
- SLI/SLO liên quan: latency_p95_ms (Objective: 3000ms, Target: 99.5%)
- Điều kiện và thời gian duy trì: latency_p95 > 3000ms kéo dài trong 5 phút.
- Ảnh hưởng tới người dùng: Người dùng phải chờ đợi lâu để nhận được câu trả lời từ AI, gây trải nghiệm kém và có thể dẫn đến timeout ở client.
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra Dashboard phần biểu đồ Latency xem sự gia tăng này là đột biến (spike) hay tăng đều.
  2. Truy cập Langfuse, lọc các trace có thời gian thực thi > 3000ms, xem waterfall để xác định nguyên nhân là do RAG (retrieval) hay LLM (generation) chậm.
  3. Kiểm tra log hệ thống xem có lỗi kết nối mạng hoặc timeout tới các dịch vụ bên ngoài (như vector DB, LLM API) không.
- Mitigation tạm thời: Bật chế độ "fallback" bỏ qua bước RAG phức tạp hoặc chuyển sang model LLM nhỏ hơn (nhanh hơn) nếu nguyên nhân do LLM quá tải.
- Owner: on-call-engineer

## Alert 2: Elevated Error Rate (> 5%)

- Tên: elevated_error_rate
- Severity: critical
- SLI/SLO liên quan: error_rate_pct (Objective: 2%, Target: 99.0%)
- Điều kiện và thời gian duy trì: error_rate_pct > 5% kéo dài trong 3 phút.
- Ảnh hưởng tới người dùng: Ứng dụng không phản hồi, người dùng nhận được thông báo lỗi liên tục khi chat, gián đoạn hoàn toàn luồng nghiệp vụ.
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra Dashboard phần Error Breakdown để xem loại lỗi nào (error_type) đang chiếm tỷ lệ cao nhất (ví dụ: LLMAPIError, RAGTimeout, RateLimit).
  2. Lấy Correlation ID của một vài request bị lỗi từ log và tìm kiếm trên Langfuse (hoặc grep trong file log) để xem chi tiết Stack Trace.
  3. Kiểm tra trạng thái (Status Page) của nhà cung cấp LLM hoặc hạ tầng database xem có sự cố diện rộng nào không.
- Mitigation tạm thời: Nếu do LLM provider lỗi, thử switch (chuyển đổi) sang API key dự phòng hoặc mô hình LLM fallback. Nếu do quá tải, có thể bật cơ chế Rate Limiting gắt gao hơn để bảo vệ hệ thống.
- Owner: on-call-engineer

## Alert 3: Cost Budget Exceeded (> $2.5/ngày)

- Tên: cost_budget_exceeded
- Severity: warning
- SLI/SLO liên quan: daily_cost_usd (Objective: 2.5, Target: 100.0%)
- Điều kiện và thời gian duy trì: Tổng chi phí trong ngày (daily_cost_usd) vượt quá $2.5.
- Ảnh hưởng tới người dùng: Không ảnh hưởng trực tiếp tới người dùng, nhưng ảnh hưởng nghiêm trọng đến ngân sách vận hành của doanh nghiệp.
- Ba bước kiểm tra đầu tiên:
  1. Xem biểu đồ Traffic và Tokens trên Dashboard để đối chiếu: Chi phí tăng do lượng người dùng tăng đột biến hay do số lượng token mỗi request đột nhiên tăng cao?
  2. Truy cập Langfuse để phân tích độ dài prompt (Input tokens). Có khả năng RAG đang kéo về quá nhiều context không cần thiết làm phình to prompt.
  3. Kiểm tra xem có người dùng/IP nào đang spam hoặc gọi API bất thường (DDoS, Bot) không.
- Mitigation tạm thời: Bật cơ chế giới hạn số lượng token đầu ra (max_tokens) hoặc tắt/giảm bớt số lượng tài liệu (top_k) mà RAG kéo về. Chặn IP nếu phát hiện bị spam.
- Owner: team-lead
