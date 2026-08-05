# Báo cáo cá nhân — P4 Policy Agent

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | [Trần Đoàn Quang Vũ] |
| MSSV | [2A202601999] |
| Khóa/Lớp | K3 |
| Vai trò chính | P4 — Policy Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Policy Agent | `src/agents/policy.py`, hàm `run` | `CaseFacts` và verdict đã làm sạch từ Order/Seller, Payment, Delivery Agent | `PolicyVerdict` gửi Verifier | Hoàn thành |
| Prompt pháp chế | `src/agents/prompts/policy.txt` | Sáu rule EC_POLICY_V1 tại README §4 | Chỉ dẫn if/else theo đúng thứ tự ưu tiên | Hoàn thành |
| Policy tools | `src/tools/policy_tools.py` | `CaseFacts`, primary issue và matched rule | Mapping mã, kiểm tra ưu tiên, confidence | Hoàn thành |
| Compatibility entry point | `src/agents/policy_agent.py` | Lời gọi Policy Agent | Export hàm `run` mà không phá pipeline cũ | Hoàn thành |
| Kiểm thử rule | `tests/test_rules.py` | Các `CaseFacts` kiểm thử | Kiểm tra priority, mapping và fallback | Hoàn thành mã nguồn; chưa chạy được do Python local bị lỗi |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Giữ tương thích schema | P5 Coordinator/Verifier | Bổ sung `confidence` có giá trị mặc định, không đổi cách gọi hiện tại |
| Chặn quyết định sai của LLM | Verifier | Policy chỉ chấp nhận draft khi issue và số rule đều khớp deterministic baseline |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Mã hóa sáu rule theo đúng ưu tiên | `src/rules.py`, `src/agents/prompts/policy.txt` | Rule đầu tiên khớp là kết quả cuối cùng | `python -m pytest tests/test_rules.py -q` |
| Ánh xạ quyết định | `map_policy_codes` | Root-cause code và resolution action hợp lệ | Test `test_policy_code_mapping` |
| Chống MAST/sai thứ tự | `is_priority_consistent` | Loại draft chọn rule thấp hơn dù mã issue hợp lệ | Test `test_policy_rejects_valid_but_lower_priority_llm_choice` |
| Cô lập dữ liệu | `src/agents/policy.py` | Không gọi database, CSV hoặc API dữ liệu; chỉ gọi LLM với facts đã làm sạch | Kiểm tra import và luồng `run` |
| Tạo bản nháp quyết định | `PolicyVerdict` | Assessment fields, ranked cause, responsible parties, refund, actions và confidence | Kiểm tra object trả về từ `policy.run` |

Artifact cụ thể của P4 là `PolicyVerdict` được Policy Agent bàn giao cho Verifier. Verdict chứa `primary_issue`, `case_status`, `ranked_causes`, `responsible_parties`, `recommended_refund_brl`, `resolution_actions`, `confidence`, evidence và trạng thái LLM.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Policy Agent là “thẩm phán” của pipeline. Agent phải chọn đúng một kết luận từ dữ liệu đã kiểm chứng, áp dụng rule theo đúng thứ tự ưu tiên, xác định số tiền hoàn, nguyên nhân gốc, bên chịu trách nhiệm và hành động xử lý. Nếu LLM chỉ chọn một mã hợp lệ nhưng bỏ qua rule ưu tiên cao hơn thì toàn bộ primary issue, refund và responsible party có thể sai.

### Cách triển khai

Sáu dòng trong README §4 được biểu diễn thành chuỗi `if / else if` và phải dừng tại điều kiện đầu tiên khớp:

1. Đơn bị hủy nhưng đã thanh toán.
2. Đơn unavailable nhưng đã thanh toán.
3. Giao trễ do seller bàn giao sau hạn.
4. Giao trễ dù seller bàn giao đúng hạn, quy trách nhiệm logistics.
5. Nhiều payment row nhưng đã đối soát hợp lệ.
6. Giao đúng hạn và payment khớp, bác yêu cầu hoàn do giao trễ.

Với đơn nhiều item, chỉ seller có item `handoff_after_limit = true`, tương ứng seller nằm trong `late_seller_ids`, bị coi là vi phạm.

LLM nhận prompt yêu cầu phân tích tuần tự trong nội bộ và chỉ trả JSON tóm tắt. Hệ thống không yêu cầu xuất chain-of-thought chi tiết. Sau khi nhận JSON, `is_priority_consistent` đối chiếu cả `primary_issue` và `matched_rule` với deterministic engine. Nếu không khớp, Policy Agent bỏ draft và dùng kết quả deterministic.

Refund và các mã quy định không được để LLM tự sáng tạo. Python ánh xạ kết quả theo bảng cố định:

| Primary issue | Root cause | Responsible party | Refund | Action |
| --- | --- | --- | ---: | --- |
| `canceled_order_paid` | `ORDER_CANCELED_AFTER_PAYMENT` | `platform/OLIST_PLATFORM` | Tổng payment | `issue_full_refund` |
| `unavailable_order_paid` | `ORDER_UNAVAILABLE_AFTER_PAYMENT` | `platform/OLIST_PLATFORM` | Tổng payment | `issue_full_refund` |
| `late_delivery_seller` | `SELLER_HANDOFF_AFTER_LIMIT` | Seller vi phạm | Tổng freight | `refund_freight` |
| `late_delivery_logistics` | `CARRIER_DELIVERED_AFTER_ESTIMATE` | `logistics_provider/LOGISTICS_PROVIDER` | Tổng freight | `refund_freight` |
| `valid_split_payment` | `MULTIPLE_PAYMENTS_RECONCILED` | Không có | 0 | `explain_valid_split_payment` |
| `unsupported_late_claim` | `DELIVERY_WITHIN_ESTIMATE` | Không có | 0 | `reject_late_refund` |

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `CaseFacts`, `OrderSellerVerdict`, `PaymentVerdict`, `DeliveryVerdict` |
| Output | `PolicyVerdict` đã validate bằng Pydantic |
| Module phụ thuộc | `src/rules.py`, `src/schemas.py`, `src/llm_client.py`, `src/tools/policy_tools.py` |
| Module sử dụng output | `src/agents/verifier.py`, được điều phối bởi `src/pipeline.py` |
| Điều kiện lỗi cần xử lý | LLM timeout, JSON lỗi, issue không hợp lệ, sai matched rule hoặc chọn rule thấp hơn |

### Cách xác minh

```powershell
python -m pytest tests/test_rules.py -q
python -m pytest tests/test_rules.py -q -k "policy"
```

- **Kết quả mong đợi:** Toàn bộ test pass; draft sai ưu tiên bị từ chối; mapping trả đúng root cause/action.
- **Kết quả thực tế:** `git diff --check` pass. Chưa chạy được pytest trên máy hiện tại vì `.venv` trỏ tới Python 3.10 đã bị gỡ và không có Python launcher khả dụng.
- **Artifact/log:** `src/agents/prompts/policy.txt`, `src/tools/policy_tools.py`, `tests/test_rules.py`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** LLM có thể trả về một `primary_issue` nằm trong enum nhưng vẫn sai vì bỏ qua rule ưu tiên cao hơn.
- **Các phương án đã cân nhắc:** Tin kết quả LLM nếu mã hợp lệ; hoặc đối chiếu LLM với deterministic priority engine trước khi sử dụng.
- **Phương án đã chọn:** Chỉ chấp nhận draft khi cả `primary_issue` và `matched_rule` khớp rule đầu tiên do deterministic engine xác định.
- **Lý do:** Bảo đảm đúng chính sách, ổn định với model nhỏ dưới 10B, đồng thời vẫn giữ LLM tham gia suy luận và handoff.
- **Bằng chứng quyết định phù hợp:** Test `test_policy_rejects_valid_but_lower_priority_llm_choice` mô phỏng giao trễ đồng thời có split payment; rule logistics phải thắng rule split payment.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `No Python at ... Python.3.10 ... python.exe` và `py : The term 'py' is not recognized`.
- **Lệnh tái hiện:** `.\.venv\Scripts\python.exe -m pytest -q` và `py -m pytest -q`.
- **Nguyên nhân gốc:** Virtual environment được tạo bằng bản Python 3.10 không còn tồn tại; máy hiện tại cũng không có Python launcher trong `PATH`.
- **Cách xử lý:** Không xóa môi trường của nhóm hoặc báo test pass giả. Ghi rõ blocker và cung cấp lệnh chạy sau khi cài/tạo lại Python environment.
- **Cách xác minh sau khi sửa môi trường:** Chạy `python -m pytest tests/test_rules.py -q`.
- **Điều học được:** Phải phân biệt mã đã qua kiểm tra tĩnh với test runtime đã thực sự chạy; không báo hoàn thành kiểm thử khi interpreter chưa hoạt động.

## 7. Hiểu biết về luồng end-to-end

1. Input `EC_xxx.json` cung cấp case ID, order ID và nội dung khiếu nại. `data_loader` truy xuất, join dữ liệu Olist và tạo `CaseFacts` đã làm sạch.
2. Coordinator lập kế hoạch dispatch. Order/Seller, Payment và Delivery Agent phân tích domain của mình rồi handoff verdict cho Policy Agent.
3. Policy Agent không truy xuất lại dữ liệu. Agent áp dụng EC_POLICY_V1 theo thứ tự, tạo quyết định nháp gồm assessment, root cause, responsible party, refund, resolution action và confidence.
4. Verifier tính lại deterministic decision, kiểm tra evidence ID, số tiền và schema. Nếu Policy Agent lệch, Verifier phủ quyết trước khi ghi output.
5. Pipeline ghi `CaseOutput` vào `output/EC_xxx.json` và ghi handoff/audit vào trace. Một case đạt yêu cầu khi schema hợp lệ, issue đúng, entity/evidence có thật, refund đúng và action khớp chính sách.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** [Trần Đoàn Quang Vũ]

**Ngày xác nhận:** 2026-08-05
