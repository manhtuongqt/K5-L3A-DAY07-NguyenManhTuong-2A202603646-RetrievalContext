# Rà soát cuối phần cơ bản Day07

Ngày: 14/11/2026, Asia/Saigon. Phạm vi: 85 điểm cơ bản; bonus chưa triển khai.

Phần việc còn lại nêu trong snapshot rà soát bên dưới đã được kiểm tra tiếp tại [GATE_CHECKLIST.md](GATE_CHECKLIST.md) và [submission_check.json](../results/submission_check.json). Dùng hai artifact này để xem trạng thái chốt hiện tại.

Đây là rà soát kỹ thuật độc lập sau dev/test, không phải một lời xác nhận audit
thay cho người học. Không sửa source/config đã freeze, không mở store, không gọi
API và không chỉnh cấu hình theo kết quả test.

## 1. Kết quả kiểm tra trực tiếp

Đã thực hiện **496/496 kiểm tra nhất quán** bằng cách đọc các tệp hiện hành,
không chỉ dựa vào cờ `passed` có sẵn:

- 11 hash implementation trong selection, ba hash dữ liệu/model, bốn config,
  bốn trace dev, bốn tệp nhãn dev và sáu tệp benchmark đã khóa đều khớp.
- Đủ **82 trace thật**: 68 dev C0–C3 và 14 test C0/C2; tổng 173 model call,
  280 chunk được trả về. Thứ tự/ID case đúng benchmark từng split.
- Nội dung, nguồn, page, metadata và cả bốn offset của từng chunk được đối chiếu
  với `data/chunks.jsonl`; không thay text để hợp thức hóa citation.
- Context được render từ chunk nguyên văn, số ký tự đúng budget và bằng context
  trong request model cuối, kể cả case cuối cùng báo lỗi.
- Selection chọn C2 lúc **09:09:02 UTC**, trước thời điểm bắt đầu của toàn bộ
  14 trace test. Các hash implementation/config/data vẫn bằng selection hiện hành.

Canonical chunk SHA256 vẫn là
`d29a0d3c7c2efaf0a6ab6bddc3dda3aad4a92255f4a70ef4b7455eb39f2e0a31`.
Manifest và báo cáo tái tạo độc lập dùng đúng hash này. Vector B vẫn có SHA256
`266db21df0190f393a3c8b2927ef49c1a96b70c42801b628d095bf7157278fc9`.

## 2. Đối chiếu BENCHMARK và RUBRIC

| Yêu cầu cơ bản | Bằng chứng đã kiểm tra | Đánh giá |
|---|---|---|
| Dùng lại Day06 và embedding/store thật | 312 chunk B/69 đơn vị HTML, nguồn/offset giữ nguyên; pinned BGE 384 chiều và Qdrant persistent | Có bằng chứng trực tiếp và tái tạo retrieval độc lập |
| Ít nhất ba retrieval | Dense/BM25/Hybrid; cùng corpus, câu hỏi/filter; query gốc top-3 và query agent tách riêng | Đúng thiết kế, có trace riêng |
| Benchmark tối thiểu | 15+2 dev, 5+2 test; gold/absence checks khóa trước retrieval | Đủ 24 câu; không tính câu thiếu evidence vào mẫu số retrieval |
| Agent model thật | Raw native function calls, request ID, messages, tool schema, usage và context thật trong 82 trace | Không lấy mock làm điểm benchmark |
| Hai cấu hình cải thiện | C2 rank fusion; C3 gói top-k/context lớn hơn; có cả kết quả không cải thiện | Hợp lệ; không tách được nhân quả riêng của top-k và budget trong C3 |
| Chọn dev trước test | Selection C2, dev strict 17/17; test timestamps sau selection, hash vẫn đúng | Không chọn lại theo test |
| Context/answer/citation/abstention | Nhãn và lý do cho từng ca thành công, lý do cho từng citation ID; case lỗi giữ nguyên | Đủ dữ liệu đánh giá, không suy semantic support từ ID hợp lệ |
| Lỗi và mẫu số | C1/D03 vẫn là error; strict giữ 17 case, context có evidence vẫn được đo riêng | Không chuyển error thành abstention đúng |
| Tài nguyên | Usage, native cost, latency, tool calls và retries trong trace; USD chưa biết được giữ N/A | Có báo chi phí và phần chưa biết; không gọi agent là miễn phí |

Không có ngưỡng accuracy tuyệt đối cho phần cơ bản trong RUBRIC. Kết quả tốt
không thay các điều kiện về protocol, nguồn, nhãn và giải thích sai sót.

## 3. Kiểm tra lại kết quả test

Đã tính lại metrics từ raw trace + nhãn, rồi đối chiếu với `results/metrics_test.json`.
Sau chuẩn hóa JSON keys, **toàn bộ trường aggregate của C0 và C2 khớp**.

| Chỉ số test | C0 baseline | C2 đã chọn |
|---|---:|---:|
| Case hoàn tất | 7/7 | 7/7 |
| Strict end-to-end | 6/7 | 7/7 |
| CER exact | 5/5 | 5/5 |
| Context 0/1/2 | 0/0/5 | 0/0/5 |
| Answer 0/1/2 | 0/0/5 | 0/0/5 |
| Grounded answer mean | 2,00/2 | 2,00/2 |
| Citation hỗ trợ | 5/6 | 6/6 |
| Từ chối đúng | 2/2 | 2/2 |
| Từ chối nhầm | 0/5 | 0/5 |
| Tool use | 7/7 | 7/7 |

Đã đọc độc lập 10 câu trả lời có đáp án, nguồn được cite và bốn lời từ chối:

- T01 giữ đủ ba nhóm ký tự JSON vẫn phải escape.
- T02 giữ string đầu vào của `parse_float` và mặc định `float(num_str)`.
- T03 giữ overflow/underflow, list/restkey/restval, mặc định None và điều kiện non-blank.
- T04 C0 thêm ví dụ quoted field có line break nhưng chỉ cite đoạn `line_num`;
  ví dụ được hỗ trợ ở chunk khác trong context, không nằm trong sole citation.
  Do đó answer/context=2 nhưng citation=false là cách chấm có căn cứ. C2 không
  thêm điều kiện ngoài citation nên đạt.
- T05 giữ cả strict/non-strict, OSError và thay đổi symlink loop Python 3.13;
  hai citation cùng hỗ trợ các điều kiện.
- TU01/TU02 từ chối cung cấp p95 deployment hoặc backup configuration không có
  trong nguồn, không bịa con số/tên bucket/retention.

Đây là đối chiếu hỗ trợ, không phải hai người chấm độc lập hoặc chấm mù.

## 4. Audit người học và lịch sử sửa evaluator

Hồ sơ hiện hành có xác nhận benchmark, dev và test của người học. Xác nhận test
được ghi lúc **09:16:58 UTC** từ lời xác nhận cụ thể trong hội thoại. Đã kiểm tra
`confirmed_reviews()` trên mọi cấu hình: **81 hàng output** gắn đúng hash và trace,
gồm 67 dev và 14 test. Case dev lỗi không bị dựng thành output để tăng số hàng.
Các packet draft cũ giữ nguyên pending như lịch sử; trạng thái hiện hành nằm trong
`results/audit/status.json` và bản confirmed view. Không sửa nhãn cũ để nhận xác nhận.

Lỗi CER được sửa **trước selection và test**: evaluator cũ bỏ qua context nếu
final action lỗi. C1/D03 có evidence trong request thực gửi nên CER phải tính;
C1 từ 13/15 thành 14/15, strict vẫn 14/17. Đã kiểm tra hash code cũ tại
`results/history/evaluation_before_cer_fix.py` bằng giá trị trong
`results/history/metric_correction.json`; code hiện tại cũng khớp hash corrected
và selection. Không đổi query/model/raw trace/gold/nhãn để thực hiện sửa này.

## 5. Phần chốt submission cần theo dõi

Tại snapshot rà soát này, báo cáo cá nhân và `metrics_test.json` đã được sinh sau
xác nhận test. Nội dung có các hạng mục tương ứng mẫu: dữ liệu/benchmark,
retrieval/thử nghiệm, context/agent, nhãn test, lỗi dev, lựa chọn, chi phí và giới hạn.
README có cài đặt, prepare pinned sources/model/store, dev/freeze/test và lưu ý API.
Remote origin đúng mẫu `K5-L3A-DAY07-NguyenManhTuong-2A202603646-RetrievalContext`.

Các bước root đang chốt, cần kiểm tra artifact thực tế trước khi tuyên bố đã nộp:

1. `docs/DEMO.md` và ba ca answered/abstain/error có đường dẫn dùng được.
2. `docs/GATE_CHECKLIST.md`, checker submission, link nội bộ không gãy.
3. Kiểm tra secret/quyền chia sẻ, commit/push đúng origin và quyền người chấm đọc repo.
4. Nộp link LMS do người học thực hiện; commit/push không đồng nghĩa đã nộp LMS.

Bản này không tự khẳng định các bước vừa liệt kê đã xong nếu chưa có bằng chứng.
Nếu artifact được tạo sau snapshot, dùng checker cuối và trạng thái Git để chốt.
Không cần Docker/UI/bonus để chứng minh phần cơ bản hiện tại; các mục đó không
được dùng làm lý do trì hoãn hoặc tự cộng điểm ngoài phạm vi đã thực hiện.

## 6. Giới hạn còn giữ nguyên

Một run mỗi cấu hình, test nhỏ (5 có đáp án + 2 thiếu evidence), corpus Python tiếng
Anh, HTML extraction chưa đủ mọi bảng/hình, audit trên nháp hỗ trợ có nguy cơ
thiên lệch. Gateway model alias/token/cost là provider claim; chưa xác minh upstream
hay đơn vị tiền. Tái tạo retrieval đã chạy thật độc lập trên cùng môi trường Windows,
không chứng minh đầu ra model API hoặc mọi số thực byte-identical xuyên nền tảng.
Giữ các giới hạn này trong báo cáo thay vì diễn giải 7/7 như độ chính xác tổng quát.
