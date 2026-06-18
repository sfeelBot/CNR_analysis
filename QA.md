# QA.md — 버그 기록

QA subagent가 코드 리뷰 + 실제 실행 테스트(헤드리스, `QT_QPA_PLATFORM=offscreen`)로 발견한 이슈.
형식은 [CLAUDE.md](CLAUDE.md) 3단계 규칙을 따른다.

## [2026-06-18] 라인/사각형 좌표를 canvas에 직접 set 했을 때 spinbox가 동기화되지 않음
- 증상: `ImageCanvas.set_line()`/`set_rect()`를 (드래그나 타이핑 경로가 아니라) 직접 호출하면
  `MainWindow`의 좌표 spinbox(`line_spins`/`rect_spins`)가 갱신되지 않고 이전 값(혹은 기본값 0)에 머무름.
  캔버스 상의 라인/사각형과 계산 결과(Signal/Noise/CNR)는 정확하지만, spinbox 표시만 stale해짐.
- 원인: `ImageCanvas.set_line`/`set_rect`는 내부 상태와 아티스트만 갱신하고 `line_changed`/`rect_changed`
  시그널을 emit하지 않음. spinbox 동기화(`_set_line_spins`/`_set_rect_spins`)는 그 시그널에 연결된
  `on_line_changed`/`on_rect_changed`에서만 일어나므로, 시그널 없이 직접 호출하는 경로는 빠짐.
  현재 GUI 안에서는 `on_line_coords_typed`/`on_rect_coords_typed`만 `canvas.set_line`/`set_rect`를
  직접 호출하는데, 그 경로는 마침 spinbox가 이미 올바른 값이라 증상이 안 보였을 뿐 — 추후 "좌표 붙여넣기",
  "초기화" 같은 기능을 추가하면 바로 드러날 잠재 버그.
- 재현 방법: 헤드리스로 `MainWindow` 생성 후 `win.canvas.set_line((0,8),(15,8))` 호출, `win.line_spins`의
  값들이 그대로 0인지 확인.
- 수정 내용: `ImageCanvas.set_line`/`set_rect`가 항상 `line_changed`/`rect_changed`를 emit하도록 변경.
  대신 `MainWindow.on_line_coords_typed`/`on_rect_coords_typed`에서 중복 호출이던 `recompute_and_redraw()`를
  제거하여(시그널 체인이 이미 처리) 이중 계산을 막음. `_set_line_spins`/`_set_rect_spins`는 같은 값을 다시
  쓸 때 `blockSignals`로 보호되어 있어 무한 루프는 발생하지 않음(확인됨).
- 상태: 수정완료

## [2026-06-18] width/height spinbox를 연속으로 바꾸면 중간 상태에서 가짜 에러 팝업이 뜸
- 증상: `.raw` 폴더에서 width를 먼저 바꾸고 곧바로 height를 바꾸면(예: 32 → 8), 두 값이 합쳐지기 전에
  "이전 height + 새 width" 조합으로 먼저 한 번 reload를 시도해 파일 크기 불일치 에러가 뜸. 최종적으로
  설정하려는 (width,height) 조합 자체는 올바른데도 중간 단계 때문에 사용자에게 혼란스러운 에러가 노출됨.
- 원인: `width_spin.valueChanged`와 `height_spin.valueChanged`가 각각 독립적으로 `on_raw_dims_changed`를
  호출하고, 그 즉시 `_load_current_file()`을 실행함 — 두 spinbox 값이 "같은 편집"의 일부라는 걸 합쳐서
  처리하는 로직이 없었음.
- 재현 방법: 헤드리스로 `.raw` 이미지(예: 32x8) 로드 후 `width_spin.setValue(8)` → 즉시 `height_spin.setValue(32)`
  순서로 호출(같은 호출 스택 안에서) 시 중간에 8x8 불일치로 reload 실패.
- 수정 내용: `on_raw_dims_changed`가 즉시 reload하지 않고 `QTimer.singleShot(0, ...)`로 reload를 다음
  이벤트 루프 틱으로 미루고, 같은 틱 안에서 또 변경이 들어오면 중복 예약하지 않도록
  `self._dims_reload_pending` 플래그로 한 번만 reload되게 묶음. 실제 GUI 사용(이벤트 루프가 돌아가는 상태)에서는
  같은 동작(연속 변경 → reload 1번)이 되고, 헤드리스 테스트에서는 `app.processEvents()`로 큐를 비워야
  reload가 실행됨(테스트 코드에서 유의).
- 상태: 수정완료

## 환경 한계 (앱 버그 아님, 기록만)
- `QT_QPA_PLATFORM=offscreen` 헤드리스 환경에서 `QMessageBox.critical`/`.warning` 호출이 Python 프로세스를
  세그폴트시킴 (앱 코드와 무관, 이 PyQt5/오프스크린 플랫폼 조합 자체의 한계로 보임 — `QMessageBox.critical(None,...)`
  단독 호출도 동일하게 재현됨). 실제 화면이 있는 환경에서는 정상 동작할 것으로 예상되며, 별도 확인 필요.
  헤드리스 자동 테스트에서 에러 다이얼로그 경로(잘못된 raw 크기 reload, 확장자 전환 시 매칭 파일 0개)는
  이 한계로 인해 다이얼로그 자체는 못 띄워봤지만, 그 아래의 `load_raw`/`load_image`가 올바른 `ValueError`를
  던지는 것은 별도로 검증됨.
