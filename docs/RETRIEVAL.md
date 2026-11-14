# Kết nối Day06 và ba phương pháp retrieval

## Dữ liệu và quyền sử dụng

Day07 dùng nguyên 312 chunk B của corpus tài liệu Python 3.13 ở Day06, từ commit
`64c4ab778f81ba5608d4b2b57315f6369aedd0fd`. Mỗi chunk giữ `chunk_id`, `document_id`,
`page`, `start/end` tương đối với đơn vị nguồn và `source_start/source_end` tương đối
với toàn văn bản đã chuẩn hóa. Adapter chỉ thêm `id=chunk_id`, `source_id=document_id`.
Không chia lại chunk, không đọc benchmark gold để tạo index hay filter.

69 đơn vị nguồn là các đoạn HTML liên tục, không phải trang PDF vật lý. Manifest gốc
nằm trong `data/source_manifest.json`, dữ liệu nguồn đã chuẩn hóa theo đơn vị trong
`data/pages.jsonl`. SHA256 các tệp gốc và mô hình được kiểm tra trước khi dùng.

Tài liệu Python được dùng theo PSF License Version 2; mã ví dụ còn có 0BSD.
Giữ bản giấy phép đầy đủ tại [data/python_license.html](../data/python_license.html).
[Thông báo Day06](../data/DAY06_THIRD_PARTY_NOTICES.md) là bản lịch sử nguyên văn;
các đường dẫn trong tệp đó chỉ cấu trúc kho Day06. Thay đổi kế thừa: trích xuất HTML,
chuẩn hóa ký tự và whitespace, chia đơn vị nguồn/chunk. Adapter Day07 chỉ đổi schema.
Bản trích xuất không bao phủ ảnh và mọi loại bảng HTML; không tuyên bố toàn bộ
Python documentation đã được index. Embedding BAAI/bge-small-en-v1.5 theo MIT;
FastEmbed và Qdrant client theo Apache-2.0. Model không được commit.

## Tái tạo trên máy khác

```powershell
python -m pip install -r requirements-retrieval.txt
python scripts/prepare_data.py
```

Lệnh không cần checkout Day06: tải các tệp nhỏ từ GitHub tại commit cố định, tải
ONNX/tokenizer từ revision HuggingFace đã khóa, tạo document embedding thật bằng
CPU và nạp Qdrant local. Cần mạng lần đầu và quyền đọc hai nguồn công khai.

Nếu có Day06 sẵn trên máy:

```powershell
python scripts/prepare_data.py --day6-root ../K5-L3-Day06-DataIngestionEngineering
```

Lệnh kiểm tra SHA256 snapshot trước khi sao chép; dùng lại `.local/vectors_B.npy`
nếu hash đúng với `results/index.json` Day06. Không mở, sửa hoặc khóa vector store
Day06. Model và Qdrant Day07 có thư mục riêng dưới `.local/`. Tham số `--root`
cho phép tái tạo trong một thư mục mới thay vì ghi đè kết quả hiện hành.

Khi tái embedding trên máy khác, kernel số thực có thể tạo khác biệt nhỏ;
manifest ghi rõ cache cũ hay vector mới, hash thực tế, hình dạng và mức tương thích.
Không tự tạo vector ngẫu nhiên, không thay lỗi model bằng kết quả giả. Cả document
và query dùng cùng ONNX quantized BGE 384 chiều, CLS pooling và L2; query thêm
`Represent this sentence for searching relevant passages: ` đúng một lần,
document không thêm prefix. Revision/hash từng file ở `configs/embedding_model.json`.

## Phương pháp cố định

| Phương pháp | Cách thực hiện |
|---|---|
| Dense | Qdrant local persistent, collection `day07_B`, cosine, exact search |
| BM25 | Okapi k1=1.5, b=0.75; IDF dương `log(1+(N-df+0.5)/(df+0.5))` |
| Hybrid | Dense top10 + BM25 top10, RRF `sum(1/(60+rank))`; không cộng score thô |

BM25 tokenize Unicode NFC/casefold và từ `\w+`, giữ underscore, không stemming,
không tách từ tiếng Việt riêng vì corpus/query chính là tiếng Anh. Lặp từ trong query
không cộng thêm trọng số. Thống kê IDF/độ dài tính trên toàn corpus, sau đó lọc
candidate. BM25 không có từ trùng sẽ trả 0 kết quả; không ép đủ top-k.
RRF ghi `branch_ranks` và `branch_scores`, hòa score thì dùng chunk ID tăng dần.
Dense giữ ranking trả từ Qdrant, không giả định tie-break giữa vector score bằng nhau.

Filter chỉ nhận `document_type`, `language`, `version` do người dùng cung cấp hoặc
được hệ thống suy ra rõ từ yêu cầu; không nhận nguồn/trang gold làm filter.
`RetrievalService.search` nhận query gốc, ghi phương pháp/score/rank vào từng kết quả.
Một owner mở client, dùng tuần tự và gọi `close()`; không mở hai service đồng thời
trên một thư mục Qdrant local. Không cần Docker hay API key cho phần retrieval.
Model điều phối thật của agent là thành phần riêng, vẫn có thể cần API.

## Kiểm chứng

```powershell
python -X utf8 -m unittest discover -s tests -p test_retrieval_real.py -v
```

Unit test kiểm tra BM25/filter, fusion rank và xử lý trùng; integration test mở store
thật, tìm một chuỗi lấy từ nguồn (không dùng benchmark), kiểm tra schema/filter,
trường hợp trả rỗng, giữ nguyên toàn bộ offset và mở lại store có cùng top3/score.
Integration test chỉ skip nếu chưa chạy `prepare_data.py`; skip không chứng minh
gate môi trường thực đã đạt. Kết quả benchmark cần chạy và báo riêng sau khi khóa.
