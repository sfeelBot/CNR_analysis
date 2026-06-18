# PREPROCESSING.md — 파일 로딩 & 측정 로직

> 최종 확인: 초기 구현 작성 시점 (코드와 함께 갱신할 것). 이 문서는 `image_io.py`, `measurements.py`, `batch.py`, `export.py`의
> 동작을 코드를 보지 않고도 파악할 수 있도록 설명한다. 코드를 수정했는데 이 문서가 그대로면 안 됨.

## 1. 파일 포맷 (`image_io.py`)

### `.raw`
- 헤더 없음, **16-bit unsigned little-endian** (`numpy dtype '<u2'`) grayscale, row-major(가로 우선)로 저장.
- width/height는 파일 안에 없으므로 GUI에서 입력받음 (시작 다이얼로그 + 메인 윈도우의 상시 spinbox, 둘 다 같은 값을 공유).
- 로딩 시 **파일 크기 검증**: `len(bytes) == width * height * 2` 가 아니면 `ValueError`. GUI는 이를 잡아서
  `QMessageBox`로 사용자에게 보여주고 크래시하지 않음.
- 로딩 결과는 `(height, width)` shape의 `uint16` ndarray. 측정에는 이 원본 값을 그대로 사용 (rescale 금지).

### `.bmp`
- Pillow(`PIL.Image.open`)로 로딩.
- 이미지 mode가 `"L"`(8-bit gray) 또는 `"I"`/`"I;16"`(16-bit gray)이면 픽셀 값을 그대로 사용.
- RGB/Palette 등 컬러 모드인 경우: 기본 동작은 **에러로 거부**(측정값 의미가 왜곡되므로). 그레이스케일이 아닌
  BMP를 그레이로 변환해서라도 열고 싶다면 GUI에 별도 옵션(opt-in 체크박스)으로만 허용 — 자동 변환은 하지 않음.
- 16-bit BMP는 비표준이라 Pillow 지원이 일관되지 않을 수 있음 — 로드 실패 시 명확한 에러 메시지로 표면화.

### 공통: raw 배열과 display 배열의 분리
- `LoadedImage.raw`: 측정에 사용하는 원본 numeric 배열 (uint16 또는 PIL이 반환한 원본 dtype). **절대 화면 표시용으로 정규화하지 않음.**
- `LoadedImage.display`: `to_display_uint8(raw, lo, hi)`로 `[lo, hi]` 범위를 0–255로 stretch한 배열, `imshow` 표시 전용.
- 이 둘을 절대 섞지 않는다 — signal/background/noise 계산은 항상 `raw`에서, 화면은 항상 `display`에서.

### Display range는 폴더/확장자 단위로 고정 (이미지마다 다시 계산하지 않음)
- `(lo, hi)`를 매 이미지마다 새로 계산(percentile 등)하면, 같은 raw 픽셀 값이라도 이미지마다 다른 회색
  밝기로 보여서 "같은 값 = 같은 밝기"가 깨짐. 이를 막기 위해 `(lo, hi)`는 **폴더(정확히는 현재 선택된
  확장자)당 한 번만** `default_display_range()`(첫 이미지의 1/99 percentile, 평탄 이미지면 min/max로
  fallback)로 계산해서 고정하고, 이후 모든 이미지에 동일하게 재사용한다.
- `MainWindow.display_range`가 이 고정값을 들고 있으며, `load_image(..., display_range=self.display_range)`로
  매 파일 로드에 전달한다. `display_range`가 `None`이면(폴더/확장자 변경 직후 첫 로드) `load_image`가
  `default_display_range()`로 기본값을 골라주고, `MainWindow`가 그 값을 받아 고정한다.
- 확장자를 바꾸면(`.raw`↔`.bmp`, 네이티브 값 범위가 보통 크게 다름) `display_range`를 `None`으로 리셋해
  새 확장자에서 다시 기본값을 계산한다. 반면 raw의 width/height만 바꾸는 것은 같은 바이트를 다르게
  reshape하는 것뿐이라 값 분포(히스토그램) 자체는 안 바뀌므로 `display_range`를 리셋하지 않는다.
- GUI의 "Display Range" Min/Max spinbox로 사용자가 직접 덮어쓸 수 있다 (의료영상 뷰어의 window/level과
  동일한 개념). 변경 시 디스크에서 다시 읽지 않고 이미 로드된 `raw`에서 `to_display_uint8`만 재계산.

### 확장자 추가 방법
`image_io.py`의 `EXT_LOADERS` dict에 `{".새확장자": loader_function}` 추가. GUI 확장자 콤보박스에도 추가.

## 2. 라인 프로파일 샘플링 (`measurements.sample_line_profile`)

- 입력: 이미지(raw 배열), 두 점 `p0=(x0,y0)`, `p1=(x1,y1)` (pixel 좌표, sub-pixel 가능, 축에 평행하지 않아도 됨).
- 샘플 개수 `num_points`는 기본적으로 `round(유클리드 거리) + 1` (이동 거리 1픽셀당 1샘플).
- `np.linspace(x0,x1,num_points)`, `np.linspace(y0,y1,num_points)`로 좌표를 만들고, **nearest-neighbor**
  (`np.round` 후 정수 인덱스, 이미지 경계로 clip)로 픽셀 값을 추출.
- **bilinear 보간을 쓰지 않는 이유**: signal/background는 "실제 픽셀 값"을 기준으로 정의되어야 하므로
  (사양: "plot 중 가장 낮은 값"), 보간으로 값이 섞이면 측정 의미가 왜곡됨. 향후 보간이 필요해지면 이 함수만
  교체하면 되지만, 결과 수치가 달라지므로 반드시 이 문서에 변경 사항을 기록할 것.
- 항상 `raw` 배열에 대해서만 호출 (display 배열 금지).

```python
def sample_line_profile(image, p0, p1, num_points=None):
    x0, y0 = p0; x1, y1 = p1
    if num_points is None:
        num_points = max(int(round(np.hypot(x1 - x0, y1 - y0))) + 1, 2)
    xs = np.linspace(x0, x1, num_points)
    ys = np.linspace(y0, y1, num_points)
    col = np.clip(np.round(xs).astype(int), 0, image.shape[1] - 1)
    row = np.clip(np.round(ys).astype(int), 0, image.shape[0] - 1)
    return image[row, col].astype(np.float64)
```

## 3. Signal / Background (`measurements.find_signal_and_background`)

라인 프로파일 배열 `P` (길이 `N`), 제외 margin `a` (GUI spinbox, 정수 ≥ 0, 사용자 조절 가능):

```
idx_min = argmin(P)
signal  = P[idx_min]                       # 프로파일 최저값 = signal

lo = clip(idx_min - a, 0, N)
hi = clip(idx_min + a + 1, 0, N)            # +1: 슬라이싱이 오른쪽 배제이므로
background_points = concat(P[0:lo], P[hi:N])
background_mean   = mean(background_points)
```

- `background_points`가 비어있으면(예: `a`가 너무 커서 전체 프로파일을 덮음) `background_mean = NaN` +
  GUI에 경고 표시. 예외를 던지지 않음.
- `a` 값을 바꾸면 같은 프로파일에 대해 즉시 재계산되어야 함 (라이브 갱신, GUI.md 참고).

## 4. Noise / Area (`measurements.compute_noise`)

사각형 ROI `(x0,y0)`–`(x1,y1)` (pixel 좌표, 사용자가 어느 방향으로 드래그해도 됨):

```
xa, xb = sorted([x0, x1]); ya, yb = sorted([y0, y1])
xa, xb = clip(round(xa), 0, W), clip(round(xb), 0, W)
ya, yb = clip(round(ya), 0, H), clip(round(yb), 0, H)
roi          = raw_image[ya:yb, xa:xb]
noise        = std(roi)              # population std, ddof=0 (numpy 기본값)
rect_min     = roi.min()
rect_max     = roi.max()
rect_mean    = roi.mean()
noise_min_max = rect_max - rect_min  # ROI 내 최대-최소 픽셀값 차이 (std와는 별개의 보조 지표)
area_px      = (xb - xa) * (yb - ya)   # == roi.size
```

- 클리핑 후 `roi.size == 0`이면 (ROI가 이미지 밖으로 완전히 나간 경우) `noise`/`noise_min_max`/`rect_min`/
  `rect_mean` 모두 `NaN`, GUI에 "ROI empty" 표시.
- `area_px`는 항상 정수 픽셀 개수(가로 픽셀 수 × 세로 픽셀 수)로 GUI에 함께 표시.
- `noise_min_max`, `rect_min`, `rect_mean`은 CNR 계산에는 쓰이지 않는 **참고용 추가 지표** — CNR은 여전히
  `noise`(표준편차) 기준. GUI 결과 패널과 배치 결과 테이블/Excel에 모두 별도 컬럼으로 노출.

## 5. CNR (`measurements.compute_cnr`)

```
CNR = abs((signal - background_mean) / noise)
```

- 항상 절대값으로 표시 — `signal`이 보통 라인 프로파일의 최저값이라 `background_mean`보다 작아 부호가
  음수로 나오기 쉬운데, CNR은 대비의 "크기"를 보는 지표이므로 부호 없이 절대값으로 통일.
- `noise == 0`이면 `ZeroDivisionError`를 내지 않고 `NaN`/`inf` 반환 + GUI에 "N/A — noise가 0" 표시.
  배치 처리 결과 테이블에서는 해당 행의 `error` 컬럼에 `"noise=0"` 기록.
- Excel로 내보낼 때 NaN은 빈 셀로 저장됨 — "데이터 없음"이 아니라 "noise가 0이라 계산 불가"라는 뜻이므로
  팝업/엑셀 어딘가에 이 규칙을 한 번 안내.

## 6. `measurements.measure()` — 단일 진입점

```
measure(image, line, rect, exclusion_margin) -> {
    "signal", "background_mean", "noise", "noise_min_max", "rect_min", "rect_mean",
    "area_px", "cnr",
    "idx_min", "background_points"  # ProfilePanel 시각화용
}
```
GUI의 실시간 갱신과 배치 처리(`batch.py`)가 **모두 이 함수 하나만** 호출한다. 둘이 따로 계산 로직을
구현하지 않는 이유는 단일 이미지에서 본 값과 배치 결과가 절대 어긋나지 않게 하기 위함.

## 7. 배치 처리 (`batch.py`)

1. `scan_folder(folder, ext)`: 선택된 확장자의 파일을 자연/알파벳 순으로 정렬해 리스트로 반환.
   GUI의 파일 목록과 배치 처리가 **같은 함수**를 호출 — 정렬 기준이 달라서 "화면에서 고른 기준 이미지"와
   "배치가 도는 순서"가 어긋나는 일이 없도록 함.
2. `run_batch(folder, ext, line, rect, exclusion_margin, width, height, progress_cb=None)`:
   - 폴더 내 각 파일에 대해 `load_image` → `measure()` 호출.
   - 파일 하나가 실패(크기 불일치, 손상 등)해도 **배치 전체를 멈추지 않음** — 해당 행에 `error` 메시지를
     기록하고 다음 파일로 진행.
   - `.raw`의 width/height는 기준 이미지에서 쓴 값을 그대로 재사용. 배치 도중 spinbox를 바꿔도 이미 시작된
     배치에는 영향 없음(시작 시점 값 캡처).
   - 라인/사각형 좌표는 기준 이미지에서 그린 **그대로의 픽셀 좌표**를 모든 파일에 동일하게 적용 — 폴더 내
     이미지 크기가 다르면 좌표가 이미지 밖을 가리킬 수 있으므로 `measure()` 내부 clip 로직이 그대로 적용됨.
3. 결과: `[{filename, signal, background_mean, noise, noise_min_max, rect_min, rect_mean, area_px, cnr, error}, ...]` 리스트.

## 8. Excel 내보내기 (`export.py`)

```python
export_to_xlsx(rows: list[dict], out_path: str)
# pandas.DataFrame(rows).to_excel(out_path, index=False, engine="openpyxl")
```
- 풀 정밀도 float 그대로 저장 (팝업 테이블의 소수점 자리수 표시는 화면용일 뿐, 내보내기에는 영향 없음).
- 저장 실패(파일이 다른 프로그램에서 열려 있음 등)는 예외를 잡아 GUI에서 `QMessageBox.critical`로 안내.

## 9. 도메인 주의사항 (구현/QA 시 항상 점검)

- raw 파일 크기 ≠ width×height×2 → 명확한 에러, 크래시 금지.
- BMP가 RGB/Palette면 기본적으로 거부 (opt-in 변환 전까지).
- 라인/사각형 좌표가 이미지 경계 밖이면 항상 clip (드래그 중 + 계산 직전 이중 방어).
- ROI가 클리핑 후 0 픽셀이 되는 경우.
- noise == 0인 경우.
- 제외 margin `a`가 너무 커서 background_points가 빈 경우.
- 폴더 내 이미지 크기가 기준 이미지와 다른 경우 (특히 `.bmp`는 raw처럼 보장이 없음).
- 좌표 rounding 컨벤션(`np.round`)을 라인 샘플링과 ROI 슬라이싱에서 동일하게 사용.
