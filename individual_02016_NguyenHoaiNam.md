# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                             |
| --------------- | ---------------------------------------------------- |
| Họ và tên       | Nguyễn Hoài Nam                                       |
| MSSV            | 02016                                                 |
| Khóa/Lớp        | K3                                                    |
| Vai trò chính   | Coordinator & Verifier — thiết kế kiến trúc, ra quyết định kỹ thuật |
| Ngày hoàn thành | 2026-08-05                                            |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Kiến trúc tổng thể | `architecture.md` | README EC_POLICY_V1 | Sơ đồ agent, bảng quyền truy cập, luồng handoff | Hoàn thành |
| Coordinator Agent | `src/agents/coordinator.py` — `plan()`, `summarize()` | `CaseFacts` | `DispatchPlan`, câu tổng hợp cuối | Hoàn thành |
| Pipeline thực thi | `src/pipeline.py` — `process_case()` | file input JSON | `CaseOutput` + 10 event trace/case | Hoàn thành |
| Verifier Agent | `src/agents/verifier.py` — `run()`, `_checks()` | `CaseFacts` + `PolicyVerdict` | Output đã xác minh + báo cáo kiểm tra | Hoàn thành |
| LLM client | `src/llm_client.py` — `call_json()` | prompt hệ thống + user | dict đã parse, hoặc `None` | Hoàn thành |
| Trace & metadata | `src/trace.py` — `Tracer`, `write_metadata()` | sự kiện từ pipeline | `logging/trace.jsonl`, `logging/metadata.json` | Hoàn thành |

Vai trò của tôi là **thiết kế và ra quyết định kỹ thuật**: xác định ranh giới giữa
phần tính toán deterministic và phần suy luận bằng LLM, thiết kế cơ chế phủ quyết
của Verifier, và chốt cấu hình model sau khi đo thực tế. Tôi không nhận ownership
phần nghiệp vụ của Policy Agent hay tầng nạp dữ liệu.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Dựng môi trường chung | Cả nhóm | `requirements.txt` cài sạch vào venv Python 3.11, import 9 package pass |
| Bảo mật repo | Cả nhóm | `.gitignore` + `.env.example`; xác minh bằng `git check-ignore` rằng `.env` và `.venv/` không lọt commit |
| Đo và chọn provider | Cả nhóm | Đo tốc độ Ollama local vs Groq, đưa ra khuyến nghị có số liệu |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Thiết kế ranh giới deterministic / LLM | `architecture.md` §1, §4 | Bảng phân quyền truy cập dữ liệu | Script đối chiếu doc với code |
| Nâng Coordinator thành agent điều phối thật | `src/agents/coordinator.py` | `dispatch_plan` xuất hiện trong trace mỗi case | `grep dispatch_plan logging/trace.jsonl` |
| Cơ chế phủ quyết của Verifier | `src/agents/verifier.py` | `confidence` sinh từ mức đồng thuận | Trường `agreed`/`source` trong trace |
| Bốn lớp chống hard gate | `schemas.py`, `llm_client.py` | 50/50 output pass validate schema | `pytest -q`, script validate output |
| Chốt model ≤ 10B | `src/config.py` | `llama-3.1-8b-instant` (8B) | Truy vấn `/v1/models` của Groq |

Một output cụ thể mà phần việc của tôi tạo ra:

`logging/trace.jsonl` — mỗi case sinh đúng 10 event theo thứ tự
`case_start → facts_extracted → dispatch_plan → handoff ×4 → verified → summary → case_done`.
Đây là bằng chứng kiểm chứng được rằng hệ thống có phân công và handoff thật giữa
các agent, không phải một prompt duy nhất được đặt nhiều tên.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Đề ra hai ràng buộc kéo ngược chiều nhau. README §9.1 giới hạn **mỗi agent chỉ dùng
model ≤ 10B tham số**. README §7 lại nói **không có điểm** cho việc đặt tên nhiều
agent nhưng xử lý nằm trong một prompt duy nhất.

Model 7–8B làm tệ đúng ba thứ bài này chấm nặng nhất: cộng `payment_value` nhiều
dòng rồi làm tròn 2 chữ số (20% điểm), so sánh timestamp khi hai mốc gần nhau
(quyết định rule 3/4/6), và giữ đúng thứ tự ưu tiên 6 rule (thêm 45%). Nhưng nếu
viết thuần Python rồi dán nhãn agent lên thì mất điểm kiến trúc.

Phần việc của tôi là tìm ranh giới cho cả hai ràng buộc cùng thỏa mãn.

### Cách triển khai

Tôi chia hệ thống theo **loại việc**, không theo tầng kỹ thuật:

- **Python lo trích xuất và số học.** Toàn bộ phép cộng tiền và so sánh ngày nằm
  trong `data_loader.build_facts()`. Không con số nào đi qua LLM để được tính.
- **LLM lo phán đoán và điều phối.** Coordinator quyết định dispatch agent nào,
  Policy chọn `primary_issue` từ 6 rule. Cả hai quyết định đều có hiệu lực thật.
- **Verifier có quyền phủ quyết.** Python chạy lại `rules.decide()` và so với kết
  luận của Policy. Lệch thì lấy kết quả deterministic.

Điểm tôi cân nhắc lâu nhất là quyền phủ quyết này có phải "giả vờ dùng agent"
không. Kết luận là không: README §7 định nghĩa Verifier Agent đúng là *"kiểm tra ID,
số tiền và schema trước khi ghi file"*, nên đây là làm đúng vai đề giao, không phải
lách. Đổi lại, tôi biến chính sự bất đồng đó thành tín hiệu có ích — `confidence`
lấy từ mức đồng thuận giữa hai đường suy luận (0.95 khi trùng, 0.60 khi phải phủ
quyết) thay vì điền một hằng số bịa.

Về quyền truy cập, tôi đặt ra ranh giới: **không agent nào được đọc CSV trực tiếp**,
tất cả chỉ nhận `CaseFacts` đã trích sẵn. Ba domain agent còn không thấy verdict của
nhau, nên bằng chứng đưa lên Policy là độc lập thật chứ không hùa theo agent chạy
trước.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `input/EC_XXX.json` (`case_id`, `claimed_order_id`, `message`) |
| Output | `output/EC_XXX.json` theo schema README §6, đã qua pydantic validate |
| Module phụ thuộc | `data_loader.py` (CaseFacts), `rules.py` (engine deterministic) |
| Module sử dụng output | Verifier ghi file; `trace.py` ghi log handoff |
| Điều kiện lỗi cần xử lý | LLM trả JSON hỏng; provider rate-limit 429; order không có trong CSV; đơn không có item row; đơn chưa giao (`delivered_late = None`) |

### Cách xác minh

```bash
pytest -q
python -m src.llm_client
python run.py --no-llm
python run.py
```

- **Kết quả mong đợi:** 20 test pass; health check OK; 50/50 case sinh output hợp lệ.
- **Kết quả thực tế:** `20 passed in 0.09s`; health check `OK` trong 1.3s;
  `--no-llm` xong 50/50 trong 1.1s; lượt chạy LLM thật đo được 3.2s/case ở case đơn lẻ.
- **Artifact/log:** `logging/trace.jsonl`, `logging/metadata.json`, `output/EC_*.json`.
  Không chứa secret — API key chỉ nằm trong `.env` và đã bị `.gitignore` chặn.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Bản đầu tiên của hệ thống có `coordinator.py` chỉ là một hàm Python
  gọi các agent theo thứ tự cứng. Nó không "giao việc" theo đúng nghĩa README §7 mô
  tả cho Coordinator Agent — đây là lỗ hổng kiến trúc tôi phát hiện khi rà lại đề.

- **Các phương án đã cân nhắc:**
  1. Giữ nguyên hàm Python, chấp nhận mất điểm phần "phân công".
  2. Để model 8B tự do chọn agent nào chạy, không ràng buộc.
  3. Model quyết định dispatch thật, nhưng Python áp sàn: `policy` và `verifier`
     luôn chạy, kế hoạch rỗng hoặc bịa tên agent thì chạy cả ba domain agent.

- **Phương án đã chọn:** Phương án 3.

- **Lý do:** Phương án 1 mất điểm kiến trúc. Phương án 2 rủi ro: model bỏ sót agent
  là mất bằng chứng, mà 15% điểm nằm ở evidence. Phương án 3 giữ được quyết định
  **có hiệu lực thật** — agent không được dispatch thì thật sự không gọi LLM, tiết
  kiệm call trong giới hạn 2h30 — nhưng bỏ sót chỉ mất phần diễn giải, không bao giờ
  làm sai số tiền, vì `CaseFacts` đã tính đủ từ trước và Verifier còn tính lại lần nữa.

- **Bằng chứng quyết định phù hợp:** Sau khi đổi kiến trúc, 6 case Olist thật đại
  diện 6 nhánh rule vẫn ra đúng `primary_issue` cả 6, và 20/20 test vẫn pass. Trace
  mỗi case tăng từ 8 lên 10 event, có thêm `dispatch_plan` và `summary`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Lệnh `python run.py --no-llm` treo vô hạn. Trước đó smoke test 6
  case bằng cùng cấu hình lại chạy xong trong vài giây, nên ban đầu tôi nghi do số
  lượng case chứ không nghi cấu hình.

- **Lệnh tái hiện:** `python run.py --no-llm` với 50 file trong `input/`.

- **Nguyên nhân gốc:** Cờ `--no-llm` không thật sự tắt LLM. Nó chỉ trỏ `LLM_BASE_URL`
  sang một port chết để ép call fail nhanh. Nhưng mỗi call vẫn phải đi hết thang
  retry của `tenacity` **và** thang retry nội bộ của SDK `openai`, mỗi lớp đều có
  exponential backoff. Nặng hơn: `@retry(stop=stop_after_attempt(...))` được áp lúc
  **import**, nên việc hạ `config.LLM_MAX_RETRIES` xuống 1 lúc runtime hoàn toàn vô
  tác dụng. 50 case × 6 call × nhiều vòng backoff = treo.

- **Cách xử lý:** Thêm cờ `config.USE_LLM`. `call_json()` kiểm tra cờ này và trả
  `None` ngay từ đầu, không chạm tới client. Đây là công tắc thật, không phải mẹo
  làm cho call fail nhanh hơn.

- **Cách xác minh sau khi sửa:** `python run.py --no-llm` → **50/50 case trong 1.1
  giây**, 50 file output đều pass validate schema.

- **Điều học được:** Decorator của `tenacity` đóng băng tham số ở thời điểm import.
  Muốn đổi hành vi retry lúc runtime phải truyền callable hoặc kiểm tra cờ bên trong
  hàm — sửa biến config sau khi module đã load thì không có tác dụng. Bài học rộng
  hơn: "tắt tính năng" phải là đường thoát sớm, không phải làm cho nó thất bại nhanh.

Hai lỗi nhỏ hơn cũng do tôi phát hiện và sửa:

- `.env` để trống khiến `os.getenv("LLM_API_KEY", "ollama")` trả **chuỗi rỗng** chứ
  không phải giá trị mặc định, làm SDK báo `Missing credentials`. Sửa thành
  `os.getenv(...) or "ollama"`.
- Kế hoạch ban đầu chạy model local. Đo thực tế cho thấy `vicuna:7b-v1.5-q5_1` trên
  máy mất **4 phút 07 giây** cho một call nguội. Với 300 call thì không khả thi, nên
  tôi chuyển sang Groq — health check chỉ mất **1.3 giây**.

## 7. Hiểu biết về luồng end-to-end

> Ghi chú: 5 câu hỏi trong mẫu gốc nói về Crossref, vector index và corrupted/repaired
> test set — đó là nội dung của lab RAG, không phải Day 9. Tôi trả lời theo đúng
> luồng của bài này.

**1. Dữ liệu đi từ input đến output như thế nào?**

`input/EC_XXX.json` cung cấp `claimed_order_id`. `data_loader` dùng ID đó join 4 file
CSV (`orders`, `order_items`, `order_payments`, `sellers`), cộng tiền và so ngày bằng
Python, trả về `CaseFacts`. Coordinator đọc facts rồi lập kế hoạch dispatch. Các
domain agent được giao việc sẽ phân tích và handoff verdict sang Policy. Policy chọn
`primary_issue`. Verifier tính lại bằng Python, phủ quyết nếu lệch, rồi ghi
`output/EC_XXX.json`.

**2. Vì sao không để LLM tự tính tiền và so ngày?**

Vì ràng buộc ≤ 10B. Model 8B cộng nhiều dòng tiền hay lệch cent và so timestamp sai
khi hai mốc gần nhau. Mà `financial_resolution` chiếm 20% điểm, còn so sánh ngày lại
quyết định chọn rule 3, 4 hay 6 — kéo theo 45% điểm nữa. Giao phần này cho Python là
loại bỏ hoàn toàn một lớp rủi ro, trong khi phần suy luận vẫn do agent thật đảm nhiệm.

**3. Evidence ID được đảm bảo có thật bằng cách nào?**

Ba lớp. `rules.build_evidence()` chỉ dựng ID từ row có thật trong `CaseFacts`. Trong
`order_seller.py`, seller ID mà model đề xuất bị lọc qua `f.seller_ids` — model nêu
seller không thuộc đơn thì bị loại. Cuối cùng `verifier._checks()` dựng tập ID hợp lệ
rồi đối chiếu từng evidence trước khi ghi file.

**4. Vì sao Verifier được quyền phủ quyết Policy, mà vẫn không phải "giả vờ dùng agent"?**

Vì README §7 giao cho Verifier Agent đúng việc đó: kiểm tra ID, số tiền và schema
trước khi ghi file. Policy vẫn suy luận thật và quyết định thật; Verifier chỉ chặn
khi kết luận mâu thuẫn với dữ liệu kiểm chứng được. Bất đồng không bị vứt đi mà được
ghi vào trace và biến thành `confidence` thấp hơn.

**5. Dựa vào artifact nào để nói hệ thống chạy đúng?**

Ba thứ: `pytest` 20 test cho engine deterministic (trong đó 5 test riêng cho va chạm
thứ tự ưu tiên); `logging/trace.jsonl` với 10 event mỗi case chứng minh có handoff
thật; và `output/EC_*.json` được validate lại bằng chính schema pydantic, kiểm tra
đủ 50 file, đúng giới hạn 5 ID / 10 evidence / 5 action.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hoài Nam
**Ngày xác nhận:** 2026-08-05
