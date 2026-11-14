# Nguồn và quyền sử dụng

## Đề và starter Day07

Đề bài và code starter: VinUni-AI20k, [K5-L3-Day07-Retrieval-Context-Engineering](https://github.com/VinUni-AI20k/K5-L3-Day07-Retrieval-Context-Engineering), commit `c67ec6292cd6d15e6e6cbaa2c7e7260398bb5a19`. Giữ tài liệu gốc và phân biệt với phần triển khai trong `src/`.

## Corpus Python từ Day06

Snapshot tài liệu Python 3.13 được tái sử dụng từ bài Day06 của Nguyễn Mạnh Tường, commit `64c4ab778f81ba5608d4b2b57315f6369aedd0fd`. Nguồn gốc là [Python Documentation](https://docs.python.org/3.13/), không phải nội dung do sinh viên viết.

- Tài liệu dùng PSF License v2; mã ví dụ còn có thể dùng theo 0BSD. Bản giấy phép gốc được giữ tại [data/python_license.html](data/python_license.html).
- Các biến đổi: trích xuất HTML sang text, chuẩn hóa, chia đơn vị nguồn và chunk; giữ ID, offset, nguồn và provenance của Day06.
- Manifest nguồn: [data/source_manifest.json](data/source_manifest.json). Notices Day06 gốc: [data/DAY06_THIRD_PARTY_NOTICES.md](data/DAY06_THIRD_PARTY_NOTICES.md).
- Corpus có 69 đơn vị HTML đã chuẩn hóa, không phải 69 trang PDF. Bộ trích xuất có giới hạn về bảng/hình/list; không tuyên bố bao phủ mọi nội dung hiển thị của Python Docs.

## Embedding

[BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5), giấy phép MIT theo model card; bản ONNX quantized lấy từ [qdrant/bge-small-en-v1.5-onnx-q](https://huggingface.co/qdrant/bge-small-en-v1.5-onnx-q). Revision và SHA256 được giữ trong [configs/embedding_model.json](configs/embedding_model.json).

FastEmbed, Qdrant client, ONNX Runtime và các dependency giữ giấy phép của từng package. Model cache và database local không được commit; script chuẩn bị dữ liệu ghi rõ nguồn và kiểm tra hash khi tái tạo.

## Model trả lời

Model điều phối được gọi qua endpoint cấu hình trong môi trường local. Tên model cấu hình và tên model gateway trả về là thông tin provider báo; không tự xác minh được upstream đằng sau alias. Không đưa API key, token hay `.env` lên GitHub. Usage được lưu nguyên giá trị provider báo; trường chi phí gateway chưa rõ đơn vị không được quy đổi thành USD hoặc gọi là miễn phí.
