# Báo cáo Lab 08

## 1. Sinh viên thực hiện

- Họ và tên: Lê Thành Long
- Repo/commit: local
- Ngày: 11/05/2026

## 2. Kiến trúc (Architecture)

Đồ thị (graph) của em bao gồm các node cốt lõi mô phỏng vòng đời xử lý ticket hỗ trợ:
- `intake_node`: Chuẩn hóa câu truy vấn của người dùng và đưa vào State.
- `classify_node`: Đưa ra quyết định điều hướng (`route` và mức độ uy rủi ro `risk_level`) sử dụng LLM tương thích chuẩn OpenAI (`ChatOpenAI`). Node này tự động parse kết quả dạng JSON từ LLM và có xử lý cắt bỏ phần suy luận của các Reasoning model (ví dụ: các thẻ `<think>`).
- Các bộ định tuyến có điều kiện (Conditional routers): Bao gồm `route_after_classify`, `route_after_evaluate`, `route_after_retry`, và `route_after_approval` giúp điều phối luồng trạng thái tới các node tiếp theo một cách hợp lý.
- `tool_node`: Thực thi công cụ tương ứng với yêu cầu và thêm kết quả vào quá trình lưu trữ.
- `evaluate_node`: Kiểm tra kết quả thực thi và gán cờ `"needs_retry"` hoặc `"success"`.
- `retry_or_fallback_node`: Theo dõi số lần lỗi để gọi lại `tool_node` nếu gặp lỗi, cho tới khi chạm đến giới hạn `max_attempts` thì sẽ chuyển hướng sang `dead_letter_node`.
- `risky_action_node` & `approval_node`: Đảm bảo quy trình phê duyệt của con người (HITL - Human-in-The-Loop) cho các thao tác rủi ro cao trước khi được thực thi.
- `answer_node`: Trả về câu trả lời cuối cùng dựa trên bối cảnh nhận được từ các tool.
- `finalize_node`: Ghi nhận sự kiện hoàn thành và chuyển trạng thái END.

## 3. Cấu trúc trạng thái (State schema)

Trạng thái tuân theo TypedDict được định nghĩa chặt chẽ để dễ dàng tra cứu dấu vết giữa các luồng tương tác nhiều bước.

| Field | Reducer | Mục đích |
|---|---|---|
| messages | add | Lưu giữ lịch sử tương tác qua nhiều bước gọi tool |
| tool_results | add | Audit tất cả đầu ra từ mọi lời gọi tool (không ghi đè) |
| errors | add | Lưu nhật ký lỗi theo thời gian để phục vụ cơ chế retry có giới hạn |
| events | add | Audit các event được phát ra bởi các nodes để tracing và theo dõi metrics |
| route | overwrite | Theo dõi tuyến đường (route) hiện tại đang chạy tới đâu |
| evaluation_result| overwrite | Đánh giá hiện tại về tool check (needs_retry vs success) |
| attempt | overwrite | Lưu chỉ số (index) đếm số lần retry hiện tại |

## 4. Kết quả chạy kịch bản (Scenario results)

| Kịch bản (Scenario)| Expected route | Actual route | Success | Retries | Interrupts |
|-------------------|----------------|--------------|--------:|--------:|-----------:|
| S01_simple        | simple         | simple       | True    |       0 |          0 |
| S02_tool          | tool           | tool         | True    |       0 |          0 |
| S03_missing       | missing_info   | missing_info | True    |       0 |          0 |
| S04_risky         | risky          | risky        | True    |       0 |          1 |
| S05_error         | error          | error        | True    |       2 |          0 |
| S06_delete        | risky          | risky        | True    |       0 |          1 |
| S07_dead_letter   | error          | error        | True    |       1 |          0 |

## 5. Phân tích lỗi (Failure analysis)

1. **Lỗi khi chạy tool hoặc retry:** Em quản lý logic này bằng biến đếm `attempt` rõ ràng. Nếu kết quả tool trả về lỗi, `evaluate_node` sẽ đặt trạng thái là `"needs_retry"`. Khi số lần lặp đạt tới ngưỡng `max_attempts` thiết lập trong kịch bản (scenario), hệ thống sẽ thoát vòng lặp và trực tiếp rơi vào route an toàn `dead_letter`.
2. **Hành động rủi ro không có sự phê duyệt:** Nếu LLM phân loại truy vấn thuộc nhóm rủi ro `risky` (ví dụ: refund, delete), hệ thống sẽ rẽ nhánh an toàn tới `risky_action`. Điều này đảm bảo trạng thái phải đi qua node `approval_node`, ngăn chặn hoàn toàn việc các hành động quan trọng thực thi tự động mà không có sự đánh giá từ con người (HITL).

## 6. Minh chứng phục hồi / lưu trữ (Persistence / recovery evidence)

Em đã cấu hình linh hoạt cơ chế checkpointer sử dụng `MemorySaver()` cùng `thread_id=thread-<id>` giúp tách biệt hoàn toàn trạng thái của các buổi chạy scenario khác nhau. Hệ thống đảm bảo khôi phục trạng thái thông qua việc cấp ID truyền trong `config={"configurable": {"thread_id": ...}}`. Kiến trúc này cũng đã sẵn sàng để em nâng cấp lên `SqliteSaver` gốc của LangGraph thông qua chuỗi kết nối trong config.

## 7. Phần mở rộng em đã thực hiện (Extension work)

- Em đã tích hợp vòng lặp retry có kiểm soát (bounded retry loops), ánh xạ trực tiếp với con đếm trạng thái để đảm bảo fail-safe.
- Thiết lập module phân tích file JSON linh hoạt để tự xử lý lời gọi LLM từ `ChatOpenAI` bên trong `classify_node`. Bằng cách tự động dọn dẹp các thẻ suy luận (`<think>`), đồ thị agent của em có thể inference ổn định với cả các LLM dạng Reasoning (như DeepSeek, Minimax, Qwen...).
- Em cũng tích hợp cấu hình đọc biến môi trường thông qua thư viện `python-dotenv` để giữ bí mật file key.

## 8. Kế hoạch cải tiến của em (Improvement plan)

Nếu có thêm thời gian, em sẽ ưu tiên:
- Tích hợp giao diện UI qua Streamlit để người dùng (human testers) có thể dễ dàng bấm nút Approve/Reject trực quan, kết nối trực tiếp với chức năng `interrupt()`.
- Production hóa hệ thống Database với PostgreSQL nhằm lưu các States chuẩn xuống một sơ đồ cơ sở dữ liệu thay vì Memory, thiết lập cơ chế Time Travel vững chắc hơn.
- Cải thiện kiến trúc thực thi Tool-call, thay thế các kết quả `mock-tool-result` mô phỏng bằng các Executor Python thực tế được bao bọc dưới tập API của `ToolNode` (để hỗ trợ parallel fan-out).
