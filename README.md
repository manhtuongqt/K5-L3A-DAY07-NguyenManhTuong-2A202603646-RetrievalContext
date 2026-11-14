# Day 7 — Agentic RAG

## Bài làm cá nhân

**Nguyễn Mạnh Tường — 2A202603646 — L3A.** Repo này triển khai phần cơ bản Day07; bonus chưa thực hiện.

Tôi sử dụng lại 312 chunk B của tài liệu Python ở Day06, embedding BGE-small-en-v1.5 384 chiều và Qdrant persistent. Agent gọi model thật qua endpoint cấu hình local, chọn truy xuất bằng tool, đọc context có nguồn rồi trả lời với citation hoặc từ chối khi thiếu bằng chứng. Ba phương pháp được so sánh là **Dense, BM25 và Hybrid RRF**.

Đề và starter gốc vẫn ở phía dưới. Code bài làm nằm trong `src/`, chương trình chạy ở `scripts/`; fixture và mock test không phải kết quả benchmark thật.

### Cách chạy

Yêu cầu Python 3.11+, mạng để tải model lần đầu, API model hoạt động cho phần agent. Retrieval chạy CPU local, không cần Docker. Chỉ mở một tiến trình dùng cùng path Qdrant tại một thời điểm.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 scripts/prepare_data.py
```

`prepare_data.py` tự tải nguồn Day06 từ commit đã khóa và tạo embedding/index thật. Nếu có checkout Day06 trên máy, có thể dùng `--day6-root ../K5-L3-Day06-DataIngestionEngineering` để tái sử dụng model/vector đã kiểm tra hash. Không cần database của máy người làm. Chi tiết tại [docs/RETRIEVAL.md](docs/RETRIEVAL.md).

Sao chép `.env.example` thành `.env`, điền key/base URL/model của tài khoản được phép sử dụng. File `.env` được Git bỏ qua. Không điền key thật vào `.env.example` và không gửi key vào chat.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_environment.py
.\.venv\Scripts\python.exe -X utf8 scripts/check_environment.py --probe
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

`--probe` và các lệnh chạy agent có gọi API, có thể phát sinh phí. Tên alias model và usage do gateway báo được lưu đúng nguồn; không mặc định xác minh được model upstream. Native cost chưa rõ đơn vị không được gọi là USD hoặc miễn phí.

### Benchmark và thứ tự thí nghiệm

Bộ câu hỏi có **17 dev** (15 có đáp án, 2 thiếu evidence) và **7 test** (5 có đáp án, 2 thiếu evidence). Năm câu test mới khác bộ test đã phân tích ở Day06. Benchmark/gold/protocol được khóa trước truy xuất; model chỉ nhận ID, câu hỏi và filter đã có trong yêu cầu.

- [Protocol](benchmark/protocol.json) · [khóa](benchmark/lock.json) · [gói review nguồn](benchmark/REVIEW.md).
- [Xác nhận benchmark hiện tại](results/audit/benchmark_human_confirmation.json) được ghi riêng sau khi người học review. Trạng thái pending trong lock/packet gốc là lịch sử lúc tạo, không được sửa để làm sai hash.
- Không chạy lại `build_benchmark.py` lên bộ đã khóa sau khi xem kết quả. Khi nghiên cứu bộ mới, tạo một phiên bản/output riêng và đánh giá lại.

**Muốn chạy lại từ đầu:** các run đã nộp được giữ nguyên. Lệnh dưới tạo workspace mới trong `.local/`, dựng lại dữ liệu/index từ remote và so sánh ba ranking dev, không gọi API model trả lời:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/reproduce.py
```

Đã chạy kiểm chứng lệnh này: [reproduction_cli.json](results/reproduction_cli.json). Thêm `--api-dev` nếu muốn gọi model thật để chạy lại bốn cấu hình dev ở workspace mới; có thể phát sinh phí và cần chấm lại các output mới. Không sao chép xác nhận nhãn cũ sang output mới. Trong workspace gốc, đổi evaluator sau khi đã có run sẽ bị kiểm tra signature chặn resume; đây là bảo toàn lịch sử, không phải lý do xóa run cũ.

Các lệnh riêng bên dưới mô tả thứ tự thí nghiệm; dùng trong workspace mới có dữ liệu/env tương ứng nếu muốn tạo một thí nghiệm mới.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/eval_retrieval.py --split dev --method dense
.\.venv\Scripts\python.exe -X utf8 scripts/eval_retrieval.py --split dev --method bm25
.\.venv\Scripts\python.exe -X utf8 scripts/eval_retrieval.py --split dev --method hybrid
.\.venv\Scripts\python.exe -X utf8 scripts/run_experiments.py --split dev --configs C0 C1 C2 C3 --workers 2
```

C0 là baseline dense; C1 BM25; C2 cải thiện bằng rank fusion; C3 thử thêm context (top-k 5, budget 8.000 ký tự). C0–C2 dùng top-k 3, budget 4.000 ký tự. Mọi cấu hình dùng cùng model, policy filter và một lượt search tối đa; vẫn có lượt model tiếp theo để answer/abstain. Thông số này là lựa chọn thí nghiệm, không phải giới hạn bắt buộc của đề.

Runner lưu từng case ngay khi hoàn thành. Nếu ngắt, chạy lại đúng lệnh để tiếp tục các case chưa có; không thay kết quả lỗi bằng một lần chạy đẹp hơn. Nếu đổi code/config, dùng một phiên bản thử nghiệm mới và giữ run cũ. Các script retrieval ghi đè output cùng tên, vì vậy phải dùng `--output` khác khi muốn đo lại mà giữ kết quả gốc.

Sau dev, đọc trace và điền/kiểm tra nhãn context, answer, citation và abstention cùng lý do tại `results/audit/dev/`. Xác nhận của người học gắn với hash cụ thể; không tự động phê duyệt nhãn do AI soạn nháp. Sau khi đã đủ nhãn và xác nhận:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/freeze_selection.py
```

Lệnh lưu `results/selection.json` trước test và từ chối chọn lại khi đã có selection/test. Lấy ID cấu hình được chọn từ file đó rồi chạy test với **C0 và cấu hình được chọn**, không phải mặc định coi C3 là tốt nhất:

```powershell
# Run đã nộp chọn C2 bằng dev, trước test.
.\.venv\Scripts\python.exe -X utf8 scripts/run_experiments.py --split test --configs C0 C2 --workers 2
```

Runner kiểm tra model, cấu hình, code và benchmark đã freeze. Đọc cả năm câu test có đáp án và hai câu thiếu evidence của từng cấu hình, chấm nguồn thực sự hỗ trợ câu trả lời. Từ chối câu có đáp án được chấm 0; lỗi hệ thống được báo riêng, không đổi thành từ chối đúng.

### Đọc kết quả và demo

<!-- DAY07_RESULTS_START -->
Cấu hình **C2** được chọn bằng dev trước test. Strict dev **17/17 (100.0%)**; strict test **7/7 (100.0%)**. Baseline test **6/7 (85.7%)**. Chỉ số strict yêu cầu cả câu trả lời và citation đạt, hoặc từ chối đúng. Xem [báo cáo đầy đủ](report/individual/2A202603646_NguyenManhTuong.md), [selection](results/selection.json) và [bảng test](results/metrics_test.json).
<!-- DAY07_RESULTS_END -->

Kết quả cần đọc theo ba tầng: **Hit@1/Hit@3** của query gốc, **Context Evidence Rate** trong context thực gửi model, và **chất lượng câu trả lời/citation/abstention**. Không dùng score retrieval để tự chấm câu trả lời đúng. Citation được audit theo từng ID duy nhất trong mỗi câu trả lời; đếm cả ID inline trong lời từ chối và báo riêng số lần xuất hiện.

Tài liệu hoàn thiện bài làm: [báo cáo cá nhân](report/individual/2A202603646_NguyenManhTuong.md), [hướng dẫn demo](docs/DEMO.md), [đối chiếu gate](docs/GATE_CHECKLIST.md), [nguồn và giấy phép](THIRD_PARTY_NOTICES.md). Các tài liệu kết quả được chốt sau khi chạy/audit xong.

---

## Đề bài gốc

**Bài cá nhân · Python 3.11+ · tiếp nối Day 6**

Dùng embedding và vector store từ Day 6 để xây một agent biết tìm bằng chứng, trả lời có nguồn và nhận biết khi không đủ thông tin. Bạn tự chọn kiến trúc, số tool và cách tổ chức retrieval.

> **Tùy chọn:** [Gợi ý dùng AI để lập trình](AGENT_SETUP.md) giúp bạn làm lab; phần này không bắt buộc và không tính điểm.

## Bài cần làm

![Agent tìm tài liệu trong kho Day 6 và trả lời có nguồn](assets/retrieval-pipeline.svg)

1. Kết nối dữ liệu, embedding và vector store Day 6.
2. Xây agent dùng model thật và ít nhất một khả năng truy xuất dữ liệu. Agent có thể dùng nhiều tool và nhiều lượt gọi.
3. Thử **ít nhất 3 phương pháp retrieval khác nhau**, trong đó có dense retrieval dùng vector store Day 6. Tự chọn các phương pháp còn lại; xem [gợi ý](GUIDE.md#2-thử-các-phương-pháp-retrieval).
4. Thử nhiều cấu hình, benchmark, phân tích lỗi và chọn cấu hình tốt trên **dev**; sau đó đánh giá trên **test**.

Benchmark tối thiểu có **24 câu**: dev gồm 15 câu có đáp án và 2 câu thiếu bằng chứng; test gồm 5 câu có đáp án và 2 câu thiếu bằng chứng. Xem [benchmark](BENCHMARK.md) và [rubric](RUBRIC.md).

## Thử thách nâng cao · +15 điểm

Index một tài liệu thực tế từ **100 trang** có bảng, ảnh và biểu đồ; xây agent truy xuất và trả lời các câu hỏi về nội dung đó. Hoàn thành [thử thách nâng cao](ADVANCED.md) và đạt **ít nhất 90% benchmark test** để nhận 15 điểm bonus. Phần cơ bản tối đa 85 điểm; toàn bài tối đa 100 điểm.

## Bắt đầu

1. Đọc [hướng dẫn](GUIDE.md), [rubric](RUBRIC.md) và [quy tắc](RULES.md).
2. Tạo repo cá nhân theo [cách nộp bài](SUBMISSION.md), chuẩn bị đầu ra Day 6 và model hỗ trợ tool calling.
3. Dùng hoặc thay thế [starter](starter/README.md); bạn cần kết nối model và vector store thật.
4. Chạy `python -m unittest discover -s tests -v`. Test mock chỉ kiểm tra code, không phải benchmark agent thật.

![Các bước thử nghiệm trên dev và đánh giá trên test](assets/experiment-loop.svg)

Nộp code, cách chạy, cấu hình, benchmark, trace và [báo cáo](report/individual/MSSV_HoTen.md). Thời gian ở [checkpoints](CHECKPOINTS.md) là gợi ý, có thể điều chỉnh theo lớp và phạm vi thử nghiệm.
