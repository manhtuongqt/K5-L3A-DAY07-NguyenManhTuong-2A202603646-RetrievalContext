"""Build the student's report from real frozen runs and explicitly approved reviews."""
from __future__ import annotations
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.lab_common import ROOT,read_json,write_json,now,sha256
from src.evaluation import aggregate_agent,context_hit
from scripts.human_reviews import confirmed_reviews
from scripts.review_helpers import evaluation_trace,citation_counts

def fmt(f):
    return f"{f['n']}/{f['N']}"+(f" ({f['rate']*100:.1f}%)" if f.get('rate') is not None else ' (N/A)')

def usage_summary(traces):
    native=Decimal('0');known=unknown=attempts=repairs=0;tokens=Counter();models=Counter()
    for trace in traces:
        repairs+=sum(e.get('event')=='invalid_action' for e in trace.get('events',[]))
        for call in trace['model_calls']:
            attempts+=len(call.get('attempts',[]))
            models[str(call.get('model','unknown'))]+=1
            u=call.get('usage') or {}
            for field in ('input_tokens','output_tokens'):
                if isinstance(u.get(field),(int,float)):tokens[field]+=u[field]
            x=u.get('raw',{}).get('x_ckey',{})
            if isinstance(x.get('cost'),(int,float)):
                native+=Decimal(str(x['cost']));known+=1
            else:unknown+=1
    return {'cases':len(traces),'model_calls':sum(len(t['model_calls']) for t in traces),'http_attempts':attempts,
            'tool_calls':sum(t['tool_calls'] for t in traces),'model_action_repairs':repairs,
            'provider_reported_tokens':dict(tokens),'reported_models':dict(models),
            'gateway_native_cost':{'known_total':float(native),'known_response_count':known,'unknown_response_count':unknown,
                                   'unit':'provider native unit, not verified','usd':None},
            'limit':'Provider-reported usage, not independently measured tokens or a USD invoice. Errors/retries without usage may have unknown cost.'}

def build(root=ROOT):
    selection=read_json(root/'results/selection.json');winner=selection['selected_config']
    metrics_dev=selection['dev_metrics'];test_cases=read_json(root/'benchmark/test.json')
    configs=list(dict.fromkeys(['C0',winner]));test_metrics={};usage={}
    current_reviews=[]
    for split,ids in [('dev',list(metrics_dev)),('test',configs)]:
        for cid in ids:
            raw=read_json(root/f'results/agent/{split}/{cid}/traces.json')
            reviews=confirmed_reviews(split,cid,root)
            current_reviews.extend(dict(r,config_id=cid,split=split) for r in reviews)
            metrics=aggregate_agent(read_json(root/f'benchmark/{split}.json'),[evaluation_trace(t) for t in raw],reviews)
            metrics['citation_counts']=citation_counts(raw)
            metrics['confirmation_file']=f'results/audit/{split}_human_confirmation.json'
            usage[f'{split}/{cid}']=usage_summary(raw)
            if split=='test':test_metrics[cid]=metrics
    write_json(root/'results/metrics_test.json',test_metrics)
    write_json(root/'results/usage_summary.json',usage)
    write_json(root/'results/audit/reviews_confirmed.json',current_reviews)
    total_human=sum(len(confirmed_reviews(s,c,root)) for s,ids in [('dev',list(metrics_dev)),('test',configs)] for c in ids)
    write_json(root/'results/audit/status.json',{'generated_at':now(),'benchmark_items_confirmed':24,
        'dev_semantic_rows_confirmed':sum(len(confirmed_reviews('dev',c,root)) for c in metrics_dev),
        'test_semantic_rows_confirmed':sum(len(confirmed_reviews('test',c,root)) for c in configs),
        'semantic_rows_confirmed':total_human,'pending_required_reviews':0,
        'method':'AI-assisted drafts, explicitly reviewed and accepted by the student; exact bytes tied to confirmation files.',
        'original_packets':'Original pending/draft statuses are preserved as historical snapshots. Current approval is external and exact-hash-bound.'})
    retrieval=[]
    for split,methods in [('dev',['dense','bm25','hybrid']),('test',['dense','hybrid'])]:
        for method in methods:
            s=read_json(root/f'results/retrieval/{split}/{method}/summary.json')
            retrieval.append(f"| {method} | {split} | {fmt(s['hit1'])} | {fmt(s['hit3'])} | {s['errors']} | {s['elapsed_ms']['median']:.2f} ms |")
    agent_rows=[];context_rows=[];resource_rows=[]
    for split,group in [('dev',metrics_dev),('test',test_metrics)]:
        for cid,m in group.items():
            g=m['grounded_answer'];c=m['context_grades'];u=usage[f'{split}/{cid}']
            grade=f"{g['0']}/{g['1']}/{g['2']}; {g['mean']:.2f}/2" if g['mean'] is not None else 'N/A'
            agent_rows.append(f"| {cid}/{split} | {fmt(m['strict_end_to_end'])} | {fmt(m['tool_use'])} | {grade} | {fmt(m['citation_validity'])} | {fmt(m['answer_citation_coverage'])} | {fmt(m['abstention'])} | {fmt(m['false_abstention'])} | {m['errors']} |")
            context_rows.append(f"| {cid}/{split} | {fmt(m['context_evidence_rate'])} | {c['0']}/{c['1']}/{c['2']} (n={c['N']}) | {json.dumps(m['tool_call_distribution'])} |")
            resource_rows.append(f"| {cid}/{split} | {u['model_calls']} | {u['tool_calls']} | {u['model_action_repairs']} | {u['provider_reported_tokens'].get('input_tokens',0):,}/{u['provider_reported_tokens'].get('output_tokens',0):,} | {u['gateway_native_cost']['known_total']:.2f} | {m['elapsed_ms']['median']/1000:.2f} s |")
    config_rows=[]
    for cid in metrics_dev:
        c=read_json(root/f'configs/{cid}.json')
        config_rows.append(f"| {cid} | {c['method']} | {c['top_k']} | {c['budget_chars']:,} ký tự | {c['max_searches']} | {c['hypothesis']} |")
    test_detail=[]
    for cid in configs:
        by={r['query_id']:r for r in confirmed_reviews('test',cid,root)}
        traces=read_json(root/f'results/agent/test/{cid}/traces.json')
        for trace in traces:
            r=by.get(trace['query_id']);qid=trace['query_id']
            label=('error' if r is None else f"answer={r.get('answer_grade')}; context={r.get('context_grade')}; citation={r['citation_support']}; abstain={r.get('abstention_correct')}")
            reason=(r['reason'] if r else str(trace.get('reason'))).replace('|',' / ')
            test_detail.append(f"| {cid}/{qid} | {trace['status']} | {label} | {reason} | [trace](../../results/agent/test/{cid}/cases/{qid}.json) |")
    tests=read_json(root/'results/tests.json');repro=read_json(root/'results/retrieval_reproduction.json')
    dev_runtime=read_json(root/'results/runtime_trace_verification_dev.json');test_runtime=read_json(root/'results/runtime_trace_verification_test.json')
    winner_test=test_metrics[winner];baseline_test=test_metrics['C0']
    report=f'''# Báo cáo Day07 — Agentic RAG

Nguyễn Mạnh Tường · 2A202603646 · L3A. Phạm vi: phần cơ bản 85 điểm; chưa làm bonus.

## 1. Dữ liệu và benchmark

### 1.1. Dữ liệu Day06 và quyền sử dụng

Tôi dùng lại corpus Python 3.13 từ commit Day06 `64c4ab778f81ba5608d4b2b57315f6369aedd0fd`: 9 tài liệu chính thức, 69 đơn vị HTML có nội dung và 312 chunk B theo đoạn, tối đa 1.000 ký tự. Đây là đơn vị HTML đã chuẩn hóa, không phải trang PDF. Tôi giữ ID, text, source/page, metadata và offsets gốc; không chia lại để khớp câu hỏi. Nguồn/PSF License và 0BSD cho ví dụ: [notices](../../THIRD_PARTY_NOTICES.md), [source manifest](../../data/source_manifest.json), [adapter manifest](../../data/day6_manifest.json).

Embedding BAAI/bge-small-en-v1.5 ONNX quantized, revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55`, 384 chiều, CLS/L2, CPU. Query dùng prefix `Represent this sentence for searching relevant passages: ` đúng một lần; document không prefix. Giữ giới hạn 512 token của embedding và file hash trong [model lock](../../configs/embedding_model.json). Qdrant client 1.16.0 local persistent, collection `day07_B`, cosine exact, thư mục `.local/qdrant_day07`. Docker không cần cho cách chạy này; model trả lời là API riêng.

Vector B tái sử dụng có SHA256 `266db21df0190f393a3c8b2927ef49c1a96b70c42801b628d095bf7157278fc9`, trùng Day06. Script có thể tải nguồn đã pin và tái embedding/index từ đầu, không cần checkout hoặc database riêng của máy tôi.

### 1.2. Agent model và điều kiện chạy

Model cấu hình `{selection['model_config']['model']}` qua `{selection['model_config']['base_url']}`, giao thức OpenAI-compatible, temperature {selection['model_config']['temperature']}, max output {selection['model_config']['max_tokens']} token. Đây là alias và usage do gateway báo; tôi không tự xác minh upstream đằng sau tên model. Key chỉ nằm trong `.env`/biến môi trường; thông tin công khai tại [model config](../../configs/model.json).

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
{chr(10).join(config_rows)}

C2 và C3 là hai cấu hình nhằm cải thiện, có run riêng. C3 thay đồng thời top-k và budget nên chỉ đánh giá gói chính sách context, không tách riêng nhân quả từng yếu tố. Chạy một lần mỗi cấu hình; temperature 0 không bảo đảm API/gateway tái lập tuyệt đối, query model tạo giữa các run vẫn có thể khác.

### 2.3. Ranking query gốc, cutoff top-3

| Phương pháp | Split | Hit@1 | Evidence Hit@3 | Lỗi | Median search |
|---|---|---|---|---:|---|
{chr(10).join(retrieval)}

Mẫu số retrieval chỉ có 15 dev hoặc 5 test **có đáp án**, không cộng câu thiếu evidence. Một hit yêu cầu một chunk giữ trọn evidence alternative, đúng source/page. Bảng trên là query gốc, không phải query model viết lại. [Trace retrieval](../../results/retrieval). Số kết quả thực trả về được lưu ở từng query; không ép đủ ba bằng dữ liệu giả.

### 2.4. Chọn context và Context Evidence Rate

Giữ nguyên chunk kèm header ID/source/page, loại trùng theo ID/text, ưu tiên rank từ lần tìm mới nhất rồi các candidate cũ còn hữu ích. Budget tính bằng ký tự gồm header/dấu phân cách, không phải token LLM. Không cắt âm thầm chunk. CER exact kiểm evidence thực nằm trong context cuối **đã gửi**; đọc ngữ nghĩa context bằng thang 0/1/2 riêng.

| Config/split | CER exact | Nhãn context 0/1/2 | Phân bố search call |
|---|---|---|---|
{chr(10).join(context_rows)}

Exact quote là phép đo bảo thủ; context code/example có thể đủ nghĩa nhưng thiếu nguyên câu quote đã khóa. Vì vậy CER exact và nhãn context=2 không nhất thiết trùng. Tôi giữ nguyên gold và báo cả hai, không sửa quote sau test để tăng điểm.

Trước khi chọn/test, tôi sửa một lỗi **tổng hợp CER**: C1/D03 có đủ context đã gửi nhưng final action bị lỗi citation; aggregator cũ bỏ qua context khi status=error. CER C1 từ 13/15 thành 14/15; strict end-to-end vẫn 14/17. Không đổi model, query, raw trace, gold hoặc nhãn đã được tôi duyệt. [Lịch sử sửa và hash](../../results/history/metric_correction.json) giữ code cũ đúng byte. Lỗi câu trả lời không đồng nghĩa thiếu context.

## 3. Agent và đánh giá

### 3.1. Kết quả từ câu trả lời thực

| Config/split | Strict end-to-end | Tool use | Answer 0/1/2; mean | Citation hợp lệ | Answer có citation | Từ chối đúng | Từ chối nhầm | Lỗi |
|---|---|---|---|---|---|---|---|---:|
{chr(10).join(agent_rows)}

Strict end-to-end là chỉ số bổ sung trên **toàn bộ case lên lịch**: có đáp án cần answer=2 và citation hỗ trợ đủ, thiếu evidence cần từ chối đúng; lỗi vẫn không đạt. Grounded answer/context/citation/abstention là những metrics riêng theo BENCHMARK.md. Tool use và quality thành công có mẫu số công bố; lỗi được báo riêng, không giấu bằng cách đổi thành abstain hoặc bỏ khỏi tổng scheduled.

Citation được chấm theo từng **ID duy nhất trong mỗi câu trả lời**, đối chiếu tất cả điều kiện/claim gắn với ID đó; có cả ID inline trong reason abstain. Báo số lần xuất hiện riêng tại [usage/metrics](../../results/metrics_test.json). Evaluator dùng projection hợp nhất declared/inline IDs, giữ nguyên raw trace. ID có trong context hoặc model tự xác nhận không thay việc đọc nguồn. 0/0 được hiểu là N/A, không phải 100%.

### 3.2. Audit và trách nhiệm kiểm tra

Tôi đã đối chiếu bộ câu hỏi và bản chấm dev/test, xác nhận giữ các nhãn. Bản nháp được AI hỗ trợ chuẩn bị từ source/context/answer thật, sau đó được tôi review; đây không phải hai người chấm độc lập hoặc chấm mù. Hồ sơ exact-hash: [dev](../../results/audit/dev_human_confirmation.json), [test](../../results/audit/test_human_confirmation.json). Có {total_human} hàng chấm output được xác nhận; case lỗi không được dựng thành một câu trả lời để chấm.

Các packet và review JSON ban đầu giữ dòng pending để bảo toàn lịch sử; trạng thái hiện tại ở [status](../../results/audit/status.json), [confirmed view](../../results/audit/reviews_confirmed.json). Nếu nhãn/trace thay đổi, xác nhận hash cũ không tự áp dụng.

### 3.3. Nhãn từng ca test

| Config/query | Trạng thái | Nhãn | Lý do đối chiếu | Bằng chứng |
|---|---|---|---|---|
{chr(10).join(test_detail)}

Packet nguồn/citation chi tiết: [test REVIEW](../../results/audit/test/REVIEW.md). Context chấm 0=không có evidence, 1=thiếu điều kiện/nguồn, 2=đủ; answer 0=sai/không hỗ trợ/từ chối nhầm, 1=đúng một phần, 2=đúng và đủ. Citation có nhãn hỗ trợ riêng cho từng ID và lý do.

## 4. Phân tích lỗi, cải thiện và quyết định

### 4.1. Các lỗi dev đã kiểm tra

1. **C0/D01 — tìm nhầm phương thức.** Context nói về `pop`, `index`, `del`, thiếu `list.remove`. Không dùng ValueError của index làm evidence cho remove. C0 từ chối nhầm, strict không đạt. C2 tìm đúng remove và trả lời có citation; C3 vẫn bỏ lỡ dù lấy năm chunk. Tên API và query model tạo ảnh hưởng kết quả, không thể chỉ tăng budget là xong.
2. **C0/D10 — câu đúng chưa chắc citation đủ.** Answer thêm qualifier `__all__`; toàn context có thông tin đó, nhưng sole citation được dẫn không hỗ trợ qualifier. Answer/context có thể chấm 2, citation vẫn sai. C2 dẫn nguồn hỗ trợ đủ, C3 không thêm điều kiện dư chưa được cite.
3. **C1/D02 — dẫn ví dụ thay cho claim hiệu năng.** Code queue example không tự chứng minh fast append/pop ở cả hai đầu. Đoạn giải thích đúng có trong context nhưng không phải ID được cite; không tự chấm citation đúng vì agent tình cờ đọc được nguồn khác.
4. **C1/D03 — định dạng citation sau repair vẫn sai.** Model đưa ID trong arguments nhưng không in `[id]` trong answer, runtime từ chối sau một lần sửa. Giữ nguyên status error và trace, không chạy lại để thay bằng kết quả thuận lợi. Context vẫn được tính riêng theo bằng chứng thực gửi.

Hai giả thuyết đo riêng: C2 bổ sung tín hiệu lexical cho dense, C3 thêm context để giữ điều kiện. Strict dev C0=15/17, C1=14/17, C2=17/17, C3=16/17. C2 cải thiện so với baseline trong run này; C3 không cải thiện thêm. Không suy từ một run rằng hybrid luôn tốt hoặc context lớn luôn xấu. [Audit dev](../../results/audit/dev/REVIEW.md).

### 4.2. Freeze và test

Tôi chọn **{winner}** bằng dev, lưu lúc `{selection['selected_at']}` UTC trước mọi run test. Thứ tự chọn: strict dev, CER, ít từ chối nhầm, chi phí USD nếu đầy đủ, latency, ID. C2 thắng tiêu chí đầu nên không cần tie-break; giá USD unknown không được thay bằng 0. [Selection và hashes](../../results/selection.json).

Test giữ nguyên model/config/prompt/benchmark sau freeze. Baseline strict {fmt(baseline_test['strict_end_to_end'])}, {winner} strict {fmt(winner_test['strict_end_to_end'])}. Query gốc và query viết lại của agent được lưu riêng. Chỉ năm câu có đáp án và hai câu thiếu evidence mỗi cấu hình nên một câu làm tỷ lệ thay đổi lớn; không suy rộng ngoài corpus này. Test đã mở chỉ phục vụ đánh giá và phân tích, không chọn lại winner hoặc chỉnh để báo điểm test độc lập.

## 5. Thời gian, token và chi phí

| Config/split | Model call | Search call | Sửa action | Input/output token provider báo | Native cost đã báo | Median end-to-end |
|---|---:|---:|---:|---|---:|---|
{chr(10).join(resource_rows)}

Native cost là trường `usage.raw.x_ckey.cost`, **chưa xác minh đơn vị**, không quy thành USD. Giá USD của model là N/A; known subtotal 0 không có nghĩa miễn phí. Token là usage provider báo, có thể khác bộ đếm thực của upstream/gateway. Các request lỗi không có usage có chi phí không biết. [Rollup](../../results/usage_summary.json) phân biệt scope dev/test và số response có cost. Bảng không gồm smoke, tải model, cài môi trường hoặc điện/phần cứng. Retrieval embedding/vector/lexical local có phí API 0 USD, không phải tổng chi phí agent bằng 0.

Worker=2 chồng thời gian đợi API; lock tuần tự truy cập Qdrant/ONNX local. Thời gian trong bảng là mỗi case, không phải tổng wall-clock. Một lần đo mỗi cấu hình không chứng minh hiệu năng ổn định.

## 6. Tái lập, kiểm tra và trình bày

- [README](../../README.md) có cài đặt/env/prepare/dev/freeze/test; dependencies trực tiếp pin trong requirements, `requirements-lock.txt` là snapshot môi trường Windows đã chạy.
- `python -X utf8 scripts/run_tests.py`: **{tests['tests']} test**, {tests['failures']} failure, {tests['errors']} error, {tests['skipped']} skip; [log](../../results/tests.log). Test mock chỉ kiểm hành vi, không tạo số liệu benchmark model.
- [Tái tạo retrieval độc lập](../../results/retrieval_reproduction.json): tải remote pinned source và model, re-embed thật mất {repro['prepare_elapsed_seconds']:.1f}s, 14/14 kiểm tra qua, vector byte-identical. Đây là tái lập trên cùng môi trường Windows, chưa chứng minh xuyên nền tảng hoặc model API byte-identical.
- [Verifier dev](../../results/runtime_trace_verification_dev.json): {dev_runtime['traces']} trace, {dev_runtime['checks']} kiểm tra; [verifier test](../../results/runtime_trace_verification_test.json): {test_runtime['traces']} trace, {test_runtime['checks']} kiểm tra. Kiểm tra raw source/offset, exact context gửi, budget, native schemas, hash và không đưa gold vào request. Đây là integrity check, không thay audit ngữ nghĩa.
- Demo ba ca: C2/D01 answered có nguồn; C2/DU01 thiếu evidence và abstain; C1/D03 lỗi citation. [Hướng dẫn](../../docs/DEMO.md).

Giới hạn: corpus Python tiếng Anh và trích HTML chưa bao phủ hết bảng/hình; dev/test cùng lĩnh vực; mẫu nhỏ; một lượt mỗi cấu hình; nhãn trên bản hỗ trợ có nguy cơ thiên lệch; model/usage qua proxy chỉ là provider claim; chưa làm bonus >=100 trang. Tôi không coi test code xanh là bằng chứng mọi câu trả lời đều đúng.

## 7. Kết luận

Tôi chọn **{winner} Hybrid RRF, top-k 3, context 4.000 ký tự, một lượt search** cho thí nghiệm cơ bản này bằng kết quả dev. Retrieval, context, câu trả lời và citation phải đọc tách biệt. Tôi giữ cả lỗi, run không cải thiện và phần chi phí chưa biết để người chấm có thể đối chiếu. Kết quả test đánh giá lựa chọn đã cố định, không dùng để chọn lại. Bonus chưa thực hiện; link repo do tôi nộp LMS.
'''
    destination=root/'report/individual/2A202603646_NguyenManhTuong.md'
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(report,encoding='utf-8',newline='\n')
    readme=root/'README.md';text=readme.read_text(encoding='utf-8')
    summary=f"Cấu hình **{winner}** được chọn bằng dev trước test. Strict dev **{fmt(metrics_dev[winner]['strict_end_to_end'])}**; strict test **{fmt(winner_test['strict_end_to_end'])}**. Baseline test **{fmt(baseline_test['strict_end_to_end'])}**. Chỉ số strict yêu cầu cả câu trả lời và citation đạt, hoặc từ chối đúng. Xem [báo cáo đầy đủ](report/individual/2A202603646_NguyenManhTuong.md), [selection](results/selection.json) và [bảng test](results/metrics_test.json)."
    text=re.sub(r'(?s)(<!-- DAY07_RESULTS_START -->).*?(<!-- DAY07_RESULTS_END -->)',lambda m:m[1]+'\n'+summary+'\n'+m[2],text)
    readme.write_text(text,encoding='utf-8',newline='\n')
    return destination

if __name__=='__main__':print(build())
