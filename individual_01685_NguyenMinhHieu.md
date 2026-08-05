# Member Role Report — Day 9: Multi Agent A2A

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                 |
| --------------- | ---------------------------------------- |
| Họ và tên       | Nguyễn Minh Hiếu                      |
| MSSV            | 01685                         |
| Khóa/Lớp        | [K3]                                     |
| Vai trò chính   | Data & Contracts Engineer (P1)           |
| Ngày hoàn thành | 2024-08-05                               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao   | Trạng thái                            |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| DataLoader         | `tools/data_loader.py` | 9 file CSV của Olist | Object `CaseFacts` chứa thông tin order | Hoàn thành |
| Data Contracts     | `core/contracts.py` | Các trường dữ liệu thô | Pydantic Dataclass chuẩn hóa (`CaseFacts`, `Order`, `OrderItem`...) | Hoàn thành |
| Fixtures Generator | `scripts/generate_fixtures.py` | 3 file JSON input (EC_001 -> 003) | `tests/fixtures/sample_orders.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                 | Thành viên/module được hỗ trợ | Kết quả                 |
| ------------------------- | ----------------------------- | ----------------------- |
| Setup luồng Data & Cấu trúc | Cả nhóm                       | Đã tạo branch `feature/data` và cấu trúc thư mục chuẩn |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao          | Cách xác minh   |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Parse & Index Data    | `tools/data_loader.py`      | Index dữ liệu bằng pandas với độ phức tạp truy vấn O(1) | Chạy script trích xuất không lỗi |
| Chuẩn hóa Data Contract | `core/contracts.py`       | Cấu trúc Pydantic chặt chẽ cho toàn bộ entities | Kiểm tra schema JSON output |
| Sinh test fixtures    | `scripts/generate_fixtures.py` | File `sample_orders.json` chứa 3 cases mẫu | Chạy script generate_fixtures.py |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:
File `sample_orders.json` giúp team phát triển các Agent có thể lấy ngay thông tin thực tế của 3 order (như timestamps, items, sellers) để test Prompt mà không cần phải chạy lại module load CSV nặng nề mỗi lần debug.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Bài toán yêu cầu xử lý logic dựa trên bằng chứng (evidence-based). Nếu cho Agent trực tiếp đọc file CSV hoặc tự suy luận SQL, Agent rất dễ bị ảo giác (hallucinate) các cột không tồn tại hoặc nối (join) sai. Giải pháp của tôi là xây dựng lớp Data Loader để join sẵn các bảng và gói gọn vào một Data Contract chuẩn (`CaseFacts`), giúp các Agent chỉ việc tiêu thụ dữ liệu sạch.

### Cách triển khai
- Sử dụng Pandas để đọc 5 file CSV cốt lõi (`orders`, `customers`, `order_items`, `payments`, `sellers`).
- **Tối ưu hiệu năng:** Thay vì `merge` hoặc `loc` nhiều lần khi query, tôi dùng `set_index('order_id')` cho bảng 1-1 và dùng `groupby('order_id')` chuyển thành `dict` cho các bảng 1-n (items, payments). Việc này giúp hàm `get_case_facts` chạy ở tốc độ cực cao $O(1)$.
- Dùng `Pydantic` định nghĩa các dataclass. Điều này giúp dễ dàng chuyển đổi object sang JSON để truyền vào Prompt của Agent.

### Input, output và contract

| Thành phần              | Mô tả                                  |
| ----------------------- | -------------------------------------- |
| Input                   | `case_id`, `order_id` và `message` từ file input JSON |
| Output                  | Object `CaseFacts` chứa list các Items, Payments và thông tin Seller, Order |
| Module phụ thuộc        | Không có (Data layer nằm ở dưới cùng) |
| Module sử dụng output   | Coordinator Agent và các sub-agents sẽ tiêu thụ `CaseFacts` |
| Điều kiện lỗi cần xử lý | Order không tồn tại trong DB, thiếu thông tin Customer/Seller |

### Cách xác minh

```bash
python scripts/generate_fixtures.py
```

- **Kết quả mong đợi:** Script chạy thành công, báo "Data loaded and indexed", và extract được 3 case EC_001, 002, 003.
- **Kết quả thực tế:** Chạy hoàn thành trong chưa tới 1 phút, lưu file json chính xác.
- **Artifact/log:** `tests/fixtures/sample_orders.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần xử lý việc truy xuất thông tin của 50 đơn hàng từ các file CSV lớn (có file lên tới hàng chục MB).
- **Các phương án đã cân nhắc:** 
  1. Dùng SQLite memory database để Agent tự viết câu lệnh SQL query.
  2. Load toàn bộ lên Pandas DataFrame và dùng Pandas filter mỗi lần Agent yêu cầu.
  3. Load lên Pandas, pre-index tất cả theo `order_id` và trả về Pydantic Object cố định.
- **Phương án đã chọn:** Phương án 3 (Pre-index Pandas + Pydantic).
- **Lý do:** Trade-off ở đây là đánh đổi một chút bộ nhớ RAM (để lưu dict/index) lấy tốc độ $O(1)$ và tính chính xác tuyệt đối. LLM rất kém trong việc tự sinh câu query SQL phức tạp (dễ bị 0 điểm vì false evidence), nên việc fix cứng Data Contract `CaseFacts` sẽ khóa chặt schema, đảm bảo LLM không bao giờ hallucinate trường dữ liệu.
- **Bằng chứng quyết định phù hợp:** Script `generate_fixtures` trích xuất thông tin order với độ trễ gần như bằng 0 sau khi đã load xong vào RAM.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Lỗi khi Pydantic parse các trường ngày tháng (timestamp) bị trống (`NaN`) trong Pandas Dataframe thành chuỗi `"nan"` thay vì `None`.
- **Lệnh hoặc bước tái hiện:** Trích xuất một order chưa được giao hàng (thiếu `order_delivered_customer_date`).
- **Nguyên nhân gốc:** Pandas biểu diễn giá trị null bằng `float('nan')`, khi Pydantic cast sang string nó trở thành `"nan"`, làm sai logic check timestamp của Agent sau này.
- **Cách xử lý:** Viết thêm hàm helper `_clean_nan()` trong `DataLoader` để check `pd.isna(val)`. Nếu true thì trả về `None`, ngược lại mới ép kiểu `str(val)`.
- **Cách xác minh sau khi sửa:** Chạy lại file fixture, các trường ngày tháng trống hiện lên là `null` trong JSON.
- **Điều học được:** Luôn phải cẩn thận với cách Pandas handle missing values (NaN) khi kết nối với các hệ thống yêu cầu Strict Typing như Pydantic.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu đi vào hệ thống như thế nào?
2. Vai trò của Data Loader là gì?
3. Agent xử lý `CaseFacts` ra sao?
4. Việc trích xuất Data Contract trước mang lại lợi ích gì?

**Câu trả lời:**

1. **Dữ liệu đi vào hệ thống:** Hệ thống nhận input là một yêu cầu JSON của khách hàng (chứa `case_id` và `claimed_order_id`).
2. **Vai trò của Data Loader:** Thay vì bắt LLM mò mẫm dữ liệu, Data Loader sẽ query lập tức các file CSV Olist dựa trên `order_id` này để gom toàn bộ sự thật khách quan (facts) về thời điểm mua, lịch sử giao hàng, số tiền thanh toán, vào chung một object `CaseFacts`.
3. **Agent xử lý CaseFacts:** Các Agent (Order Agent, Payment Agent) sẽ nhận data JSON sinh ra từ `CaseFacts`, đọc và đối chiếu với các Rule (quy tắc bồi thường) để phân định lỗi thuộc về ai (Seller hay Logistics) mà không bị phụ thuộc vào lời nói dối của khách hàng.
4. **Lợi ích của Data Contract:** Nó chia tách hoàn toàn (decouple) tầng dữ liệu và tầng AI. Agent không cần biết dữ liệu đến từ CSV hay SQL, chúng chỉ cần xử lý JSON chuẩn. Đảm bảo input sạch.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Minh Hiếu
**Ngày xác nhận:** 2024-08-05
