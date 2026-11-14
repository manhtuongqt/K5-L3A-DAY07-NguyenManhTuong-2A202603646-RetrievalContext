# Báo cáo Day07 — Agentic RAG

Nguyễn Mạnh Tường · 2A202603646 · L3A. Phạm vi: phần cơ bản 85 điểm; chưa làm bonus.

## 1. Dữ liệu và benchmark

### 1.1. Dữ liệu Day06 và quyền sử dụng

Tôi dùng lại corpus Python 3.13 từ commit Day06 `64c4ab778f81ba5608d4b2b57315f6369aedd0fd`: 9 tài liệu chính thức, 69 đơn vị HTML có nội dung và 312 chunk B theo đoạn, tối đa 1.000 ký tự. Đây là đơn vị HTML đã chuẩn hóa, không phải trang PDF. Tôi giữ ID, text, source/page, metadata và offsets gốc; không chia lại để khớp câu hỏi. Nguồn/PSF License và 0BSD cho ví dụ: [notices](../../THIRD_PARTY_NOTICES.md), [source manifest](../../data/source_manifest.json), [adapter manifest](../../data/day6_manifest.json).

Embedding BAAI/bge-small-en-v1.5 ONNX quantized, revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55`, 384 chiều, CLS/L2, CPU. Query dùng prefix `Represent this sentence for searching relevant passages: ` đúng một lần; document không prefix. Giữ giới hạn 512 token của embedding và file hash trong [model lock](../../configs/embedding_model.json). Qdrant client 1.16.0 local persistent, collection `day07_B`, cosine exact, thư mục `.local/qdrant_day07`. Docker không cần cho cách chạy này; model trả lời là API riêng.

Vector B tái sử dụng có SHA256 `266db21df0190f393a3c8b2927ef49c1a96b70c42801b628d095bf7157278fc9`, trùng Day06. Script có thể tải nguồn đã pin và tái embedding/index từ đầu, không cần checkout hoặc database riêng của máy tôi.

### 1.2. Agent model và điều kiện chạy

Model cấu hình `claude-opus-5` qua `https://api.xah.io/v1`, giao thức OpenAI-compatible, temperature 0.0, max output 1600 token. Đây là alias và usage do gateway báo; tôi không tự xác minh upstream đằng sau tên model. Key chỉ nằm trong `.env`/biến môi trường; thông tin công khai tại [model config](../../configs/model.json).

Agent dùng native function calling: search, answer hoặc abstain. Lượt đầu chỉ cho search; hết ngân sách tìm chỉ còn answer/abstain. Mọi query và nội dung answer/abstain do model thật tạo, không lấy expected answer từ benchmark. Trace giữ request messages, tool schema, kết quả, context thực gửi, usage, lỗi và retry. Model call sửa định dạng không được tính là một lượt tìm dữ liệu mới.

### 1.3. Bộ câu hỏi và chống rò rỉ

Benchmark tối thiểu đủ 24 câu: dev 15 có evidence + 2 thiếu evidence; test 5 có evidence + 2 thiếu evidence. Dùng lại dev Day06 và viết năm test mới về chủ đề khác năm test Day06 đã thảo luận. Gold có nguồn/page/quote/offset, alternative là OR; câu thiếu evidence có full-corpus scan 69 đơn vị và lý do ngữ nghĩa, không suy từ việc top-k không tìm được.

[Protocol](../../benchmark/protocol.json), [lock](../../benchmark/lock.json), [absence checks](../../benchmark/absence_checks.json). Model chỉ nhận ID/question/filter, không nhận answerable, gold hoặc expected answer. Filter chỉ lấy từ phạm vi đã có trong câu hỏi, không dùng gold source/page. Bộ câu hỏi đã được tôi đối chiếu và xác nhận; [hồ sơ benchmark](../../results/audit/benchmark_human_confirmation.json).

## 2. Retrieval và thử nghiệm

### 2.1. Ba phương pháp

- Dense: query BGE → Qdrant exact cosine.
- BM25: Okapi k1=1.5, b=0.75, IDF dương; tokenize NFC/casefold/Unicode words, giữ underscore, không stemming. Corpus chính tiếng Anh; không tuyên bố đã tối ưu tiếng Việt.
- Hybrid RRF: lấy top10 dense + top10 BM25, cộng `1/(60+rank)`, không cộng raw cosine với raw BM25. Lưu branch rank/score; cùng corpus và filter policy.

### 2.2. Các cấu hình agent thực chạy

| ID | Retrieval | Top-k | Context budget gồm nguồn | Search tối đa | Giả thuyết |
|---|---|---:|---|---:|---|
| C0 | dense | 3 | 4,000 ký tự | 1 | Baseline dense retrieval. |
| C1 | bm25 | 3 | 4,000 ký tự | 1 | Lexical API-name matching. |
| C2 | hybrid | 3 | 4,000 ký tự | 1 | Improvement 1: dense+BM25 rank fusion. |
| C3 | hybrid | 5 | 8,000 ký tự | 1 | Improvement 2: larger context policy, same fused retriever. |

C2 và C3 là hai cấu hình nhằm cải thiện, có run riêng. C3 thay đồng thời top-k và budget nên chỉ đánh giá gói chính sách context, không tách riêng nhân quả từng yếu tố. Chạy một lần mỗi cấu hình; temperature 0 không bảo đảm API/gateway tái lập tuyệt đối, query model tạo giữa các run vẫn có thể khác.

### 2.3. Ranking query gốc, cutoff top-3

| Phương pháp | Split | Hit@1 | Evidence Hit@3 | Lỗi | Median search |
|---|---|---|---|---:|---|
| dense | dev | 12/15 (80.0%) | 13/15 (86.7%) | 0 | 12.70 ms |
| bm25 | dev | 12/15 (80.0%) | 12/15 (80.0%) | 0 | 1.48 ms |
| hybrid | dev | 13/15 (86.7%) | 13/15 (86.7%) | 0 | 15.30 ms |
| dense | test | 2/5 (40.0%) | 4/5 (80.0%) | 0 | 17.26 ms |
| hybrid | test | 3/5 (60.0%) | 5/5 (100.0%) | 0 | 16.21 ms |

Mẫu số retrieval chỉ có 15 dev hoặc 5 test **có đáp án**, không cộng câu thiếu evidence. Một hit yêu cầu một chunk giữ trọn evidence alternative, đúng source/page. Bảng trên là query gốc, không phải query model viết lại. [Trace retrieval](../../results/retrieval). Số kết quả thực trả về được lưu ở từng query; không ép đủ ba bằng dữ liệu giả.

### 2.4. Chọn context và Context Evidence Rate

Giữ nguyên chunk kèm header ID/source/page, loại trùng theo ID/text, ưu tiên rank từ lần tìm mới nhất rồi các candidate cũ còn hữu ích. Budget tính bằng ký tự gồm header/dấu phân cách, không phải token LLM. Không cắt âm thầm chunk. CER exact kiểm evidence thực nằm trong context cuối **đã gửi**; đọc ngữ nghĩa context bằng thang 0/1/2 riêng.

| Config/split | CER exact | Nhãn context 0/1/2 | Phân bố search call |
|---|---|---|---|
| C0/dev | 12/15 (80.0%) | 1/0/14 (n=15) | {"1": 17} |
| C1/dev | 14/15 (93.3%) | 1/0/13 (n=14) | {"1": 16} |
| C2/dev | 14/15 (93.3%) | 0/0/15 (n=15) | {"1": 17} |
| C3/dev | 13/15 (86.7%) | 1/0/14 (n=15) | {"1": 17} |
| C0/test | 5/5 (100.0%) | 0/0/5 (n=5) | {"1": 7} |
| C2/test | 5/5 (100.0%) | 0/0/5 (n=5) | {"1": 7} |

Exact quote là phép đo bảo thủ; context code/example có thể đủ nghĩa nhưng thiếu nguyên câu quote đã khóa. Vì vậy CER exact và nhãn context=2 không nhất thiết trùng. Tôi giữ nguyên gold và báo cả hai, không sửa quote sau test để tăng điểm.

Trước khi chọn/test, tôi sửa một lỗi **tổng hợp CER**: C1/D03 có đủ context đã gửi nhưng final action bị lỗi citation; aggregator cũ bỏ qua context khi status=error. CER C1 từ 13/15 thành 14/15; strict end-to-end vẫn 14/17. Không đổi model, query, raw trace, gold hoặc nhãn đã được tôi duyệt. [Lịch sử sửa và hash](../../results/history/metric_correction.json) giữ code cũ đúng byte. Lỗi câu trả lời không đồng nghĩa thiếu context.

## 3. Agent và đánh giá

### 3.1. Kết quả từ câu trả lời thực

| Config/split | Strict end-to-end | Tool use | Answer 0/1/2; mean | Citation hợp lệ | Answer có citation | Từ chối đúng | Từ chối nhầm | Lỗi |
|---|---|---|---|---|---|---|---|---:|
| C0/dev | 15/17 (88.2%) | 17/17 (100.0%) | 1/0/14; 1.87/2 | 15/16 (93.8%) | 14/14 (100.0%) | 2/2 (100.0%) | 1/15 (6.7%) | 0 |
| C1/dev | 14/17 (82.4%) | 16/16 (100.0%) | 1/0/13; 1.86/2 | 14/15 (93.3%) | 13/13 (100.0%) | 2/2 (100.0%) | 1/14 (7.1%) | 1 |
| C2/dev | 17/17 (100.0%) | 17/17 (100.0%) | 0/0/15; 2.00/2 | 16/16 (100.0%) | 15/15 (100.0%) | 2/2 (100.0%) | 0/15 (0.0%) | 0 |
| C3/dev | 16/17 (94.1%) | 17/17 (100.0%) | 1/0/14; 1.87/2 | 15/15 (100.0%) | 14/14 (100.0%) | 2/2 (100.0%) | 1/15 (6.7%) | 0 |
| C0/test | 6/7 (85.7%) | 7/7 (100.0%) | 0/0/5; 2.00/2 | 5/6 (83.3%) | 5/5 (100.0%) | 2/2 (100.0%) | 0/5 (0.0%) | 0 |
| C2/test | 7/7 (100.0%) | 7/7 (100.0%) | 0/0/5; 2.00/2 | 6/6 (100.0%) | 5/5 (100.0%) | 2/2 (100.0%) | 0/5 (0.0%) | 0 |

Strict end-to-end là chỉ số bổ sung trên **toàn bộ case lên lịch**: có đáp án cần answer=2 và citation hỗ trợ đủ, thiếu evidence cần từ chối đúng; lỗi vẫn không đạt. Grounded answer/context/citation/abstention là những metrics riêng theo BENCHMARK.md. Tool use và quality thành công có mẫu số công bố; lỗi được báo riêng, không giấu bằng cách đổi thành abstain hoặc bỏ khỏi tổng scheduled.

Citation được chấm theo từng **ID duy nhất trong mỗi câu trả lời**, đối chiếu tất cả điều kiện/claim gắn với ID đó; có cả ID inline trong reason abstain. Báo số lần xuất hiện riêng tại [usage/metrics](../../results/metrics_test.json). Evaluator dùng projection hợp nhất declared/inline IDs, giữ nguyên raw trace. ID có trong context hoặc model tự xác nhận không thay việc đọc nguồn. 0/0 được hiểu là N/A, không phải 100%.

### 3.2. Audit và trách nhiệm kiểm tra

Tôi đã đối chiếu bộ câu hỏi và bản chấm dev/test, xác nhận giữ các nhãn. Bản nháp được AI hỗ trợ chuẩn bị từ source/context/answer thật, sau đó được tôi review; đây không phải hai người chấm độc lập hoặc chấm mù. Hồ sơ exact-hash: [dev](../../results/audit/dev_human_confirmation.json), [test](../../results/audit/test_human_confirmation.json). Có 81 hàng chấm output được xác nhận; case lỗi không được dựng thành một câu trả lời để chấm.

Các packet và review JSON ban đầu giữ dòng pending để bảo toàn lịch sử; trạng thái hiện tại ở [status](../../results/audit/status.json), [confirmed view](../../results/audit/reviews_confirmed.json). Nếu nhãn/trace thay đổi, xác nhận hash cũ không tự áp dụng.

### 3.3. Nhãn từng ca test

| Config/query | Trạng thái | Nhãn | Lý do đối chiếu | Bằng chứng |
|---|---|---|---|---|
| C0/T01 | answered | answer=2; context=2; citation=[True]; abstain=None | The answer preserves all three escaping exceptions with ensure_ascii=False: quotation mark, reverse solidus and U+0000-U+001F control characters. These are explicitly listed in the cited source. | [trace](../../results/agent/test/C0/cases/T01.json) |
| C0/T02 | answered | answer=2; context=2; citation=[True]; abstain=None | The answer says the callback receives each JSON float as a string and None defaults to float(num_str); both required conditions are explicitly in its citation. | [trace](../../results/agent/test/C0/cases/T02.json) |
| C0/T03 | answered | answer=2; context=2; citation=[True]; abstain=None | The answer correctly gives extra fields as a list under restkey=None, missing fields filled by restval=None, the non-blank-row condition, and the optional fieldnames/first-row behavior. The cited paragraph supports all of these details. | [trace](../../results/agent/test/C0/cases/T03.json) |
| C0/T04 | answered | answer=2; context=2; citation=[False]; abstain=None | The answer correctly distinguishes physical lines from parsed records because records may span multiple lines. Its additional quoted-field/line-break example is supported elsewhere in the actual context by QUOTE_MINIMAL chunk 2788ee6e34ada6b0c2c01ee5bf11f7b1. However it cites only the line_num paragraph, which does not establish that extra quoting condition; answer grounding and citation validity are scored separately. | [trace](../../results/agent/test/C0/cases/T04.json) |
| C0/T05 | answered | answer=2; context=2; citation=[True, True]; abstain=None | The answer correctly states OSError for missing paths/symlink loops in strict mode, partial resolution and unchecked remainder in non-strict mode, and no exception for symlink loops in non-strict Python 3.13. The two citations collectively cover these behaviors and version condition. | [trace](../../results/agent/test/C0/cases/T05.json) |
| C0/TU01 | abstain | answer=None; context=None; citation=[]; abstain=True | The response explicitly declines a p95 latency guarantee and does not invent timings, workload measurements or Windows-specific performance. It accurately states the supplied CSV usage documentation lacks that guarantee. | [trace](../../results/agent/test/C0/cases/TU01.json) |
| C0/TU02 | abstain | answer=None; context=None; citation=[]; abstain=True | The response declines to provide a production backup bucket or retention period. Its auxiliary statement mapping Path.unlink to os.remove/os.unlink is actually visible in the supplied correspondence table, and it invents no backup configuration. | [trace](../../results/agent/test/C0/cases/TU02.json) |
| C2/T01 | answered | answer=2; context=2; citation=[True]; abstain=None | The answer preserves all three escaping exceptions with ensure_ascii=False: quotation mark, reverse solidus and U+0000-U+001F control characters. These are explicitly listed in the cited source. | [trace](../../results/agent/test/C2/cases/T01.json) |
| C2/T02 | answered | answer=2; context=2; citation=[True]; abstain=None | The answer says the callback receives each JSON float as a string and None defaults to float(num_str); both required conditions are explicitly in its citation. | [trace](../../results/agent/test/C2/cases/T02.json) |
| C2/T03 | answered | answer=2; context=2; citation=[True]; abstain=None | The answer gives the complete overflow/underflow distinction, extra values in a restkey list, missing fields filled by restval, both None defaults and the non-blank-row qualifier, all directly supported. | [trace](../../results/agent/test/C2/cases/T03.json) |
| C2/T04 | answered | answer=2; context=2; citation=[True]; abstain=None | The answer confines itself to the documented line-count versus record-count distinction and multi-line records. Unlike C0, it does not add a separately sourced quoted-field example. | [trace](../../results/agent/test/C2/cases/T04.json) |
| C2/T05 | answered | answer=2; context=2; citation=[True, True]; abstain=None | The answer correctly states OSError for missing paths/symlink loops in strict mode, partial resolution and unchecked remainder in non-strict mode, and no exception for symlink loops in non-strict Python 3.13. The two citations collectively cover these behaviors and version condition. | [trace](../../results/agent/test/C2/cases/T05.json) |
| C2/TU01 | abstain | answer=None; context=None; citation=[]; abstain=True | The response explicitly declines an unsupported p95 guarantee and supplies no guessed performance, upload-workload or Windows-specific timing. The missing deployment measurements match the frozen absence check. | [trace](../../results/agent/test/C2/cases/TU01.json) |
| C2/TU02 | abstain | answer=None; context=None; citation=[]; abstain=True | The response declines to invent the production project backup bucket or retention period. It only summarizes that the supplied Path.unlink material concerns deletion and does not contain private backup configuration. | [trace](../../results/agent/test/C2/cases/TU02.json) |

Packet nguồn/citation chi tiết: [test REVIEW](../../results/audit/test/REVIEW.md). Context chấm 0=không có evidence, 1=thiếu điều kiện/nguồn, 2=đủ; answer 0=sai/không hỗ trợ/từ chối nhầm, 1=đúng một phần, 2=đúng và đủ. Citation có nhãn hỗ trợ riêng cho từng ID và lý do.

## 4. Phân tích lỗi, cải thiện và quyết định

### 4.1. Các lỗi dev đã kiểm tra

1. **C0/D01 — tìm nhầm phương thức.** Context nói về `pop`, `index`, `del`, thiếu `list.remove`. Không dùng ValueError của index làm evidence cho remove. C0 từ chối nhầm, strict không đạt. C2 tìm đúng remove và trả lời có citation; C3 vẫn bỏ lỡ dù lấy năm chunk. Tên API và query model tạo ảnh hưởng kết quả, không thể chỉ tăng budget là xong.
2. **C0/D10 — câu đúng chưa chắc citation đủ.** Answer thêm qualifier `__all__`; toàn context có thông tin đó, nhưng sole citation được dẫn không hỗ trợ qualifier. Answer/context có thể chấm 2, citation vẫn sai. C2 dẫn nguồn hỗ trợ đủ, C3 không thêm điều kiện dư chưa được cite.
3. **C1/D02 — dẫn ví dụ thay cho claim hiệu năng.** Code queue example không tự chứng minh fast append/pop ở cả hai đầu. Đoạn giải thích đúng có trong context nhưng không phải ID được cite; không tự chấm citation đúng vì agent tình cờ đọc được nguồn khác.
4. **C1/D03 — định dạng citation sau repair vẫn sai.** Model đưa ID trong arguments nhưng không in `[id]` trong answer, runtime từ chối sau một lần sửa. Giữ nguyên status error và trace, không chạy lại để thay bằng kết quả thuận lợi. Context vẫn được tính riêng theo bằng chứng thực gửi.

Hai giả thuyết đo riêng: C2 bổ sung tín hiệu lexical cho dense, C3 thêm context để giữ điều kiện. Strict dev C0=15/17, C1=14/17, C2=17/17, C3=16/17. C2 cải thiện so với baseline trong run này; C3 không cải thiện thêm. Không suy từ một run rằng hybrid luôn tốt hoặc context lớn luôn xấu. [Audit dev](../../results/audit/dev/REVIEW.md).

### 4.2. Freeze và test

Tôi chọn **C2** bằng dev, lưu lúc `2026-11-14T09:09:02.330845+00:00` UTC trước mọi run test. Thứ tự chọn: strict dev, CER, ít từ chối nhầm, chi phí USD nếu đầy đủ, latency, ID. C2 thắng tiêu chí đầu nên không cần tie-break; giá USD unknown không được thay bằng 0. [Selection và hashes](../../results/selection.json).

Test giữ nguyên model/config/prompt/benchmark sau freeze. Baseline strict 6/7 (85.7%), C2 strict 7/7 (100.0%). Query gốc và query viết lại của agent được lưu riêng. Chỉ năm câu có đáp án và hai câu thiếu evidence mỗi cấu hình nên một câu làm tỷ lệ thay đổi lớn; không suy rộng ngoài corpus này. Test đã mở chỉ phục vụ đánh giá và phân tích, không chọn lại winner hoặc chỉnh để báo điểm test độc lập.

## 5. Thời gian, token và chi phí

| Config/split | Model call | Search call | Sửa action | Input/output token provider báo | Native cost đã báo | Median end-to-end |
|---|---:|---:|---:|---|---:|---|
| C0/dev | 37 | 17 | 3 | 24,743/2,746 | 74.02 | 12.10 s |
| C1/dev | 35 | 17 | 2 | 22,750/2,603 | 70.03 | 12.09 s |
| C2/dev | 34 | 17 | 0 | 21,547/2,573 | 68.04 | 10.93 s |
| C3/dev | 36 | 17 | 2 | 34,819/2,666 | 78.68 | 12.37 s |
| C0/test | 16 | 7 | 2 | 11,269/1,298 | 32.01 | 12.82 s |
| C2/test | 15 | 7 | 1 | 10,060/1,227 | 30.01 | 12.33 s |

Native cost là trường `usage.raw.x_ckey.cost`, **chưa xác minh đơn vị**, không quy thành USD. Giá USD của model là N/A; known subtotal 0 không có nghĩa miễn phí. Token là usage provider báo, có thể khác bộ đếm thực của upstream/gateway. Các request lỗi không có usage có chi phí không biết. [Rollup](../../results/usage_summary.json) phân biệt scope dev/test và số response có cost. Bảng không gồm smoke, tải model, cài môi trường hoặc điện/phần cứng. Retrieval embedding/vector/lexical local có phí API 0 USD, không phải tổng chi phí agent bằng 0.

Worker=2 chồng thời gian đợi API; lock tuần tự truy cập Qdrant/ONNX local. Thời gian trong bảng là mỗi case, không phải tổng wall-clock. Một lần đo mỗi cấu hình không chứng minh hiệu năng ổn định.

## 6. Tái lập, kiểm tra và trình bày

- [README](../../README.md) có cài đặt/env/prepare/dev/freeze/test; dependencies trực tiếp pin trong requirements, `requirements-lock.txt` là snapshot môi trường Windows đã chạy.
- `python -X utf8 scripts/run_tests.py`: **64 test**, 0 failure, 0 error, 0 skip; [log](../../results/tests.log). Test mock chỉ kiểm hành vi, không tạo số liệu benchmark model.
- [Tái tạo retrieval độc lập](../../results/retrieval_reproduction.json): tải remote pinned source và model, re-embed thật mất 84.5s, 14/14 kiểm tra qua, vector byte-identical. Đây là tái lập trên cùng môi trường Windows, chưa chứng minh xuyên nền tảng hoặc model API byte-identical.
- [Verifier dev](../../results/runtime_trace_verification_dev.json): 68 trace, 11523 kiểm tra; [verifier test](../../results/runtime_trace_verification_test.json): 14 trace, 2243 kiểm tra. Kiểm tra raw source/offset, exact context gửi, budget, native schemas, hash và không đưa gold vào request. Đây là integrity check, không thay audit ngữ nghĩa.
- Demo ba ca: C2/D01 answered có nguồn; C2/DU01 thiếu evidence và abstain; C1/D03 lỗi citation. [Hướng dẫn](../../docs/DEMO.md).

Giới hạn: corpus Python tiếng Anh và trích HTML chưa bao phủ hết bảng/hình; dev/test cùng lĩnh vực; mẫu nhỏ; một lượt mỗi cấu hình; nhãn trên bản hỗ trợ có nguy cơ thiên lệch; model/usage qua proxy chỉ là provider claim; chưa làm bonus >=100 trang. Tôi không coi test code xanh là bằng chứng mọi câu trả lời đều đúng.

## 7. Kết luận

Tôi chọn **C2 Hybrid RRF, top-k 3, context 4.000 ký tự, một lượt search** cho thí nghiệm cơ bản này bằng kết quả dev. Retrieval, context, câu trả lời và citation phải đọc tách biệt. Tôi giữ cả lỗi, run không cải thiện và phần chi phí chưa biết để người chấm có thể đối chiếu. Kết quả test đánh giá lựa chọn đã cố định, không dùng để chọn lại. Bonus chưa thực hiện; link repo do tôi nộp LMS.
