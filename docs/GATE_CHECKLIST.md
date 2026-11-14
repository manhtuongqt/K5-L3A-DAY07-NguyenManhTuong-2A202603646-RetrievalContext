# Đối chiếu gate phần cơ bản Day07

Kiểm tra: `2026-11-14T09:26:38.589855+00:00` UTC. Bonus để sau, không tính vào trạng thái phần cơ bản.

| Mục | Trạng thái | Bằng chứng |
|---|---|---|
| benchmark_24_with_frozen_sources | ĐẠT | `{'frozen_files_checked': 6, 'questions': 24, 'gold_alternatives_checked': 20, 'absence_checks': 4, 'human_review_status': 'pending', 'semantic_human_review_not_inferred': True}` |
| source_and_chunk_sizes | ĐẠT | `{'chunks': 312, 'units': 69}` |
| source_model_data_hashes | ĐẠT | `data/day6_manifest.json` |
| frozen_implementation | ĐẠT | `{'scripts/run_experiments.py': '0112049723dc5520e22d00335c764ec510ee3f554d734ce8cad50bbafbc01d4f', 'src/__init__.py': '2380716aa974a4be597273e46155600ed523406069ce2a73b0c0540030d569d8', 'src/agent_run` |
| frozen_configs | ĐẠT | `results/selection.json config_hashes` |
| frozen_dev_trace_and_label_files | ĐẠT | `results/selection.json dev_trace_hashes/dev_review_hashes` |
| selection_before_test | ĐẠT | `{'selected_at': '2026-11-14T09:09:02.330845+00:00', 'winner': 'C2'}` |
| human_benchmark_confirmation | ĐẠT | `results/audit/benchmark_human_confirmation.json` |
| dev_C0_complete_scheduled_cases | ĐẠT | `{'count': 17, 'expected': 17}` |
| dev_C0_semantic_reviews | ĐẠT | `{'reviewed': 17, 'errors': 0}` |
| dev_C1_complete_scheduled_cases | ĐẠT | `{'count': 17, 'expected': 17}` |
| dev_C1_semantic_reviews | ĐẠT | `{'reviewed': 16, 'errors': 1}` |
| dev_C2_complete_scheduled_cases | ĐẠT | `{'count': 17, 'expected': 17}` |
| dev_C2_semantic_reviews | ĐẠT | `{'reviewed': 17, 'errors': 0}` |
| dev_C3_complete_scheduled_cases | ĐẠT | `{'count': 17, 'expected': 17}` |
| dev_C3_semantic_reviews | ĐẠT | `{'reviewed': 17, 'errors': 0}` |
| test_C0_complete_scheduled_cases | ĐẠT | `{'count': 7, 'expected': 7}` |
| test_C0_semantic_reviews | ĐẠT | `{'reviewed': 7, 'errors': 0}` |
| test_C2_complete_scheduled_cases | ĐẠT | `{'count': 7, 'expected': 7}` |
| test_C2_semantic_reviews | ĐẠT | `{'reviewed': 7, 'errors': 0}` |
| all_metrics_recompute | ĐẠT | `[{'split': 'dev', 'config': 'C0', 'equal': True}, {'split': 'dev', 'config': 'C1', 'equal': True}, {'split': 'dev', 'config': 'C2', 'equal': True}, {'split': 'dev', 'config': 'C3', 'equal': True}, {'s` |
| all_real_runtime_trace_integrity | ĐẠT | `{'traces': 82, 'checks': 13766, 'errors': [], 'warnings': 2}` |
| model_native_tools_used | ĐẠT | `82 actual model-controlled traces; request schemas/messages retained` |
| retrieval_dense_top3_comparable | ĐẠT | `{'cases': 17, 'answerable': 15, 'hit1': 12, 'hit3': 13}` |
| retrieval_bm25_top3_comparable | ĐẠT | `{'cases': 17, 'answerable': 15, 'hit1': 12, 'hit3': 12}` |
| retrieval_hybrid_top3_comparable | ĐẠT | `{'cases': 17, 'answerable': 15, 'hit1': 13, 'hit3': 13}` |
| two_real_improvement_configurations | ĐẠT | `C2 rank fusion; C3 larger context policy; all have separate dev runs` |
| required_code_tests | ĐẠT | `{'run_at': '2026-11-14T09:09:01.609067+00:00', 'command': 'python -X utf8 scripts/run_tests.py', 'tests': 64, 'failures': 0, 'errors': 0, 'skipped': 0, 'passed': True, 'log': 'results/tests.log', 'sco` |
| remote_retrieval_reproduction | ĐẠT | `results/retrieval_reproduction.json` |
| documented_reproduction_cli_executed | ĐẠT | `results/reproduction_cli.json` |
| persistent_Qdrant_real_collection | ĐẠT | `{'collection': 'day07_B', 'points': 312}` |
| submission_documents_and_links | ĐẠT | `{'missing': [], 'broken': []}` |
| two_dev_errors_and_measured_limits | ĐẠT | `report sections 4–6` |
| known_secret_values_absent_and_private_paths_ignored | ĐẠT | `{'exposures': [], 'limit': 'Checks known configured secrets and ignored paths, not a proof against every possible secret.'}` |

Kết quả: **34/34 kiểm tra**, **81 hàng audit output đã xác nhận**, 82 trace agent thật.

Đây là kiểm tra yêu cầu và bằng chứng, không phải điểm giảng viên. Nhãn được người học đối chiếu/xác nhận, nguồn nháp hỗ trợ được giữ đúng lịch sử. Không còn yêu cầu review của phần cơ bản nếu mọi hash xác nhận vẫn khớp. Người học tự nộp link LMS.
