# ROI Memo 간단 가이드

현재 브랜치의 실제 Qt 화면입니다. 합성 예시 영상 두 장을 사용했습니다. MAIN 미병합 Draft 구현입니다.

## 1. 메인 화면

![메인 화면](01-main.png)

1. 기존 Files에서 비교할 영상을 선택합니다. 중복 Workspace/비교 Preset은 제거한 상태입니다.
2. **View → Memo**로 오른쪽 ROI 메모 패널을 엽니다. 별도 모드 전환은 없습니다.

## 2. ROI 단위로 기록

![ROI Memo](02-memo.png)

3. **Ctrl+드래그**로 ROI를 그리면 목록에 새 ROI가 추가되고 입력란이 비워집니다. 짧은 crop 캡처가 끝나면 설명을 입력합니다.
4. 다른 ROI를 그리면 새 메모를 시작합니다. 목록의 **ROI 1 / ROI 2**를 누르면 그 ROI와 설명으로 돌아갑니다. 목록은 파일 목록이 아닙니다.
5. 제목·설명은 타이핑하는 즉시 메모리에 반영됩니다. Update 버튼은 없습니다. **Add ROI / Delete**는 목록의 ROI를 추가·삭제합니다.
6. 필요하면 **Include current ROI statistics**로 새 ROI 기록에 현재 표시된 native 통계를 함께 넣습니다.

## 3. Save Memo 한 번

![미저장 Memo 패널](03-memo-panel.png)

7. 위쪽 **주황색 ● Unsaved**는 아직 메모리에만 있는 변경입니다.
8. **Save Memo…**를 누르면 ROI 메모, PNG crop, 선택한 통계 CSV와 HTML을 한 `.pxmemo` 파일에 보관합니다. 별도 Export 버튼은 없습니다.
9. 저장이 끝나면 **초록색 ● Saved**로 바뀝니다.

![저장된 상태](04-memo-saved.png)

10. `.pxmemo`는 ZIP 컨테이너입니다. PixelScope에서 다시 열어 편집하거나, 압축 도구로 사본을 풀어 `index.html`, `images/`, `statistics/`를 보고서에 사용할 수 있습니다. 원본 영상 전체를 넣지는 않습니다.

## 4. 파일 선택이 바뀌면 초기화

11. Files의 선택 영상이나 순서·비교 페이지가 달라지면 현재 ROI 목록과 입력이 초기화됩니다. 미저장 내용은 남지 않습니다. 예전 파일을 다시 선택해도 메모를 자동 검색·매칭하지 않습니다.
12. 과거 기록은 **Open Memo…**로 명시적으로 엽니다. 원본이 없거나 입력 설정이 없어도 저장된 crop과 설명은 읽을 수 있습니다. Memo 안에서 다른 파일을 찾아 선택하는 기능은 없습니다.
13. 앱 종료 시에도 저장하지 않은 메모는 폐기됩니다. 저장 중인 파일 작업은 완료된 뒤 닫습니다.

원본으로 이동하는 연동은 Memo → Viewer 방향만 유지합니다. 저장 crop은 8-bit preview이고, 선택한 CSV 통계는 native 수치입니다. 로컬 기록에는 원본 경로가 포함될 수 있으며 HTML은 자동 원본 경로를 제외합니다.

화면 캡처 실행: **1 passed in 3.38s**. 실제 사용자 수용성과 독립 리뷰는 별도이며, 현재 검증 기록은 [ROI 간소화 계획](../../exec-plans/active/memo-roi-simplification.md)을 참고합니다.
