# 화면 근거 기반 UI 순차 개선

Status: Active. Owner: ChatGPT-assisted. Date: 2026-11-13.
Parent: https://github.com/delphykmc/pixelscope/issues/230
Baseline: main 603626d14a479a2a7ad3de74d5b23f57a50abc0c.
Branch: codex/ui-readability-audit-20261113.

## 목표와 범위

최신 Memo/비교 계약을 기준으로 실제 Qt 화면의 식별/가독성/배치를 한 항목씩
개선한다. #210 본문 상단에 최신 계약과 #230 링크를 추가하고 기존 이력은 보존했다.
폐기한 Workspace/Profile/preset, 여러 Export, Memo 파일 탐색/매칭은 복구하지 않는다.
YUV 포맷/scene matching은 요구 확인 전 보류, 물리 DPI/SMB/패키징은 별도 증거가 필요하다.
이번 작업은 PR 병합/절전 예약을 포함하지 않는다.

## 현재 증거

baseline/ 아래 실제 main QWidget.grab 캡처/JSON: 기존 capture_ui_scene.py의
window_overview/statistics_workspace/six_image_multiview/difference_analysis/
histogram_docked/plots_floating 6장과 임시 하네스의 빈/narrow/default/Memo5장.
원본은 합성 배열, QSettings 격리. DPR1, 실제 가용 desktop1024x720.
1400x880/1680x980 QWidget은 desktop을 넘겨 렌더했으며 실제 FHD모니터 증거가 아니다.
Computer Use node_repl초기화는 os error3으로 두 번 실패, OS입력검증을 주장하지 않는다.

## 순차 항목

1. [UI-01 #231](https://github.com/delphykmc/pixelscope/issues/231): 좁은Memo창에서sidebar167/value36px, 범위가 …360으로생략됨.
   기존ROI owner의 표시만반응형으로재배치하고 Scope/Edit를유지한다.
   넓은배치/수치/원본identity/분석cache/Sync/resize물리배율 계약을보존한다.
2. Files/Stats 가독성은 관찰후보. 스크롤이설계된표를실패로판정하거나
   sidebar최소폭/자동배치를강제하지않는다. 별도근거확보후다음작업으로결정한다.
3. Memo float/긴ROI labels/생성HTML브라우저표시는 아직이baseline matrix에없어후속검토.

## 검증과 위험

ROI표시재배치는숫자계산이나Qt lifetime graph를추가하지않는다. ownedQObject eventFilter를
재사용하고 resize/font/text에따른reflow는멱등으로만적용한다. narrow/wide왕복,
Scope/Edit bounds, source/generation/ROI/request identity, 기존ROI/메모/physicalzoom을검증한다.
관련Qt tests와Ruff/format/mypy/docs/strictMkDocs를실행한다. 전체pytest는별도mergegate이고
과거1961PASS를새수정결과로표시하지않는다. 사용자미추적13항목은수정하지않는다.

## UI-01 implementation checkpoint

Source: ui/issue77_ui_design_followup.py; regression:
tests/ui/test_ui_readability_roi_summary.py. The existing owned QObject eventFilter
reflows Scope and Bounds only when the text/labels/Edit/margins need more room.
The summary occupies a full-width third row at narrow widths; the two-row wide
layout returns automatically. Scope can contract while Edit remains reachable.
No sidebar minimum, user preset or numerical/source/cache authority is introduced.

RED: new narrow test timed out because full summary was elided (1 failed8.39s).
After the change, new test plus existing ROI/UI-followup modules:16passed9.83s.
The regression checks narrow/wide round trips, control bounds, tooltip, source array
identity/generation, shared ROI and analysis request signature. These are focused
results, not a new full-suite claim. New capture source SHA follows the implementation
commit; canonical guide screenshots are not auto-promoted.

## Observed validation

- `.venv/Scripts/python -m pytest -q --tb=short tests/ui/test_ui_readability_roi_summary.py
  tests/ui/test_issue77_ui_design_followup.py tests/ui/test_issue77_wp_a_roi_usability.py
  tests/ui/test_memo_roi_workflow.py tests/ui/test_memo_chrome.py
  tests/ui/test_w01_physical_zoom.py tests/ui/test_w04_review_view_state.py
  tests/ui/test_beta_workspace_hardening.py --junitxml=temp/ui01-focused-20261113.xml`:
  **82 passed in 24.77s**.
- `.venv/Scripts/python -m mypy src`: success,134 source files.
- Baseline canonical6captures and fixed-size matrix5captures all exit0 with no
  capture errors. Native desktop1024x720; wider widget snapshots are explicitly
  renderer captures rather than physicalmonitor evidence.
- User Guide exactROI entry now names the existing Region/Edit dialog and Esc
  action; stale inline-field/ControlShiftR text was corrected from actual code.
- Review, final after screenshots and static/docs closeout remain pending here.
