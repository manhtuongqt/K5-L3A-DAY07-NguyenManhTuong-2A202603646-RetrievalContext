# Demo Day07 trong 2–4 phút

Nguyễn Mạnh Tường · 2A202603646 · L3A.

Mục tiêu buổi demo là giải thích đường đi **câu hỏi → tool tìm kiếm → kết quả → context thực gửi → câu trả lời và citation**, đồng thời cho thấy một ca từ chối và một lỗi thật. Demo đọc trace đã chạy bằng model thật, không gọi lại API và không cần UI.

## 1. Chuẩn bị trước khi nói

Mở PowerShell tại gốc repository. Dán hàm dưới đây một lần; hàm chỉ đọc JSON trên máy:

```powershell
function Show-Trace {
    param([string]$Path, [switch]$FullContext)
    $t = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    $t | Select-Object query_id, config_id, question, status, tool_calls, context_chars | Format-List
    foreach ($e in $t.events) {
        if ($e.event -eq 'search') {
            Write-Host "SEARCH: $($e.query)"
            Write-Host "ACTUAL RESULTS: $($e.actual_results) / requested $($e.top_k)"
            $e.results | Select-Object rank, id, page, score | Format-Table -AutoSize
        }
    }
    Write-Host "CONTEXT IDS: $($t.context_ids -join ', ')"
    if ($FullContext) { Write-Output $t.final_context_text }
    Write-Host 'ANSWER:'
    Write-Output $t.answer
    Write-Host "DECLARED CITATIONS: $($t.citations -join ', ')"
    if ($t.errors.Count -gt 0) { $t.errors | Format-Table -AutoSize }
}
```

Có thể mở các file JSON trong VS Code song song để đọc nguyên văn chunk và tham số function call. `final_context_text` là context thực gửi, không phải đoạn được ghép lại sau khi xem đáp án chuẩn. Trong `model_calls[-1].request_messages`, trường `DOCUMENT_CONTEXT` của user state cho phép đối chiếu lại điều đó.

## 2. Mở đầu — khoảng 25 giây

> “Tôi dùng lại 312 chunk B của Day06, giữ nguồn, ID và embedding tương thích. Day07 bổ sung ba phương pháp tìm kiếm: dense, BM25 và hybrid RRF. Model thật chọn truy vấn rồi đọc context để trả lời hoặc từ chối. Tôi thử các cấu hình trên dev, chọn C2 là hybrid, cố định lựa chọn rồi mới đánh giá test. Tôi sẽ mở trace đã lưu để thấy từng bước thực tế.”

Baseline C0 và cấu hình chọn C2 đều lấy tối đa ba đoạn, budget 4.000 ký tự, tối đa một lần search. Vì vậy, trong so sánh này không dùng việc tăng budget để giải thích thay đổi kết quả.

## 3. Ca có bằng chứng — khoảng 55 giây

```powershell
Show-Trace 'results/agent/dev/C0/cases/D01.json'
Show-Trace 'results/agent/dev/C2/cases/D01.json' -FullContext
```

Nguồn: [C0/D01](../results/agent/dev/C0/cases/D01.json), [C2/D01](../results/agent/dev/C2/cases/D01.json).

**Câu hỏi:** `list.remove(value)` không tìm thấy giá trị thì xảy ra điều gì?

1. Model chọn cùng truy vấn trong hai trace: `Python list.remove(value) behavior when value is not found exception`.
2. C0 trả ba đoạn về `pop`, `del` và xử lý ngoại lệ; chưa có bằng chứng đúng cho `remove`. Agent từ chối, thay vì trả lời từ kiến thức có sẵn.
3. C2 đưa đoạn `ab3a48bfeceaac6887a87ee2509c8786` vào **hạng ba** và context cuối. Đoạn thuộc `tutorial_datastructures:u001`, có điều kiện về `list.remove` và `ValueError`.
4. C2 trả lời đúng rằng phương thức ném `ValueError`, kèm citation của chính đoạn đó.

> “Cải thiện ở đây là đưa được bằng chứng cần thiết vào top-3 và context; top-1 của C2 vẫn là đoạn về `pop`. Tôi không diễn giải một ca này thành kết luận hybrid luôn đứng đầu hoặc luôn đúng.”

## 4. Ca thiếu bằng chứng — khoảng 30 giây

```powershell
Show-Trace 'results/agent/dev/C2/cases/DU01.json'
```

Nguồn: [C2/DU01](../results/agent/dev/C2/cases/DU01.json).

Câu hỏi yêu cầu throughput `json.dumps` theo MB/s trên Ryzen 7 7800X3D. Tool có trả ba đoạn liên quan tới JSON, nhưng không có phép đo phần cứng và benchmark được hỏi. Agent ghi `status=abstain`, không đoán một con số.

> “Tìm được đoạn cùng chủ đề chưa đủ để trả lời. Ca này minh họa việc từ chối khi context thiếu số đo. Còn nhãn ‘không đủ bằng chứng trong corpus’ được chuẩn bị và kiểm tra riêng trong benchmark; tôi không suy ra corpus thiếu thông tin chỉ vì top-3 không thấy.”

## 5. Một lỗi runtime thật — khoảng 35 giây

```powershell
Show-Trace 'results/agent/dev/C1/cases/D03.json'
```

Nguồn: [C1/D03](../results/agent/dev/C1/cases/D03.json).

Câu hỏi yêu cầu điều kiện dùng tuple làm khóa dictionary. Tool đã lấy được đoạn đúng `8f257d50689da00b6cba2c5c20f413ba`. Model khai báo ID trong mảng `citations`, nhưng không chèn `[ID]` trong câu trả lời. Sau một lượt yêu cầu sửa, model vẫn lặp lỗi đó.

> “Đây là lỗi định dạng citation ở đầu ra model, không phải không tìm được tài liệu. Runtime ghi hai `invalid_model_action` rồi dừng với `status=error`. Tôi giữ nguyên trace lỗi, không đổi thành ca từ chối đúng hoặc bỏ khỏi mẫu số đánh giá.”

Muốn xem hai lần model trả sai định dạng:

```powershell
$t = Get-Content 'results/agent/dev/C1/cases/D03.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$t.model_calls | ForEach-Object { $_.tool_calls | ConvertTo-Json -Depth 8 }
```

## 6. Vì sao citation đúng ID vẫn phải đọc? — khoảng 40 giây

```powershell
Show-Trace 'results/agent/test/C0/cases/T04.json' -FullContext
Show-Trace 'results/agent/test/C2/cases/T04.json'
```

Nguồn: [C0/T04](../results/agent/test/C0/cases/T04.json), [C2/T04](../results/agent/test/C2/cases/T04.json). Đây là phân tích sau test, không dùng để đổi cấu hình đã chọn.

Cả hai trả lời rằng `csvreader.line_num` đếm dòng nguồn, còn một record có thể chiếm nhiều dòng. C0 thêm ví dụ **quoted field chứa xuống dòng**, nhưng chỉ dẫn đoạn `line_num`. Điều kiện bổ sung đó được hỗ trợ ở đoạn `QUOTE_MINIMAL` khác trong context, không phải citation mà C0 thực sự ghi. C2 trả lời gọn đúng phần mà citation `2625d9a22a42a7d8c16e7d7e66e0bd01` hỗ trợ.

> “Vì vậy, tôi chấm grounding của câu trả lời và tính hỗ trợ của citation thành hai mục riêng. Một câu có thể đúng và có đủ bằng chứng trong toàn bộ context, nhưng citation gắn vào câu chưa hỗ trợ đầy đủ mọi điều kiện.”

## 7. Chốt — khoảng 20 giây

> “Kết quả của bài không chỉ là tìm đúng tài liệu. Tôi kiểm tra ba tầng: ranking có lấy được evidence không, context thực gửi có đủ không, rồi câu trả lời và citation có được nguồn hỗ trợ không. C2 được chọn bằng dev; test được dùng để báo kết quả và giới hạn. Các lần chạy, ca lỗi, nhãn và lý do đều được giữ lại để kiểm tra.”

## 8. Nếu người nghe muốn kiểm tra sâu

- [Lựa chọn và hash cố định trước test](../results/selection.json).
- [Metrics dev](../results/metrics_dev.json).
- [Kiểm tra tính nhất quán 68 trace dev](../results/runtime_trace_verification_dev.json).
- [Kiểm tra tính nhất quán 14 trace test](../results/runtime_trace_verification_test.json).
- [Tái tạo retrieval độc lập từ nguồn đã khóa](../results/retrieval_reproduction.json).
- [Nhãn/lý do test C0](../results/audit/test/C0_reviews.json) và [C2](../results/audit/test/C2_reviews.json). Trạng thái human review phải đọc theo artifact hiện tại; kiểm tra code tự động không thay thế xác nhận đó.

Không cần gọi lại API chỉ để trình bày. Việc chạy lại controller có thể phát sinh chi phí và không bảo đảm đầu ra giống từng byte. Đọc [REPRODUCTION.md](REPRODUCTION.md) để phân biệt kiểm tra trace, tái tạo retrieval và chạy lại model.
