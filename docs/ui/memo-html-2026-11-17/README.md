# UI-04 — Memo HTML 긴 문자열 표시

Parent [#230](https://github.com/delphykmc/pixelscope/issues/230),
작업 [#240](https://github.com/delphykmc/pixelscope/issues/240).
[변경 파일·검증 명령·제약](../../exec-plans/active/memo-html-readability.md).

1. **문제:** 실제 Chrome에서 긴 제목·메모·파일명이 오른쪽 화면 밖으로 나갔다.
   1689px viewport에서 document4760px, 메모 client1100px/scroll4465px였다.
2. **수정:** 긴 문자열을 자르지 않고 줄바꿈하고, figure를 보고서 폭 안으로 제한한다.
   메모의 줄바꿈, 이미지 원본 PNG·좌표, CSV·pxmemo map은 바꾸지 않는다.
3. **호환성:** 구형 ZIP의 legacy/v2 HTML 검증 규칙은 고정한다. 새 표시는v3로
   분리했으며, 이전 main에서 생성한 실제 합성 ZIP 두 개를 읽고 변조를 거부하는
   회귀를 포함한다. 새 기능/설정/별도 Export는 추가하지 않았다.
4. **확인:** unit49건11.03초, UI10건14.94초 통과. 최종 소스
   `562244935fe859e23d7f6dcb3a8887940867be20` 독립 리뷰PASS.
   실제 Chrome에서2/4/6-source×2ROI의 crop4/8/12개 모두 로드, CSV링크2개씩 표시.
   기본1689px에서 document1674px, 좁은960px에서945px로 가로 넘침 없음.

## 긴 문자열 조건 전후

Before: merged `e6e2265a`의 production save로 생성한 보고서다.
작은 합성 crop은 텍스트 배치 재현용이며 실제 큰 이미지 확인은 아래 별도 장면이다.
After는 같은 제목/메모/파일명 길이와 작은 crop 조건이며, CSV 링크도 포함한다.

![Before — 제목·메모가 화면 밖으로 넘어감](before.jpg)

![After — 긴 문자열을 화면 안에서 줄바꿈](after.jpg)

## 큰 crop·좁은 화면

![최종 v3 — 640×360 합성 crop과 줄바꿈된 설명](after-large.jpg)

![960px — 제목·메모와 crop이 화면 폭 안에 표시됨](after-narrow.jpg)

[실제 browser 측정 JSON](checks.json). 모든 입력·Statistics 값은 합성 데이터다.
PNG·브라우저 JPG는 이미지 품질 알고리즘 수용 증거가 아니며, HTTP로 표시한
정적 보고서의 화면 증거다. 직접 file URL 자동화는 보안 정책에 차단되어 중단했다.
허용된 loopback HTTP는 합성 보고서 폴더만 제공했으며 외부에 공개하지 않았다.
파일 직접 열기·CSV 다운로드 UI·물리 DPI·인쇄/PDF·모든 브라우저·신규 full pytest는
미검증이다. 원본 영상·사용자 저장물이나 공식 승인 User Guide PNG는 변경하지 않았다.
