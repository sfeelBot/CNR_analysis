# GUI.md — 화면 구조 & 상호작용

> 최종 확인: 초기 구현 작성 시점 (코드와 함께 갱신할 것). 이 문서는 `gui/` 패키지의 구조와 동작을
> 코드를 보지 않고도 파악할 수 있도록 설명한다. 위젯을 추가/변경하면 이 문서도 같이 갱신할 것.

## 1. 레이아웃 개요 (`gui/main_window.py` — `MainWindow`)

`QSplitter` 기반 3분할:

- **좌측**: 확장자 선택 `QComboBox`(`.raw` / `.bmp`) + width/height `QSpinBox` 2개(`.raw` 선택 시만 활성화) +
  파일 목록 `QListWidget` + Prev/Next 버튼.
- **중앙**: `ImageCanvas` (이미지 + 라인/사각형 오버레이) + 모드 선택 버튼 3개("Navigate"/"Draw Line"/"Draw Rect",
  `QButtonGroup`으로 상호배타).
- **우측/하단**: `ProfilePanel`(라이브 라인 프로파일 plot) + 결과 표시 영역(아래 5절) + "Run Batch" 버튼.

## 2. 시작 흐름

1. `main.py`가 `QApplication` 생성 후 `StartupDialog` 실행.
2. `StartupDialog`: 폴더 선택(`QFileDialog.getExistingDirectory`) + 확장자 콤보 + (raw인 경우) width/height
   입력. 폴더가 비었거나 raw인데 width/height가 0이면 OK 비활성화.
3. 승인되면 `MainWindow`에 폴더/확장자/width/height를 넘겨 생성, 폴더 스캔 후 파일 목록 채움, 첫 파일 표시.
4. 확장자/width/height는 시작 후에도 메인 윈도우 상단 컨트롤에서 언제든 변경 가능 (값 바뀌면 현재 이미지 재로딩).

## 3. 상호작용 상태 머신 (`gui/image_canvas.py` — `ImageCanvas`)

`ImageCanvas`는 `FigureCanvasQTAgg` 서브클래스(이미 `QWidget`이므로 PyQt 시그널을 그대로 가질 수 있음).

### 모드
```
self.mode ∈ {"navigate", "line", "rect"}
```
모드는 메인 윈도우의 버튼 3개로 전환. 이미지를 바꿔도(`set_image`) 모드와 기존 라인/사각형 좌표는
유지된다 — 라인/사각형은 `ImageCanvas`의 영속 상태(`self._line`, `self._rect`)이며 `set_image`가
이 상태를 절대 초기화하지 않는다. (즉, 폴더 내 다른 이미지로 넘어가도 같은 픽셀 좌표의 라인/사각형이
그대로 보임 — 배치 처리가 "기준 이미지에서 그린 좌표를 재사용"하는 전제와 일치.)

### 드래그 하위 상태
```
self.drag_target ∈ {"new", "p0", "p1", "move", None}   # 라인: p0/p1, 사각형: 코너/move로 유사하게 확장
```
기존 라인의 끝점이나 사각형의 코너 근처(허용 오차 ~8px, 화면 좌표 기준)를 클릭하면 새로 그리는 대신
그 점을 다시 잡아 조정할 수 있다.

### 이벤트 핸들러 (matplotlib `mpl_connect`)
- `on_press`: 캔버스 밖 클릭 무시. `mode=="line"`이면 기존 끝점 근처 클릭 시 재조정(`drag_target="p0"/"p1"`),
  아니면 새 라인 시작(`drag_target="new"`). `mode=="rect"`도 동일한 논리(코너 재조정 vs 새 사각형).
  `mode=="navigate"`는 캔버스에 아무 동작 없음(필요시 matplotlib 기본 pan/zoom 사용).
- `on_motion`: `drag_target is None`이면 무시. 현재 좌표로 라인/사각형 아티스트의 데이터만 갱신
  (`set_data`/`set_bounds`) 하고 **`canvas.draw()` 전체 리드로우는 호출하지 않음** — 대신 블리팅
  (`restore_region` → `draw_artist` → `blit`)으로 갱신해 큰 이미지에서도 드래그가 끊기지 않게 함.
  매 motion 이벤트마다 `line_changed`/`rect_changed` 시그널을 emit — 이것이 "LIVE 갱신"의 핵심이며,
  release를 기다리지 않고 드래그 중에도 계속 갱신된다.
- `on_release`: `drag_target=None`으로 리셋, 다음 블리팅 사이클을 위해 배경 비트맵 재캡처.

### Qt 시그널
```python
line_changed = pyqtSignal(tuple, tuple)   # (p0, p1), pixel 좌표, drag 중 매 프레임 emit
rect_changed = pyqtSignal(tuple)          # (x0, y0, x1, y1), drag 중 매 프레임 emit
```

### 주요 메서드
```python
set_mode(mode)
set_image(display_array)        # 파일 전환 시: im.set_data()만 교체, 라인/사각형 아티스트는 그대로
set_line(p0, p1)                # 프로그램에서 좌표 강제 설정 (spinbox 수동 입력 반영용)
set_rect(x0, y0, x1, y1)
get_line() -> tuple | None
get_rect() -> tuple | None
```

### 왜 `matplotlib.widgets.RectangleSelector`를 안 쓰는가
라인 드래그와 동일한 press/motion/release 핸들러 + 블리팅 배경을 공유하기 위해 사각형도 수동 구현한다.
`RectangleSelector`의 내부 상태 머신이 모드 전환(라인↔사각형↔네비게이트)과 충돌할 수 있어 일관성을 위해
수동 구현을 채택했다.

## 4. 라이브 프로파일 패널 (`gui/profile_panel.py` — `ProfilePanel`)

```python
update_profile(profile: np.ndarray, idx_min: int, exclusion_lo: int, exclusion_hi: int)
```
프로파일 선, 최저값 지점 마커, `±a` 제외 구간 음영을 그린다. **블리팅을 쓰지 않고 매번 가벼운 전체
`draw()`를 호출** — 매 갱신마다 y축 범위가 새 프로파일의 min/max로 autoscale되어야 하므로 블리팅 배경을
고정해 둘 수가 없기 때문. 프로파일 길이가 작아(이미지 대각선 길이 이하) 전체 redraw도 충분히 빠르다.
드래그 반응성이 중요한 쪽은 `ImageCanvas`이며, 그쪽만 블리팅을 사용한다.

## 5. 결과 표시 / 파라미터 패널 (`MainWindow` 내부)

- `a` (제외 margin) `QSpinBox` — 변경 시 현재 라인의 프로파일을 즉시 재계산.
- 라인 좌표 `QDoubleSpinBox` 4개(x0,y0,x1,y1), 사각형 좌표 4개(x0,y0,x1,y1) — 드래그로 그린 값이 자동
  반영되고, 직접 타이핑해서 미세 조정도 가능 (양방향 동기화, 무한 루프 방지를 위해 갱신 중 `blockSignals` 사용).
- 읽기 전용 라벨: Signal, Background mean, Noise, Area(px), CNR.
- "Run Batch" 버튼: 라인과 사각형이 모두 설정된 경우에만 활성화.

## 6. Signal/Slot 매핑

| 시그널 | 슬롯 | 효과 |
|---|---|---|
| `file_list.currentRowChanged` | `on_file_selected` | 이미지 로드 후 `canvas.set_image`, 결과 재계산 |
| `ext_combo.currentTextChanged` | `on_extension_changed` | 폴더 재스캔, raw용 width/height 입력 활성/비활성 |
| `width_spin/height_spin.valueChanged` | `on_raw_dims_changed` | 현재 raw 이미지 재로딩 |
| `margin_spin.valueChanged`(`a`) | `recompute_and_redraw` | 현재 라인 기준 signal/background 재계산 |
| `mode_*_btn.toggled` | `canvas.set_mode` | 캔버스 상호작용 모드 전환 |
| `canvas.line_changed` | `on_line_changed` | 프로파일 재계산 + ProfilePanel/라벨/spinbox 갱신 |
| `canvas.rect_changed` | `on_rect_changed` | noise/area 재계산 + 라벨/spinbox 갱신 |
| `line_coord_spins[*].valueChanged` | `on_line_coords_typed` | 타이핑된 좌표를 `canvas.set_line`에 반영 |
| `rect_coord_spins[*].valueChanged` | `on_rect_coords_typed` | 타이핑된 좌표를 `canvas.set_rect`에 반영 |
| `run_batch_btn.clicked` | `on_run_batch` | `batch.run_batch()` 실행 → `ResultsDialog` 표시 |

## 7. GUI 파라미터 ↔ 계산 함수 매핑

| GUI 컨트롤 | 전달되는 함수 (PREPROCESSING.md 참고) |
|---|---|
| 확장자 콤보 | `image_io.load_image(ext=...)` |
| width/height spinbox | `image_io.load_raw(width, height)` |
| 라인 좌표(드래그/타이핑) | `measurements.sample_line_profile(p0, p1)` |
| `a` spinbox | `measurements.find_signal_and_background(exclusion_margin=a)` |
| 사각형 좌표(드래그/타이핑) | `measurements.compute_noise(rect)` |
| Run Batch | `batch.run_batch(line, rect, exclusion_margin, width, height)` |

## 8. 배치 결과 팝업 (`gui/results_dialog.py` — `ResultsDialog`)

- `QTableWidget` 컬럼: filename, signal, background_mean, noise, area_px, cnr, error.
- `error`가 있는 행은 배경색으로 강조(예: 빨간 배경) — 값이 비어 있는 게 아니라 실패했다는 것을 표시.
- "Export to Excel" 버튼 → `QFileDialog.getSaveFileName` → `export.export_to_xlsx`. 성공/실패 각각
  `QMessageBox.information`/`critical`로 안내.

## 9. 성능 관련 메모

- `ImageCanvas`는 이미지 전환/드래그 시작 시에만 전체 `draw()` 호출, 드래그 중에는 항상 블리팅.
- `ProfilePanel`은 매 갱신마다 전체 `draw()` (8절 참고) — 데이터가 작아 문제 없음.
- `sample_line_profile`/`compute_noise`는 motion 이벤트마다 호출되지만 연산량이 작아(프로파일 길이는
  이미지 대각선 길이 이하) 실시간성에 문제 없음. 만약 향후 이미지가 매우 커져 느려지면 이 부분부터 최적화.
