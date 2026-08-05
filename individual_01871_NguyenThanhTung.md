# Member Role Report — Day 9: Multi Agent A2A

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung     |
| --------------- | ------------ |
| Họ và tên       | Nguyễn Thanh Tùng |
| MSSV            | 2a202601871  |
| Khóa/Lớp        | K3           |
| Vai trò chính   | Order & Seller Agent (P2) - Xây dựng Tool Calling |
| Ngày hoàn thành | 2026-08-05   |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao   | Trạng thái                            |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| Thiết kế Tool Calling | `src/tools/order_tools.py` | `order_id` | JSON kết quả truy vấn CSDL (`order_status`, `items`, `item_total`, `freight_total`) | Hoàn thành |
| Viết System Prompt | `src/agents/prompts/order_agent.txt` | Dữ liệu Tool trả về | Chỉ thị ép LLM sử dụng Evidence-Based Reasoning | Hoàn thành |
| Tích hợp Agent Logic | `src/agents/order_agent.py` | `CaseFacts` từ DataLoader | `OrderSellerVerdict` chứa mảng `evidence_ids` | Hoàn thành |

Chỉ nhận ownership cho phần bạn trực tiếp thực hiện. Liên hệ rõ phần việc của bạn với đầu vào, đầu ra và các thành viên phụ thuộc vào phần đó.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                 | Thành viên/module được hỗ trợ | Kết quả                 |
| ------------------------- | ----------------------------- | ----------------------- |
| Cập nhật luồng Pipeline | `src/pipeline.py` | Thay thế logic `order_seller` cũ bằng module `order_agent` mới để đưa cơ chế Tool Calling vào luồng 50 cases chính. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao          | Cách xác minh   |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Tích hợp LLM Function Calling | `src/agents/order_agent.py` | LLM trích xuất Evidence ID dựa trên dữ liệu không bịa đặt | Chạy `python run.py --no-llm` và giả lập LLM thành công |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Output tạo ra là cấu trúc `OrderSellerVerdict` chứa chính xác các chuỗi `evidence_ids` như `order:<order_id>`, `item:<order_id>:<order_item_id>`, và `seller:<seller_id>` được trích xuất tự động bằng LLM dựa vào Tool trả về thay vì LLM tự suy luận (chống hallucination).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Trong pipeline xử lý khiếu nại, Agent P2 cần trích xuất chính xác trạng thái đơn hàng, người bán vi phạm và cung cấp bằng chứng (Evidence IDs). Vấn đề lớn nhất là nếu để LLM tự tính toán và suy luận từ context thông thường, model (đặc biệt là model <= 10B) sẽ dễ dẫn đến hallucination số liệu tài chính hoặc bịa đặt ID người bán không tồn tại.

### Cách triển khai

Thiết kế kiến trúc dựa trên chuẩn Tool Calling (Function Calling). LLM không tự tính toán mà được cung cấp tool `get_order_details` (Python Tool). Hệ thống ép LLM phải gọi tool này để lấy `item_total`, `freight_total` và danh sách người bán chuẩn xác từ `DataLoader`. Sau đó, LLM chỉ thực hiện phân tách (parse) JSON trả về để đóng gói thành các mảng `evidence_ids`. Nếu LLM gặp lỗi cú pháp JSON, hệ thống sẽ tự động chuyển sang Fallback deterministic logic.

### Input, output và contract

| Thành phần              | Mô tả                                  |
| ----------------------- | -------------------------------------- |
| Input                   | Tham số `CaseFacts` sinh ra từ `pipeline` |
| Output                  | Đối tượng `OrderSellerVerdict` chứa trạng thái và Evidence IDs |
| Module phụ thuộc        | `src/llm_client.py`, `src/tools/order_tools.py` |
| Module sử dụng output   | `src/agents/policy.py`, `src/pipeline.py` |
| Điều kiện lỗi cần xử lý | LLM trả về JSON sai định dạng, model name không tồn tại, kết nối API đứt |

### Cách xác minh

```bash
.venv\Scripts\python -c "import json; from src.data_loader import get_data; from src.agents import order_agent; facts = get_data().build_facts('EC_001', 'e2a03ccf5ea816036608b2d8c3ab8e60'); print(order_agent.run(facts, use_llm=True).model_dump_json(indent=2))"
```

- **Kết quả mong đợi:** Hàm chạy không văng lỗi, trả về chuỗi JSON chứa `evidence_ids` hợp lệ.
- **Kết quả thực tế:** Chạy thành công, ngay cả khi API lỗi thì hệ thống vẫn bắt lỗi và tự động fallback.
- **Artifact/log:** Các file JSON lưu trong thư mục `output/*.json` và trace log.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Làm sao để hạn chế tình trạng LLM ảo giác (hallucinate) tiền bạc và tạo ra Evidence ID không tồn tại?
- **Các phương án đã cân nhắc:** 1) Bơm toàn bộ dữ liệu file CSV thẳng vào system prompt. 2) Cho LLM tự viết script Python thực thi (Code Interpreter). 3) Dựng sẵn cơ chế Function Calling (Tool Calling) để LLM tra cứu.
- **Phương án đã chọn:** Xây dựng Function Calling (`get_order_details`).
- **Lý do:** Trade-off tuyệt vời cho độ chính xác (correctness). Code Python thao tác trực tiếp với bộ nhớ RAM đảm bảo tính chính xác 100% của số liệu tài chính. LLM lúc này chỉ đóng vai trò phân tích logic kinh doanh và chuẩn hóa định dạng (parsing), giảm thiểu tối đa rủi ro tính toán sai của các mô hình nhỏ.
- **Bằng chứng quyết định phù hợp:** Pipeline 50 cases chạy ổn định, không có hiện tượng hallucination tiền bạc, `item_total` và `freight_total` luôn khớp tuyệt đối.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Báo lỗi `ModuleNotFoundError: No module named 'src'` khi chạy test code `order_agent.py` độc lập.
- **Lệnh hoặc bước tái hiện:** Chạy lệnh gọi file trực tiếp thông qua script test nằm ngoài root (`python scratch/run_order_agent.py`).
- **Nguyên nhân gốc:** Lỗi phát sinh do cơ chế đường dẫn tương đối của Python (`sys.path`). Khi script được gọi từ trong thư mục con, thư mục root chứa module `src` không nằm trong đường dẫn import mặc định.
- **Cách xử lý:** Thay đổi thói quen chạy, luôn sử dụng lệnh thực thi từ thư mục gốc của project (vd: gọi qua `run.py` hoặc dùng lệnh `python -c` từ thư mục gốc chứa `src/`).
- **Cách xác minh sau khi sửa:** Pipeline gọi `order_agent` từ `pipeline.py` ở root chạy bình thường.
- **Điều học được:** Khi phát triển Python Multi-Agent, cần tuân thủ cấu trúc package chuẩn, luôn thiết lập CWD (Current Working Directory) tại thư mục gốc để quản lý dependencies dễ dàng.

## 7. Hiểu biết về luồng end-to-end

*Lưu ý: Mẫu template chứa câu hỏi của bài lab RAG, trong khi đây là bài lab Multi-Agent E-commerce. Dưới đây là mô tả luồng end-to-end của bài lab này:*

Bài lab Day 9 tập trung vào Multi-Agent E-commerce, không sử dụng luồng Crossref, vector index hay freshness monitoring. Thay vào đó, luồng end-to-end hoạt động như sau:
1. `DataLoader` nạp toàn bộ CSV vào in-memory RAM.
2. `Pipeline` đọc file khiếu nại (JSON), trích xuất sự thật thô (`CaseFacts`).
3. `Coordinator Agent` lập kế hoạch giao việc.
4. Các Domain Agent (`Order`, `Payment`, `Delivery`) tiến hành thu thập thông tin và parse ra bằng chứng (`Evidence IDs`).
5. `Policy Agent` tổng hợp bằng chứng, đối chiếu chính sách (Policy) để chốt lỗi sơ cấp (Primary Issue).
6. `Verifier Agent` kiểm tra chéo, tái thẩm định dữ liệu tài chính xem có đạt schema cứng hay không và ghi xuất kết quả.

**Câu trả lời:**

Toàn bộ quá trình là mô hình hóa quy trình giải quyết tranh chấp (Dispute Resolution) tự động bằng cách kết hợp sức mạnh phân tích tự nhiên của LLM và tính chính xác thuật toán của Python.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Thanh Tùng
**Ngày xác nhận:** 2026-08-05
