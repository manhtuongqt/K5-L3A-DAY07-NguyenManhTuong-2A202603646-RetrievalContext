# Kiểm tra và tái lập Day07

## 1. Ba mức kiểm chứng khác nhau

| Mức | Có gọi model trả phí? | Chứng minh điều gì? |
|---|---|---|
| Đọc và kiểm tra trace đã lưu | Không | Output, tool call, nguồn và context thực gửi nhất quán với dữ liệu |
| Tái tạo dữ liệu, embedding và vector store | Không gọi embedding API; có tải dữ liệu/model qua mạng | Có thể dựng lại retrieval từ snapshot/model đã khóa, không phụ thuộc checkout Day06 trên máy tác giả |
| Chạy lại agent bằng API thật | Có thể phát sinh phí | Hành vi của model ở lần chạy mới; không bảo đảm giống từng byte lần gốc |

Phần kiểm tra tự động không chứng minh ngữ nghĩa câu trả lời/citation hoặc người học đã audit. Những nội dung đó có nhãn, lý do và xác nhận riêng.

## 2. Kiểm tra trace mà không gọi lại API

Tại gốc repository, sau khi có môi trường Python theo README:

```powershell
python -X utf8 scripts/verify_runtime_traces.py --traces results/agent/dev/C0 results/agent/dev/C1 results/agent/dev/C2 results/agent/dev/C3
python -X utf8 scripts/verify_runtime_traces.py --traces results/agent/test/C0 results/agent/test/C2
```

Không có `--output` thì hai lệnh chỉ đọc artifacts và in kết quả, không ghi đè báo cáo đã lưu. Verifier không mở Qdrant, không gọi API và không đọc gold benchmark.

Phạm vi kiểm tra:

- Chỉ các trường câu hỏi, scope, lịch sử query, context và phản hồi runtime được gửi; không có key `gold`, `expected_answer`, `answerable` trong user state.
- Hai message đúng vai trò; system prompt khớp SHA256 và độ dài request khớp dữ liệu đã ghi.
- `DOCUMENT_CONTEXT` khớp chính xác chunk được chọn và header nguồn; toàn bộ context nằm trong budget ký tự.
- Context cuối khớp request cuối của các case `answered`/`abstain`.
- Text, nguồn, page, metadata, offset của chunk khớp `data/chunks.jsonl` và `data/pages.jsonl`.
- Số kết quả thực trả, top-k, filter, lượt search và giới hạn model call đúng cấu hình.
- Native tool schema thay đổi theo trạng thái: tìm kiếm trước, hết lượt tìm chỉ còn trả lời/từ chối.
- Usage do provider trả về được giữ nguyên. `x_ckey.cost` là đơn vị native chưa xác định, không tự đổi thành USD.

Kết quả tại lần đã lưu: [dev](../results/runtime_trace_verification_dev.json) kiểm tra 68 trace; [test](../results/runtime_trace_verification_test.json) kiểm tra 14 trace. Các warning về citation xuất hiện trong phần diễn giải từ chối được giữ lại để audit, không bị xóa khỏi trace gốc.

Chạy test code:

```powershell
python -X utf8 -m unittest discover -s tests -v
```

Test tích hợp retrieval cần dữ liệu, model và index được chuẩn bị. Các test dùng fixture để kiểm tra loop/schema không được tính thành điểm chất lượng model.

## 3. Tái tạo retrieval từ nguồn remote đã khóa

Bằng chứng đã thực hiện: [results/retrieval_reproduction.json](../results/retrieval_reproduction.json).

Lần kiểm tra này dùng thư mục độc lập, không truyền `--day6-root`, bắt đầu không có model/vectors cache trong thư mục đó. Script tải snapshot Day06 ở commit `64c4ab778f81ba5608d4b2b57315f6369aedd0fd`, tải embedding model theo lock và tạo Qdrant riêng.

14 hạng mục đã qua gồm tải đúng nguồn remote, dựng lại 312 chunk/69 đơn vị nguồn, SHA256 của chunk/page/model lock, kiểm tra hash model, embedding byte-identical, Qdrant 312 điểm, offset, ba phương pháp trả chunk thật và thứ hạng/score giữ nguyên sau đóng rồi mở store.

Vector SHA256 ghi nhận: `266db21df0190f393a3c8b2927ef49c1a96b70c42801b628d095bf7157278fc9`.

Để tạo một bản độc lập mới, chọn **thư mục đích mới chưa sử dụng**:

```powershell
python -X utf8 scripts/prepare_data.py --root .local/retrieval_reproduction_new
```

Lệnh này tải model/dữ liệu và có thể mất thời gian. Nó chuẩn bị dữ liệu/index; không tự sinh lại artifact 14 checks của lần kiểm tra đã lưu. Không dựng lại vào thư mục store đang được process khác mở.

Giới hạn: bằng chứng hiện tại là trên cùng môi trường Windows/Python/packages nhưng ở thư mục dữ liệu độc lập. Đây không phải xác nhận một OS khác sẽ cho số thực hoặc vector giống từng byte.

## 4. Chạy lại API thật khác với đọc trace

Lệnh tạo workspace riêng và so sánh lại ba phương pháp retrieval trên dev:

```powershell
python -X utf8 scripts/reproduce.py
```

Đã thực thi thành công tại [reproduction_cli.json](../results/reproduction_cli.json): tải nguồn/model đã pin, re-embed, dựng store riêng và so sánh mọi ranked ID cùng Hit@1/Hit@3 với run gốc. Lệnh mặc định không gọi model trả lời. Đây là lần kiểm tra khác với artifact 14 checks của mục 3.

Nếu muốn chạy model thật trên dev trong workspace mới:

```powershell
python -X utf8 scripts/reproduce.py --api-dev
```

Lệnh có thể phát sinh phí. `.env` không bị chép sang workspace; private settings được nạp vào bộ nhớ tiến trình. Các nhãn/xác nhận cũ không được sao chép làm xác nhận cho run mới. Muốn tiếp tục từ một tiến trình khác, cung cấp biến môi trường hoặc `.env` riêng trong workspace mới. Cần chấm, review và chọn cấu hình lại nếu tạo thí nghiệm mới; output mới không được thay vào run gốc đã báo cáo.

Khai báo key trong `.env` local theo `.env.example`; không đưa key vào Git. `ModelClient` đọc `DAY07_MODEL`, `DAY07_BASE_URL`, `DAY07_API_STYLE` và các giới hạn timeout/retry. Tên model do gateway báo là alias của provider, không tự chứng minh model backend hoặc bảng giá của hãng gốc.

`scripts/run_experiments.py` có cơ chế resume: chỉ chạy case còn thiếu, giữ nguyên case lỗi ban đầu. Vì vậy gọi lại lệnh trên thư mục kết quả đã đầy đủ **không có nghĩa đã gọi lại toàn bộ model**. Muốn thí nghiệm mới cần giữ nguyên run gốc, tạo một root/run độc lập với dữ liệu, config và protocol được ghi rõ; không ghi đè trace đã chấm.

Không chỉnh source/config frozen rồi tiếp tục tuyên bố test cũ là đánh giá của phiên bản mới. Nếu muốn sửa dựa trên lỗi test, test đó phải được coi là dữ liệu development và cần một holdout mới để có đánh giá độc lập.

Token và chi phí phải được báo đúng nguồn: số token trong trace là **provider-reported**, còn `x_ckey.cost` chưa xác định đơn vị. Không suy ra số USD chỉ từ tên model hoặc giá của nhà cung cấp khác. API cost của controller chưa biết không được ghi bằng 0; điều này khác với embedding chạy local không dùng API.
