# Rà soát kỹ thuật độc lập: phần cơ bản Day07

Ngày rà soát: 14/11/2026, múi giờ Asia/Saigon. Phạm vi: nguồn, adapter Day06,
retrieval, context, trace và thiết kế đánh giá. Đây là kiểm tra kỹ thuật hỗ trợ;
không thay cho việc người học đọc và xác nhận nhãn ngữ nghĩa của câu trả lời.
Không đánh giá bonus trong lần rà soát này.

Tại thời điểm rà soát, các lượt chạy dev đang tiếp tục. Không mở Qdrant chính,
không gọi model và không sửa mã nguồn/cấu hình đã khóa. Những số đếm trace dưới
đây là một snapshot đang chạy, không phải kết quả tổng kết toàn bộ bài lab.

## 1. Bằng chứng đã kiểm tra

| Nội dung | Bằng chứng trực tiếp | Kết luận |
|---|---|---|
| Nguồn Day06 | `src/retrieval.py` pin repo/commit `64c4ab778f81ba5608d4b2b57315f6369aedd0fd`; kiểm tra SHA256 trước import | Không dùng snapshot mới không rõ phiên bản |
| Chunk/source ID | 312 bản ghi trong `data/chunks.jsonl`; `id=chunk_id`, `source_id=document_id` | Không tạo lại ID hoặc chia lại chunk |
| Nội dung và offsets | 6 test retrieval đã qua, có kiểm tra toàn bộ 312 chunk với `data/pages.jsonl` | `text == page.text[start:end]`; source offsets giữ đúng vị trí trong văn bản chuẩn hóa |
| Model document/query | `configs/embedding_model.json`: pinned ONNX BGE, 384 chiều, CLS+L2, query prefix một lần | Query/index tương thích; không thay embedding bằng vector giả |
| Vector thật | `.local/vectors_B.npy` SHA256 `266db21df0190f393a3c8b2927ef49c1a96b70c42801b628d095bf7157278fc9` | Byte-identical vector B Day06 trên máy này |
| Vector store | `data/day6_manifest.json`: Qdrant local persistent, collection `day07_B`, 312 điểm, cosine/exact | Dùng Qdrant thật riêng, không mở/sửa store Day06 |
| Tái tạo độc lập | `results/retrieval_reproduction.json`: 14/14 kiểm tra, download GitHub/HuggingFace đã pin và tạo lại vector thật, 84,5 giây | Không cần checkout Day06 trên máy khác; còn giới hạn môi trường ở mục 4 |
| Ba phương pháp | Dense, BM25 và Hybrid RRF được triển khai khác nhau trong `src/retrieval.py` | Đáp ứng yêu cầu ba phương pháp, không tính đổi top-k là phương pháp mới |
| Benchmark | `benchmark/lock.json`, `protocol.json`, 17 dev/7 test, có kiểm tra absence trên 69 đơn vị nguồn | Cấu trúc tối thiểu đúng; độ đầy đủ ngữ nghĩa vẫn cần review |
| Tách gold/runtime | `agent_input` và projection trong `run_experiments.py` chỉ chuyển `id/question/filter`; runtime không import benchmark | Không đưa đáp án chuẩn hoặc `answerable` vào model/retriever |
| Agent thật | D01 có native tool call `search` từ provider rồi `abstain`, 2 model call/1 retrieval call; ID request và usage được lưu | Có evidence model điều phối thật; một trace không chứng minh đủ mọi case |
| Context thực gửi | Đã đối chiếu 21 trace dev hoàn tất, 46 model call và 63 chunk được trả về | 105/105 kiểm tra trực tiếp qua: nội dung/nguồn/offset/metadata không đổi, context render nguyên văn, budget đúng, context cuối khớp request cuối |
| Mã nguồn đã khóa | SHA256 `src/retrieval.py` thực tế khớp `results/agent/dev/C0/run.json` | Bản retrieval đang rà soát đúng bản đã dùng cho dev |

Hash canonical `data/chunks.jsonl` sau adapter:
`d29a0d3c7c2efaf0a6ab6bddc3dda3aad4a92255f4a70ef4b7455eb39f2e0a31`.
Hash này khớp cả manifest chính và báo cáo tái tạo độc lập. Hash `pages`, model lock
và vectors cũng đã đối chiếu trực tiếp với các tệp hiện hành, không chỉ đọc trạng
thái `passed` trong báo cáo.

Git attribute giữ `data/**` và model lock dạng bytes; adapter ghi JSONL canonical
bằng UTF-8/LF. Riêng `results/index.json` lịch sử Day06 là tệp text có CRLF ở máy
Windows nhưng LF trong Git blob; adapter chỉ thống nhất line ending của metadata
JSON đó để xác minh đúng hash của commit, không thay nội dung nguồn/chunk.

## 2. So sánh retrieval có công bằng không?

Các điều kiện đang được giữ giống nhau:

- Cùng 312 chunk, cùng model/index, cùng dev và nhãn.
- Báo ranking **query gốc, top-3** riêng cho Dense/BM25/Hybrid.
- Filter lấy từ yêu cầu người dùng; cùng `document_type/language/version`, không
  suy ra từ gold/source/page chuẩn. Cả ba nhánh áp dụng filter trước khi trả candidate.
- Dense dùng cosine; BM25 dùng k1=1,5, b=0,75. Hybrid không cộng hai score có đơn
  vị khác nhau: hợp nhất top10 mỗi nhánh theo `1/(60+rank)` và giữ branch ranks.
- BM25 không có từ trùng trả 0 kết quả. Trường hợp này phải giữ `actual_returned=0`,
  không bổ sung kết quả giả để làm đẹp top-3.

Agent có thể viết lại query. Ranking của query viết lại thuộc trace pipeline và
phải báo riêng với ranking query gốc; không gọi chúng là cùng một thí nghiệm.
Hiệu quả Dense/BM25 ở đây là trên corpus/query tiếng Anh, không suy rộng thành
đánh giá tokenizer tiếng Việt.

`candidate_k=10` và `rrf_k=60` trong các cấu hình hiện hành khớp với implementation
cố định. Nếu sau này đổi hai trường cấu hình này, cần thực sự nối chúng vào service
hoặc báo rõ giá trị vẫn cố định; chỉ sửa JSON sẽ không làm thuật toán đổi theo.

## 3. Những điều cần diễn giải đúng khi viết báo cáo

### 3.1. C3 thay hai yếu tố cùng lúc

C3 tăng top-k/context-top-k từ 3 lên 5 và budget từ 4.000 lên 8.000 ký tự. Đây là
một **gói chính sách context** hợp lệ để so sánh với C2. Nếu điểm thay đổi, chỉ được
kết luận tác động của gói đó; chưa tách được đóng góp riêng của top-k và budget.
Thí nghiệm này không đủ để khẳng định riêng tăng budget làm điểm tăng.

### 3.2. Citation đúng ID chưa chứng minh đúng ý

Runtime kiểm tra ID có trong context và xuất hiện trong câu trả lời. Điều này là
kiểm tra cấu trúc. Cần đọc từng claim/điều kiện với nguồn tương ứng để chấm semantic
support và ghi lý do. Một ID lặp nhiều lần trong câu trả lời được runtime dedup
trong `citations`; mẫu số báo cáo cần nói rõ là **ID citation duy nhất mỗi câu**
nếu dùng danh sách này, không gọi là số lần xuất hiện inline.

### 3.3. Thông tin chi phí chưa biết phải giữ chưa biết

`ModelClient` giữ usage gốc, kể cả trường riêng `x_ckey`, nhưng không tự đổi một
giá trị `cost` chưa biết đơn vị thành USD. `configs/model.json` hiện để giá input/
output là `null`; chỉ báo token, giá trị provider gốc và phần chi phí chưa xác minh.
Không ghi chi phí LLM bằng 0 vì retrieval embedding chạy local. Cần áp dụng nguyên
tắc bỏ qua cost tie-break cho cả nhóm hòa điểm nếu cost của một cấu hình chưa biết.

Lỗi retry có thể đã bị tính phí nhưng provider không báo usage. Trace giữ attempts
và đánh dấu usage không biết; tổng token/chi phí đã biết không được diễn giải là
tổng hóa đơn chắc chắn đầy đủ. Model alias `claude-opus-5` do gateway công bố,
không có bằng chứng từ trace để xác nhận backend model của nhà cung cấp gốc.

### 3.4. Lỗi hệ thống và abstention khác nhau

HTTP/store/output lỗi phải giữ `status=error`, không chấm thành từ chối đúng. Các
chỉ số trên output thành công cần kèm completion/error count; chỉ số end-to-end
giữ mọi case đã lên lịch trong mẫu số. Một lần đo/phiên bản chưa chứng minh ổn định
hay ý nghĩa thống kê, đặc biệt test chỉ có 5 câu có đáp án và 2 câu thiếu evidence.

### 3.5. Kết quả context và retrieval có định nghĩa khác nhau

Metric Hit@1/Hit@3 yêu cầu nguyên evidence đúng nguồn/trang trong một chunk.
Context Evidence Rate đo evidence trong context cuối thực gửi model, không đo
toàn bộ candidate đã lấy. Context grade 0/1/2 và grounded answer vẫn cần nhãn ngữ
nghĩa. Trường hợp evidence diễn đạt đúng nhưng không khớp nguyên quote cần phân
tích như giới hạn metric, không sửa gold sau khi nhìn test.

## 4. Giới hạn tái lập đã xác định

- Tái tạo retrieval đã thực chạy trong thư mục độc lập nhưng dùng cùng Windows,
  Python/package environment. Có bằng chứng tải lại nguồn/model và tính lại vector,
  chưa có bằng chứng thực chạy trên Linux hoặc một máy CPU khác.
- Direct dependencies được pin; đầy đủ transitive package versions cần lưu riêng
  nếu muốn tái lập chặt môi trường. Floating point kernels có thể khác giữa nền tảng.
- BM25 dùng tổng số thực trên tập từ query; thứ tự duyệt set giữa process có thể
  khác, dẫn tới khác biệt rất nhỏ ở chữ số cuối của score. Không tuyên bố BM25
  score byte-identical xuyên mọi process/nền tảng khi chưa kiểm tra điều đó.
- Qdrant local chỉ cho một owner mở store. `ConfiguredRetriever` có lock để các
  model request có thể song song nhưng truy cập store/embedding tuần tự. Không mở
  thêm CLI hoặc test integration trong lúc run thật đang giữ store.
- Quy trình prepare acquire owner trước khi ghi tệp, nhưng nạp snapshot không phải
  giao dịch atomic của toàn bộ bộ dữ liệu/store. Nếu bị ngắt giữa prepare cần chạy
  lại và xác minh manifest trước benchmark. Không tiếp tục chấm trên snapshot nửa chừng.
- Không tuyên bố model trả lời tái lập byte-identical. Provider temperature 0 không
  tự đảm bảo deterministic; cần giữ run gốc và thông tin lỗi/thời gian.

## 5. Những gate chưa được chứng minh bởi riêng bản rà soát này

1. Hoàn tất toàn bộ dev của C0–C3, nhãn và lý do cho mọi câu/citation.
2. Phân tích ít nhất hai lỗi dev với trace, giả thuyết và kết quả trước/sau.
3. Selection theo tiêu chí đã công bố; khóa config/code/prompt/model/reviews trước test.
4. Chạy baseline và winner trên cùng test; kiểm tra 5 câu có đáp án và 2 câu thiếu
   evidence của cả hai theo BENCHMARK.md.
5. Nhãn audit Day07 được người học đọc và xác nhận đúng phạm vi đã review.
6. Báo cáo cuối, README chạy lại, demo ba loại case và checklist submission đầy đủ.

Bản rà soát này không đánh dấu hoàn thành các việc đang chạy. Mọi thiếu sót ở phần
đánh giá/báo cáo cần giải quyết bằng artifact và kiểm chứng tiếp, không suy ra gate
đã đạt chỉ vì code test hoặc smoke đã xanh.
