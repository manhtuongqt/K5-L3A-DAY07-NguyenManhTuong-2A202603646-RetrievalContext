# Nguồn và giấy phép

## Tài liệu Python

Corpus gồm nội dung từ `https://docs.python.org/3.13/`, do Python Software Foundation và các tác giả Python cung cấp. Tiêu đề snapshot là Python 3.13.18; thời điểm tải, URL và SHA-256 của từng tài liệu ở [manifest](data/manifest.json).

Tài liệu được cấp phép PSF License Version 2. Mã ví dụ còn được cấp phép Zero-Clause BSD theo trang giấy phép. Giữ nguyên thông báo bản quyền/điều khoản đầy đủ trong [snapshot giấy phép chính thức](data/raw/python_license.html). Nguồn chính thức: <https://docs.python.org/3.13/license.html>.

Các thay đổi trong bài: bỏ giao diện điều hướng của HTML, trích xuất một số loại khối nội dung, chuẩn hóa Unicode/whitespace, chuyển sang text, chia đơn vị nguồn rồi chia chunk. Không sửa ý nghĩa nội dung nguồn có chủ đích. Đây là bản trích xuất dùng cho thí nghiệm, không thay thế toàn bộ tài liệu gốc. Bộ trích xuất chưa giữ các bảng HTML dạng ô thuần hoặc hình ảnh không có text; hạn chế này được nêu trong báo cáo.

## Embedding

- Model gốc: [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5), giấy phép MIT theo model card.
- Bản ONNX quantized: [qdrant/bge-small-en-v1.5-onnx-q](https://huggingface.co/qdrant/bge-small-en-v1.5-onnx-q).
- Model không được đưa vào Git; revision và checksum từng tệp ở [benchmark/model.json](benchmark/model.json). Tải theo revision đó khi tái lập.

## Phần mềm và đề bài

- [FastEmbed](https://github.com/qdrant/fastembed), Apache-2.0.
- [Qdrant Python client](https://github.com/qdrant/qdrant-client), Apache-2.0. Dùng local mode chính thức có lưu trên đĩa; không tự tạo database tương tự.
- Đề và tài liệu quy định từ [VinUni-AI20k/K5-L3-Day06-DataIngestionEngineering](https://github.com/VinUni-AI20k/K5-L3-Day06-DataIngestionEngineering), commit gốc `42f64eb230289ff5042abc03683252649dfbef79`. Giữ nguyên các file quy định và khung starter tùy chọn.

Dependencies được cài riêng trong `.venv`; phiên bản ghi ở `requirements-lock.txt`. Thư viện/model không được chép vào mã nguồn bài nộp.
