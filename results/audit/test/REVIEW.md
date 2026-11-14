# Đối chiếu TEST: baseline C0 và cấu hình đã chọn C2

**Bản nháp AI hỗ trợ; cần người học đọc và xác nhận nhãn hiện tại. Không coi xác nhận DEV hoặc benchmark là xác nhận TEST.**

## Tiêu chí

- Đọc đủ 5 câu có đáp án và 2 câu thiếu evidence của từng cấu hình.
- Chấm context 0/1/2, câu trả lời 0/1/2; ghi lý do dựa trên nội dung và điều kiện thực tế.
- Chấm mọi citation ID xuất hiện, kể cả trong câu từ chối; có ID đúng chưa đủ chứng minh nội dung được hỗ trợ.
- Câu thiếu evidence chỉ đạt nếu thực sự từ chối mà không đoán số liệu hoặc thông tin triển khai riêng.
- Lỗi được báo riêng và vẫn là không đạt trong strict pass trên toàn bộ 7 câu.
- Không điều chỉnh cấu hình/gold/nhãn để nâng điểm sau khi đã nhìn test.

| Cấu hình | Nhãn output | Lỗi | Strict pass | Gói nguồn chi tiết |
|---|---:|---:|---:|---|
| C0 | 7 | 0 | 6/7 | [C0_REVIEW.md](C0_REVIEW.md) |
| C2 | 7 | 0 | 7/7 | [C2_REVIEW.md](C2_REVIEW.md) |

## C0

| Câu | Context | Answer | Từ chối đúng | Citation hỗ trợ | Lý do |
|---|---:|---:|---|---|---|
| T01 | 2 | 2 | None | True | The answer preserves all three escaping exceptions with ensure_ascii=False: quotation mark, reverse solidus and U+0000-U+001F control characters. These are explicitly listed in the cited source. |
| T02 | 2 | 2 | None | True | The answer says the callback receives each JSON float as a string and None defaults to float(num_str); both required conditions are explicitly in its citation. |
| T03 | 2 | 2 | None | True | The answer correctly gives extra fields as a list under restkey=None, missing fields filled by restval=None, the non-blank-row condition, and the optional fieldnames/first-row behavior. The cited paragraph supports all of these details. |
| T04 | 2 | 2 | None | False | The answer correctly distinguishes physical lines from parsed records because records may span multiple lines. Its additional quoted-field/line-break example is supported elsewhere in the actual context by QUOTE_MINIMAL chunk 2788ee6e34ada6b0c2c01ee5bf11f7b1. However it cites only the line_num paragraph, which does not establish that extra quoting condition; answer grounding and citation validity are scored separately. |
| T05 | 2 | 2 | None | True, True | The answer correctly states OSError for missing paths/symlink loops in strict mode, partial resolution and unchecked remainder in non-strict mode, and no exception for symlink loops in non-strict Python 3.13. The two citations collectively cover these behaviors and version condition. |
| TU01 | None | None | True | N/A | The response explicitly declines a p95 latency guarantee and does not invent timings, workload measurements or Windows-specific performance. It accurately states the supplied CSV usage documentation lacks that guarantee. |
| TU02 | None | None | True | N/A | The response declines to provide a production backup bucket or retention period. Its auxiliary statement mapping Path.unlink to os.remove/os.unlink is actually visible in the supplied correspondence table, and it invents no backup configuration. |

## C2

| Câu | Context | Answer | Từ chối đúng | Citation hỗ trợ | Lý do |
|---|---:|---:|---|---|---|
| T01 | 2 | 2 | None | True | The answer preserves all three escaping exceptions with ensure_ascii=False: quotation mark, reverse solidus and U+0000-U+001F control characters. These are explicitly listed in the cited source. |
| T02 | 2 | 2 | None | True | The answer says the callback receives each JSON float as a string and None defaults to float(num_str); both required conditions are explicitly in its citation. |
| T03 | 2 | 2 | None | True | The answer gives the complete overflow/underflow distinction, extra values in a restkey list, missing fields filled by restval, both None defaults and the non-blank-row qualifier, all directly supported. |
| T04 | 2 | 2 | None | True | The answer confines itself to the documented line-count versus record-count distinction and multi-line records. Unlike C0, it does not add a separately sourced quoted-field example. |
| T05 | 2 | 2 | None | True, True | The answer correctly states OSError for missing paths/symlink loops in strict mode, partial resolution and unchecked remainder in non-strict mode, and no exception for symlink loops in non-strict Python 3.13. The two citations collectively cover these behaviors and version condition. |
| TU01 | None | None | True | N/A | The response explicitly declines an unsupported p95 guarantee and supplies no guessed performance, upload-workload or Windows-specific timing. The missing deployment measurements match the frozen absence check. |
| TU02 | None | None | True | N/A | The response declines to invent the production project backup bucket or retention period. It only summarizes that the supplied Path.unlink material concerns deletion and does not contain private backup configuration. |