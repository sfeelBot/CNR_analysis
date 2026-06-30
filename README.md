# CNR_analysis

16-bit unsigned little-endian RAW(또는 BMP) 이미지 폴더를 불러와 라인 프로파일과 사각형 ROI로
Signal / Background / Noise / CNR을 측정하는 PyQt5 데스크톱 도구입니다. 폴더 내 모든 이미지에
같은 좌표를 배치 적용해 결과를 팝업과 Excel로 내보낼 수 있습니다.

## 주요 기능

- 폴더 내 `.raw`(헤더 없는 16-bit unsigned little-endian) 또는 `.bmp` 이미지 목록 탐색, Prev/Next 탐색
- 폴더별 탭: 여러 폴더를 동시에 열어 각각 독립적으로 분석 (`"+"` 탭으로 추가, 탭을 탭바 밖으로 드래그하면
  별도 창으로 분리)
- 이미지 위에 라인을 그리면 다른 패널에 실시간 gray-value 프로파일 표시
- 프로파일 최저값을 Signal로, 그 주변 `±a` 픽셀을 제외한 나머지 구간의 평균을 Background로 측정 —
  Background/전체 프로파일의 min/max/std도 실시간으로 함께 표시
- 사각형 ROI로 Noise(표준편차), Noise(max-min), ROI 최소값/평균값, 픽셀 면적을 측정
- CNR = `|Signal - Background| / Noise` 자동 계산
- 마우스 스크롤로 확대/축소, 우클릭 드래그로 화면 이동
- 화면 표시 대비(Display Range)는 기본 `0`~`255`로 시작해 폴더 내 모든 이미지에 동일하게 고정 적용
  (수동 조절 가능), 측정값에는 영향 없음
- 라인/사각형 좌표를 폴더 내 모든 이미지에 동일하게 적용해 일괄 측정(Batch) 후 팝업 표 표시
- 결과를 Excel(.xlsx)로 내보내기

## 요구 사항

- Python 3.12+
- 의존 패키지: `requirements.txt` 참고 (PyQt5, matplotlib, numpy, Pillow, pandas, openpyxl)

## 설치 및 실행

```bash
pip install -r requirements.txt
python main.py
```

실행하면 폴더/확장자/(raw인 경우) width·height를 입력하는 시작 다이얼로그가 먼저 뜹니다.

## .exe 빌드 (Windows, PyInstaller)

```bash
pip install -r requirements-build.txt
pyinstaller CNR_Tool.spec
```

빌드 결과는 `dist/CNR_Tool/`(폴더 + `CNR_Tool.exe`, onedir 방식 — 단일 exe보다 실행이 빠름)에 생성됩니다.
이 폴더 전체를 그대로 복사해 배포하면 됩니다. `dist/`, `build/`는 git에 커밋하지 않습니다(`.gitignore`).
`CNR_Tool.spec`을 수정하면(아이콘 추가, 데이터 파일 포함 등) 다음 빌드부터 반영됩니다.

exe에는 빌드에 사용한 Python 인터프리터가 그대로 들어갑니다. "요구 사항"의 Python 3.12+ 중 실제 배포할
버전으로 빌드 환경을 맞추는 것을 권장합니다.

## 문서

- [CLAUDE.md](CLAUDE.md) — 이 저장소에서 코드를 변경할 때 따라야 하는 작업 순서(확인 → 구현 → QA)
- [GUI.md](GUI.md) — 화면 구성, 상태 머신, signal/slot 매핑 등 GUI 설계
- [PREPROCESSING.md](PREPROCESSING.md) — 파일 포맷, 측정 공식, 배치/내보내기 로직
- [QA.md](QA.md) — 발견된 버그와 수정 이력

## 프로젝트 구조

```
main.py                  엔트리 포인트
image_io.py              .raw/.bmp 로딩, 화면 표시용 normalize
measurements.py           signal/background/noise/area/CNR 계산 (순수 함수)
batch.py                  폴더 스캔 + 배치 측정
export.py                 Excel 내보내기
gui/
  main_window.py           최상위 윈도우 (폴더별 탭 관리, 탭 분리)
  analysis_page.py         탭 하나의 분석 화면 (파일 목록/캔버스/프로파일/결과)
  detachable_tab_bar.py    탭을 탭바 밖으로 드래그하면 분리 시그널을 emit하는 QTabBar
  image_canvas.py          이미지 표시 + 라인/사각형 드래그 + 줌/팬
  profile_panel.py         라이브 라인 프로파일 plot
  startup_dialog.py        폴더/확장자/크기 선택 다이얼로그
  results_dialog.py        배치 결과 표 + Excel 내보내기
CNR_Tool.spec              PyInstaller 빌드 설정 (onedir)
```
