# Kế hoạch hoàn thành Lab Day07 — Agentic RAG

Người làm: Nguyễn Mạnh Tường · MSSV 2A202603646 · Lớp L3A.

Ngày lập: 14/11/2026, múi giờ Asia/Saigon.

**Cập nhật phạm vi triển khai:** theo yêu cầu tiếp theo của người học, hiện chỉ hoàn thành phần cơ bản G0–G7. Bonus G8–G9 trong bản kế hoạch ban đầu được để sau, không tính là gate còn thiếu của bài cơ bản.

**Trạng thái sau triển khai:** xem [đối chiếu gate và bằng chứng hiện tại](GATE_CHECKLIST.md). Các dòng hiện trạng/chưa thực hiện phía dưới ghi thời điểm lập kế hoạch ban đầu, không thay thế kết quả kiểm tra cuối.

## 1. Mục tiêu và căn cứ

Hoàn thành toàn bộ yêu cầu cơ bản, sau đó thực hiện thử thách nâng cao. Mỗi bước phải có sản phẩm và bằng chứng kiểm tra; không coi test mock, một trace minh họa hoặc bản kế hoạch là bằng chứng hoàn thành bài lab.

Đã đọc toàn bộ 17 file Markdown, bốn file Python trong `starter`, bốn file test, ba JSON mẫu và hai sơ đồ SVG tại commit đề `c67ec6292cd6d15e6e6cbaa2c7e7260398bb5a19`.

Tài liệu quy định:

- [README](../README.md): mục tiêu, tối thiểu ba phương pháp retrieval và agent thật.
- [GUIDE](../GUIDE.md): quy trình triển khai, thử nghiệm và trình bày.
- [BENCHMARK](../BENCHMARK.md): split, metrics, nhãn và cách đánh giá.
- [RUBRIC](../RUBRIC.md): 85 điểm cơ bản và 15 điểm nâng cao.
- [RULES](../RULES.md): nguồn, bảo mật, không đưa gold vào agent, chỉ chọn bằng dev.
- [CHECKPOINTS](../CHECKPOINTS.md): bốn mốc thời gian tham khảo, không có CP1–CP7 chính thức.
- [SUBMISSION](../SUBMISSION.md): cấu trúc repo và danh sách bài nộp.
- [ADVANCED](../ADVANCED.md): điều kiện đầy đủ của bonus.
- [Starter](../starter/README.md), [schema](../data/README.md), [pseudocode](../PSEUDOCODE.md), [mẫu báo cáo](../report/individual/MSSV_HoTen.md).
- [AGENT_SETUP](../AGENT_SETUP.md): AI hỗ trợ lập trình là tùy chọn, không phải hạng mục tính điểm.

Các mã G0–G9 bên dưới là cách chia việc của kế hoạch này, không phải số checkpoint do đề đặt.

## 2. Hiện trạng đã kiểm tra

| Thành phần | Bằng chứng hiện tại | Kết luận |
|---|---|---|
| Repo cá nhân | `manhtuongqt/K5-L3A-DAY07-2A202603646-NguyenManhTuong-RetrievalContext`; origin cá nhân, upstream đề | Sẵn sàng |
| Starter | `python -X utf8 -m unittest discover -s tests -v`: 15/15 qua lúc kiểm tra | Chỉ xác nhận hành vi code mẫu |
| Corpus Day06 | Snapshot Python, 69 đơn vị nội dung; manifest và `data/pages.jsonl` hiện hữu | Có thể tái sử dụng |
| Chunk đã chọn Day06 | B, 312 chunk; `results/chunks_B.jsonl` và vector `(312,384)` hiện hữu | Dùng làm index cơ bản |
| Embedding | BAAI/bge-small-en-v1.5, ONNX quantized; revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55` | Khóa tương thích document/query |
| Query prefix | `Represent this sentence for searching relevant passages: ` | Chỉ thêm một lần đúng cách Day06 |
| Vector store | Qdrant local persistent; đường dẫn Day06 `.local/qdrant`, collection B là `day06_B` | Có adapter mẫu Day06; chưa kiểm tra kết nối Day07 |
| Môi trường | Python 3.11; venv Day06 có FastEmbed 0.7.3, Qdrant client 1.16.0 | Tạo môi trường Day07 và khóa dependencies riêng |
| Model điều phối | `Controller` trong starter chỉ là interface | Chưa nối model thật; chưa xác nhận key/quota/tool calling cho Day07 |
| Benchmark và audit Day07 | Hiện chỉ có fixture | Chưa thực hiện |
| Tài liệu bonus | Chưa chọn | Chưa thực hiện; không suy từ corpus HTML Day06 rằng đã đủ bonus |

Code và kết quả Day06 giữ nguyên. Ghi commit nguồn Day06 `64c4ab778f81ba5608d4b2b57315f6369aedd0fd` và SHA256 khi import. Không dùng các score Day06 làm score trả lời của agent Day07.

## 3. Kiến trúc triển khai

```text
question + scope được cung cấp trước
    → model thật chọn search / trả lời / từ chối
    → retrieval tool được cấu hình: dense / BM25 / hybrid RRF
    → kết quả có chunk ID, text, score/rank, source, page, metadata
    → gộp trùng, xếp lại candidate, chọn context có nguồn trong budget
    → model đọc context, trả lời kèm citation hoặc không đủ bằng chứng
    → lưu trace đầy đủ

Evaluator riêng đọc gold + trace + nhãn để tính metrics.
Agent và retriever không đọc gold, expected_answer hay nhãn audit.
```

- Dùng Qdrant thật cho dense; lexical không thay cho dense. Với local storage, tránh hai tiến trình cùng mở một path; dùng một owner và đóng client đúng cách. Snapshot độc lập ở Day07 được phép nếu giữ nguyên ID/vector/payload và kiểm chứng tương đương; ghi đây là bản tái tạo index Day06.
- Giữ ID gốc, nguồn, page, metadata và quan hệ text/offset. Không chỉ chuyển text rồi bỏ provenance.
- Model tạo query và quyết định có tìm tiếp; runner kiểm tra schema, giới hạn, lỗi và log. Không thay model bằng danh sách action lập sẵn khi benchmark.
- Giữ question gốc riêng với query viết lại. Retrieval benchmark query gốc và pipeline agent có bảng riêng.
- Document/tool output được đưa vào vùng dữ liệu, không được phép thay instruction của agent.
- Model ID cấu hình và ID provider trả về đều được ghi lại. Alias qua proxy không được dùng để khẳng định danh tính model upstream chưa được xác minh.

## 4. Thứ tự thực hiện và điều kiện qua từng gate

### G0 — Môi trường và một lời gọi model thật

**Việc làm:** tạo `.venv`, requirements khóa phiên bản, `.env.example` chỉ có placeholder; model/base URL/key nạp từ `.env` được Git bỏ qua hoặc biến môi trường. Kiểm tra model trả lời và hỗ trợ tool calling/structured action bằng một câu smoke ngoài benchmark. Chọn cùng một model và tham số decoding cho các cấu hình so sánh.

**Sản phẩm dự kiến:** `requirements.txt`, `.env.example`, `configs/model.json`, `scripts/check_environment.py`, log smoke đã lọc secret.

**Qua khi:** model thật gọi tool được, kết quả trả về đúng schema; lỗi key/quota/timeout được ghi rõ. Không có mock fallback. Nếu API không dùng được, tiếp tục corpus/retrieval/test offline, nhưng gate model và benchmark agent vẫn chưa đạt. Model local thật có thể thay API nếu đủ tài nguyên và được benchmark lại nhất quán.

### G1 — Adapter Day06 và index tương thích

**Việc làm:** import B=312 chunk cùng provenance; giữ hash, model revision, 384 chiều, cosine, exact search. Tái sử dụng vector đã lưu hợp lệ hoặc tạo lại bằng đúng model, ghi thời gian. Adapter nhận đường dẫn cấu hình thay vì hardcode tài khoản máy.

**Sản phẩm dự kiến:** `src/day6_adapter.py`, `src/embedding.py`, `src/store.py`, `data/day6_manifest.json`, `data/chunks.jsonl`, `results/index_checks.json`.

**Qua khi:** đủ 312 ID duy nhất; mọi text/offset đúng nguồn; vector hợp lệ và khớp index; mở lại store còn dữ liệu; query smoke trả ID/page thật. Hash và ranking tương đương được kiểm tra nếu tạo bản index riêng. Có lệnh tái tạo trên máy khác mà không cần `.local` của máy hiện tại.

### G2 — Benchmark riêng, khóa trước thử nghiệm

| Loại | Dev | Test | Tổng |
|---|---:|---:|---:|
| Có evidence | 15 | 5 | 20 |
| Thiếu evidence | 2 | 2 | 4 |
| Tổng tối thiểu | 17 | 7 | 24 |

**Việc làm:** có thể dùng 15 câu dev Day06 sau khi kiểm tra schema; tạo năm câu test mới về những điều kiện/API khác với các ca test đã thảo luận Day06. Đây là lựa chọn bảo toàn holdout cho Day07, không phải khẳng định test Day06 đã bị dùng để chỉnh. Thêm bốn câu thiếu bằng chứng gần chủ đề. Kiểm tra sự vắng mặt trên corpus đã index, không chỉ vì top-k không có kết quả.

Mỗi câu có đáp án có ID/split/question/expected answer/source/page/evidence thay thế hợp lệ. Câu thiếu evidence có `answerable:false`, hành vi mong đợi và cách kiểm tra thiếu thông tin. Nếu cần nhiều đoạn, dùng schema nhóm evidence bắt buộc; không gộp AND thành danh sách OR.

**Sản phẩm dự kiến:** `benchmark/dev.json`, `benchmark/test.json`, `benchmark/protocol.json`, `benchmark/lock.json`, `benchmark/absence_checks.json`, `results/audit/benchmark_review.csv`.

**Qua khi:** đủ 17/7, ID và ý hỏi không trùng; evidence đúng nguồn; có review ngữ nghĩa. Khóa corpus, index, câu hỏi, gold và tiêu chí chọn trước khi chạy retrieval/model trên dev. Runtime nhận projection chỉ gồm ID, question và scope hợp lệ; evaluator mới nhận đáp án/gold. Test không tham gia tuning, selection hoặc prompt examples.

### G3 — Ba phương pháp retrieval và benchmark query gốc

| Phương pháp | Triển khai | Điều kiện kiểm tra |
|---|---|---|
| Dense | Query embedding → Qdrant cosine exact | Cùng model/index Day06, không vector giả |
| BM25 | Tokenize phù hợp tên API, giữ dấu vết token; BM25 trên cùng 312 chunk | Giải thích xử lý `list.remove`, underscore và từ thường |
| Hybrid RRF | Hợp nhất rank dense + BM25; mặc định thử candidate 10 mỗi nhánh, hằng RRF 60 | Lưu rank từng nhánh; không cộng trực tiếp cosine với BM25 |

**Việc làm:** dùng cùng corpus/questions/filter policy; filter chỉ lấy từ scope/query theo quy tắc công bố. Mỗi query lưu số candidate, số kết quả thực trả về, text/ID/source/page/score/rank, query/filter, thời gian và lỗi. Luôn xuất ranking top-3 để so sánh dù pipeline lấy nhiều hơn.

**Sản phẩm dự kiến:** `src/retrievers/{dense,bm25,hybrid}.py`, `scripts/eval_retrieval.py`, `results/retrieval/dev/{config}/`.

**Qua khi:** cả ba phương pháp chạy thật trên cùng 15 câu dev có đáp án; Hit@1 và Evidence Hit@3 có tử/mẫu, định nghĩa thống nhất. Bốn câu thiếu evidence không vào mẫu số retrieval. Bộ dữ liệu trả dưới ba kết quả phải báo đúng số thực trả về; không thêm bản ghi giả.

### G4 — Agent thật và context có thể kiểm tra

**Việc làm:** triển khai search tool với schema, filter whitelist, giới hạn top-k; model đọc kết quả, tìm tiếp khi cần và chốt answer/abstain. Context loại trùng theo ID và chọn theo rank liên quan hiện tại, có thể thay evidence cũ bằng evidence tốt hơn. Giữ citation, điều kiện và nguồn.

Budget ban đầu đo bằng **ký tự**, gồm cả header nguồn và dấu phân cách; token input/output và phí lấy từ usage provider khi có. Không gọi số token của tokenizer BGE là số token chính xác của model trả lời. Theo dõi cả tổng input thực gửi, không chỉ context tài liệu. Không cắt âm thầm chunk để vừa budget; nếu trích đoạn, ghi ID và offsets gốc.

**Sản phẩm dự kiến:** `src/agent.py`, `src/model_client.py`, `src/context.py`, `src/trace.py`, `scripts/run_agent.py`, `results/smoke/`.

**Qua khi:** có trace thật cho một câu trả lời có citation và một câu thiếu evidence; trace chứng minh tool đã được gọi. Thử lỗi timeout, output sai schema, tool lỗi, query lặp, citation lạ, prompt injection từ tài liệu, context overflow và stop condition. Lỗi kết nối tách khỏi abstention vì thiếu evidence; citation đúng ID chưa được tự coi là hỗ trợ ngữ nghĩa.

### G5 — Thử cấu hình, đọc lỗi và chọn bằng dev

Thông số dưới đây là cấu hình thử ban đầu của kế hoạch, không phải giới hạn bắt buộc của đề hoặc kết quả đã đo.

| ID | Retrieval | Top-k đưa vào context | Budget ký tự | Search tối đa | Vai trò |
|---|---|---:|---:|---:|---|
| C0 | Dense | 3 | 4.000 | 1 | Baseline thật |
| C1 | BM25 | 3 | 4.000 | 1 | Phương pháp thứ hai |
| C2 | Hybrid RRF | 3 | 4.000 | 1 | Phương pháp thứ ba; cải thiện 1 |
| C3 | Hybrid RRF | 5 | 8.000 | 1 | Cải thiện 2: chính sách context lớn hơn |
| C4 | Như C3 | 5 | 8.000 | 3 | Thử thêm tìm nhiều lượt nếu lỗi dev cho thấy cần |

Giả thuyết C2: tín hiệu từ khóa API bù lỗi của dense. Giả thuyết C3: context rộng hơn giữ đủ điều kiện; đo cả nhiễu tăng thêm. C3 thay cả số đoạn lẫn budget, vì vậy chỉ kết luận về **chính sách context kết hợp**; nếu muốn tách nguyên nhân, thêm ablation chỉ đổi budget. C4 cô lập tác động nhiều lượt khi các tham số còn lại giữ nguyên. Context selection phải nhất quán; nếu thay thì đăng ký thành cấu hình mới.

**Việc làm:** chạy retrieval và agent thật trên dev cho các cấu hình cần so sánh. Đọc ít nhất hai lỗi dev, ghi query/trace, expected evidence, nguyên nhân, giả thuyết và trước/sau. Nếu dev hiện tại chưa bộc lộ đủ lỗi để phân tích, bổ sung ca dev khó có nguồn thật trước khi chốt; không bịa lỗi hoặc mở test để lấy lỗi tuning. Mọi cấu hình đều lưu lại, kể cả kém hơn baseline.

**Tiêu chí chọn cần ghi trong protocol trước chạy:**

1. Tối đa tỷ lệ câu dev đạt đầy đủ: câu có đáp án phải đúng/đủ và citation hỗ trợ; câu thiếu evidence phải từ chối đúng. Tính trên toàn bộ dev, lỗi hệ thống tính không đạt trong chỉ số bổ sung này.
2. Nếu hòa, ưu tiên Context Evidence Rate trên câu có đáp án.
3. Nếu hòa, ít từ chối nhầm hơn.
4. Nếu hòa, chi phí trung bình mỗi query gốc thấp hơn, tính cả retry/lời gọi lỗi có usage.
5. Nếu hòa, median thời gian end-to-end thấp hơn; cuối cùng thứ tự config ID.

Tỷ lệ đạt bổ sung không thay các metrics bắt buộc trong BENCHMARK.md. Chấm ngữ nghĩa phải có nhãn và lý do; script hoặc model judge chỉ hỗ trợ. Thiếu nhãn/chi phí thì chưa đủ cơ sở áp dụng tie-break tương ứng, không mặc định bằng 0.

**Sản phẩm dự kiến:** `configs/C0.json` đến `C3.json`, trace/results dev, `results/audit/dev_reviews.csv`, `results/dev_error_analysis.md`, `results/selection.json`.

**Qua khi:** ít nhất ba phương pháp và hai cải thiện có kết quả riêng; >=2 lỗi dev được phân tích; rule đã công bố và selection có timestamp/hash của cấu hình, prompt, model, dữ liệu và nhãn. Cấu hình không cần chắc chắn tăng điểm mới được ghi nhận.

### G6 — Test sau khi chốt và audit

**Việc làm:** chạy C0 và cấu hình chọn trên cùng bảy câu test; xuất ranking top-3 query gốc để đối chiếu và trace pipeline riêng. Chấm đủ năm câu có đáp án và hai câu thiếu evidence của **cả hai** cấu hình. Nếu chọn chính C0, ghi rõ baseline cũng là winner; không giả làm hai mô hình khác nhau.

| Nội dung | Cách báo |
|---|---|
| Hit@1 / Evidence Hit@3 | n/N và %, chỉ câu có đáp án; một chunk phải giữ đủ evidence theo định nghĩa đã khóa |
| Context Evidence Rate | n/N và %, đủ evidence trong context cuối thực gửi model; không suy từ top-3 |
| Nhãn context | 0/1/2 trên 5 câu có đáp án mỗi cấu hình; số từng mức và lý do |
| Grounded answer | 0/1/2, số từng mức và mean /2; từ chối câu có đáp án là 0 |
| Citation hợp lệ | Citation có trong context và hỗ trợ claim / tổng citation; 0/0 ghi N/A |
| Coverage citation | Số câu answered có citation / số câu answered |
| Abstention | Từ chối đúng / câu thiếu evidence; ghi riêng từ chối nhầm / câu có đáp án |
| Tool use | Câu có search / câu chạy thành công; phân bố số lượt; trace từng tool |
| Lỗi và tài nguyên | Tổng case, success, errors, timeout, retry, thời gian, token, chi phí và phần không biết |

Lỗi provider/store được báo riêng đúng cách starter; báo thêm tỷ lệ hoàn thành trên toàn bộ case và chỉ số dev/test cố định mẫu số để không che lỗi bằng cách loại case. Không lấy retrieval miss để tự động chấm grounding=0, không lấy ID citation hợp lệ để tự động chấm citation=true. Câu thiếu evidence phải thực sự từ chối, không vừa từ chối vừa thêm khẳng định chưa có nguồn.

**Sản phẩm dự kiến:** `results/agent/test/{config}/`, `results/audit/test_reviews.csv`, `results/audit/citation_reviews.csv`, `results/audit/REVIEW.md`, `results/metrics_test.json`, `results/test_error_analysis.md`.

**Qua khi:** mọi case có output hoặc lỗi minh bạch; baseline/winner chấm cùng tiêu chí; nhãn/lý do/source đầy đủ; người học đối chiếu và xác nhận đúng phần đã đọc. Xác nhận audit Day06 không tự chuyển sang câu trả lời/citation Day07. Sau test chỉ phân tích; muốn chỉnh để tuyên bố đánh giá độc lập phải lập test mới.

### G7 — Báo cáo, tái lập và demo cơ bản

**Việc làm:** hoàn thành báo cáo đúng mẫu, bảng ba tầng retrieval/context/answer, trước/sau, lựa chọn dev và test tách biệt. README có cài đặt, chuẩn bị data/model/store, chạy dev, freeze, chạy test, audit và tổng hợp. Đính kèm nguồn/giấy phép và cách tải lại model/dữ liệu hợp lệ.

Demo tối thiểu ba ca thật: trả lời có nguồn; thiếu evidence và từ chối; một lỗi đã phân tích. CLI và trace đủ yêu cầu đề; UI HTML chỉ là phần hỗ trợ nếu làm thêm.

**Sản phẩm dự kiến:** `report/individual/2A202603646_NguyenManhTuong.md`, README cập nhật, `requirements*.txt`, `results/reproduction.json`, `results/submission_check.json`, `docs/DEMO.md`.

**Qua khi:** test code qua; chạy smoke/tái lập trong môi trường sạch hoặc quy trình tái tạo độc lập được ghi lại; artifacts đủ và link tồn tại; file cấu hình không chứa key; dữ liệu đã chia sẻ có quyền sử dụng. Không khẳng định đầu ra model byte-identical nếu provider không deterministic; lưu run gốc và mô tả sai khác.

### G8 — Bonus: tài liệu >=100 trang và benchmark đa phương thức

**Việc làm:** chọn một báo cáo thực tế có quyền sử dụng rõ, đủ text, bảng, ảnh/sơ đồ và biểu đồ có thông tin. Xác minh file gốc và số trang trước khi chọn. Index toàn bộ nội dung hữu ích, ghi trang/phần không trích được và ảnh hưởng. Text có page/offset, bảng có row/column/unit, hình có page/bounding box/crop và lời giải thích được kiểm tra từ ảnh gốc.

Nếu tiếp tục dùng BGE tiếng Anh, chọn tài liệu tiếng Anh phù hợp; nếu đổi embedding, tạo index và ghi chi phí. Có thể index mô tả/caption để tìm crop, sau đó cho model vision thật đọc vùng truy xuất. Không dùng tên model để giả định có vision; phải smoke-test ảnh. OCR/mô tả model không được mặc định là chính xác.

| Benchmark bonus | Có đáp án | Thiếu evidence | Tổng tối thiểu |
|---|---:|---:|---:|
| Dev | 15 | 3 | 18 |
| Test | 24 | 6 | 30 |

Trong **24 câu test có đáp án**, nhóm chính không trùng lặp: bảng 6, ảnh/sơ đồ 5, biểu đồ 5, multi-hop 4, text 4. Multi-hop phải kết hợp ít nhất hai trang/bảng/hình. Hình trang trí không tính. Dev/test không chỉ đổi cách diễn đạt của cùng câu hỏi. Gold có trang/vùng/ô/đơn vị/điều kiện/phép tính và expected answer; câu thiếu evidence có cách kiểm tra sự vắng mặt.

**Sản phẩm dự kiến:** `advanced/{data,benchmark,configs,results}/`, script ingestion/retrieval đa phương thức, manifest/giấy phép, crops theo vùng, nhãn/gold/trace và báo cáo nhóm.

**Qua khi:** corpus >=100 trang hợp lệ theo đề, đủ các loại nội dung và toàn bộ phần hữu ích được index hoặc khai báo phần chưa xử lý; dev/holdout đã khóa trước tuning; từng bảng/hình/evidence đã đối chiếu bản gốc. Đây mới là gate chuẩn bị bonus, chưa phải gate điểm.

### G9 — Bonus: chạy test và kiểm chứng ngưỡng

**Việc làm:** chọn pipeline bằng dev bonus, freeze rồi chạy toàn bộ test bonus. Nhãn từng câu là đạt/không đạt có lý do và đối chiếu bản gốc. Câu có đáp án chỉ đạt khi đúng/đủ, đúng đơn vị/điều kiện/phép tính và citation xác định đầy đủ trang/vùng hỗ trợ. Câu thiếu evidence chỉ đạt khi từ chối không suy đoán. Timeout/lỗi hệ thống tính không đạt, không loại mẫu số.

**Qua khi:** tỷ lệ >=90% trên toàn bộ test đã công bố, không làm tròn; nếu 30 câu thì >=27/30. Có n/N toàn bộ và từng nhóm, trace, nhãn, chi phí/thời gian/lỗi và lệnh tái lập. Đủ ngưỡng nhưng thiếu yêu cầu tài liệu/benchmark/audit vẫn chưa được coi đạt bonus.

Nếu test dưới ngưỡng: báo đúng kết quả và bonus chưa đạt. Muốn cải tiến, chuyển test đã xem thành development và tạo holdout mới đáp ứng đủ phân bố; không thử liên tục trên cùng test rồi gọi là độc lập. Không cam kết trước 15 điểm khi chưa đo.

## 5. Ma trận đối chiếu rubric và submission

| Yêu cầu | Gate và bằng chứng dự kiến |
|---|---|
| Dữ liệu/benchmark — 13 điểm | G1–G2: provenance Day06, model/index, split, evidence, absence checks, khóa |
| Retrieval — 17 điểm | G3/G5: dense/BM25/RRF, config, rank/score/source/filter và errors |
| Agent/context — 17 điểm | G0/G4: model thật, tool trace, stop condition, context selection, citation/abstention |
| Đánh giá — 17 điểm | G3/G6: metrics riêng retrieval/context/answer, labels/reasons, citation và false abstention |
| Thử nghiệm/cải thiện — 13 điểm | G5/G6: >=2 cải thiện, >=2 lỗi dev, selection trước test, thời gian/chi phí |
| Tái lập/báo cáo — 8 điểm | G7: hướng dẫn, source/model/config, report, smoke/reproduction và giới hạn |
| Bonus — 15 điểm | G8–G9: >=100 trang, nội dung trực quan, benchmark riêng đủ nhóm, >=90% test và đủ bằng chứng |
| Quyền truy cập/secret | G0/G7: repo cá nhân người chấm xem được; không `.env`, key/token hay dữ liệu không được phép |
| Trình bày | G7: ca answered có evidence, ca thiếu evidence, ca lỗi và kết luận |

Phần cơ bản không có ngưỡng accuracy bắt buộc. Qua gate nghĩa là thực hiện đúng và có bằng chứng, không phải mọi câu đều trả lời đúng. Điểm chính thức do giảng viên chấm.

## 6. Cấu trúc đầu ra dự kiến

```text
configs/                       model, C0–C4, context/filter policy
benchmark/                     dev, test, protocol, lock, absence checks
data/                          chunks, source manifest, cách tái tạo
src/                           adapters, embedding/store, retrievers, agent, context, trace, evaluation
scripts/                       check_environment, prepare_data, eval_retrieval, run_agent,
                               freeze_selection, aggregate, check_submission
tests/                         test schema, query/index compatibility, ranking/fusion,
                               context budget/dedup, loop/stop/errors, citations, leakage, metrics
results/retrieval/dev/          top-3 query gốc của từng phương pháp
results/agent/dev/              trace agent từng cấu hình
results/agent/test/             baseline và winner sau freeze
results/audit/                  mẫu đối chiếu, nhãn, lý do, citation support, xác nhận
results/                       selection, metrics_dev/test, reproduction, submission_check
advanced/                      corpus, benchmark và kết quả bonus riêng
report/individual/              2A202603646_NguyenManhTuong.md
docs/                          kế hoạch, cách demo
.local/                        model cache, Qdrant, crops lớn; có cách tái tạo
.env                           chỉ local, không commit
```

Từng lệnh CLI mới ở trên là sản phẩm **dự kiến**, chưa có sẵn trong starter. Sau triển khai phải thay tên dự kiến bằng đường dẫn/lệnh thực và chạy kiểm chứng. Không dẫn `.local` như artifact đã chia sẻ nếu người chấm không thể tải hoặc tái tạo.

## 7. Vai trò của người làm và AI hỗ trợ

- AI hỗ trợ code, chuyển schema, chạy thí nghiệm, gom trace và soạn nháp phân tích từ dữ liệu thật.
- Người học kiểm tra code và ý nghĩa số liệu, đối chiếu benchmark/evidence/citation, xác nhận nhãn đã review và trình bày quyết định. Ghi ai thực sự làm/chấm; bản nháp AI không được tự ghi là human-reviewed.
- Phần cần phối hợp: provider/key/quota dùng được cho model thật; review gold và câu thiếu evidence; review context/citation/answer sau test; đối chiếu hình/bảng bonus; tự nộp LMS.
- Không cần cài skill/agent orchestration để được điểm. Khi xử lý PDF bonus, dùng skill PDF để đọc/render và kiểm chứng trang/vùng. Nếu làm UI, dùng Sites và kiểm tra browser khi có kết nối. Không dựng nhiều agent nếu không có yêu cầu phân công riêng.

## 8. Thứ tự và trạng thái hiện tại

1. G0–G2: môi trường, adapter, benchmark trước mọi tuning.
2. G3–G4: ba retrieval và agent/context thật.
3. G5: các cải thiện, audit dev, chọn/freeze.
4. G6–G7: test, audit, báo cáo/tái lập; chốt phần cơ bản.
5. G8–G9: hoàn thiện bonus với corpus/holdout riêng; cập nhật báo cáo chung.
6. Đối chiếu lại toàn bộ SUBMISSION/RUBRIC, kiểm tra secret và quyền xem trước commit/push bài làm; người học nộp link LMS.

Lịch bốn giờ trong đề là gợi ý, không phải bằng chứng đủ thời gian cho API, audit và bonus. Thời gian thực phụ thuộc model, quota và tài liệu.

**Trạng thái khi lập kế hoạch:** fork, clone, đọc tài liệu và test starter đã xong. G0–G9 chưa được tuyên bố đạt; cần sản phẩm và bằng chứng thực tế ở từng gate. Bản kế hoạch chưa commit/push và không thay thế báo cáo bài làm.
