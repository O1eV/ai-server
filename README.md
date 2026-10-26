# ai-sever: OvE AI 모델 서버 (FastAPI, PyTorch/ONNX)

Spring Boot가 최근 캔들을 보내면 Laya 모델이 BUY / HOLD / SELL 확률과 confidence를 돌려준다.
내부 전용 서버이며 실제 주문은 하지 않는다.

## 폴더 구조

```
app/            서빙 코드 (FastAPI)
  main.py       앱 생성, /health, 라우터 자동 등록
  api/          기능별 라우터 (모듈마다 router = APIRouter(...) 하나)
  core/         설정·로깅·수명주기·예외·의존성·모델 로딩
  dto/          요청/응답 pydantic 모델
  services/     기능 로직
common/         학습·서빙 공통 계약 (state 포맷, 질문 스키마, 라벨)
training/       학습 코드 (.py만, `python -m training.train`)
notebooks/      실험용 (프로덕션 로직 금지)
models/         로컬 체크포인트 (Git 제외, S3에서 배포)
data/           로컬 데이터셋 (원본 제외, meta.json만 추적)
outputs/        학습 산출물 (가중치 제외, 설정 JSON만 추적)
tests/          pytest
```

## 실행

```bash
.venv/bin/python -m uvicorn app.main:app --reload   # 저장소 루트에서
.venv/bin/python -m pytest
```

모델은 `models/Laya-finance` → `outputs/laya-trading` → `models/Laya` 순으로 찾고, 없으면
HuggingFace의 `convaiinnovations/laya`를 쓴다. `LAYA_MODEL_DIR`로 직접 지정할 수 있다.

## API

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/health` | 프로세스 생존 확인 |
| GET | `/api/v1/model/status` | 로드된 체크포인트 정보 |
| POST | `/api/v1/predict` | 캔들 → BUY/HOLD/SELL 확률 + confidence |

## 학습

```bash
.venv/bin/python -m training.train prepare --limit 200          # 데이터만 준비
.venv/bin/python -m training.train train --limit 200            # 준비 + 파인튜닝
.venv/bin/python -m training.train train --skip-prepare         # 이미 만든 JSONL로 재학습
```

`common/contract.py`의 state 포맷·질문 스키마는 학습과 추론이 공유한다. 이 값을 바꾸면
기존 체크포인트와 호환되지 않으므로 반드시 재학습한다.

## 브랜치별 소유 경로

PR이 같은 파일에서 충돌하지 않도록 아래 경로만 건드린다.

| 브랜치 | 소유 경로 |
| --- | --- |
| `feature/core` | `app/main.py`, `app/api/model_status.py`, `app/core/**`, `app/dto/**/__init__.py`, `common/**`, `tests/conftest.py`, `tests/test_contract.py`, `tests/test_health.py`, `.gitignore`, `README.md`, `AGENTS.md`, `requirements.txt` |
| `feature/prediction` | `app/api/prediction.py`, `app/services/**`, `app/dto/request/stock_data.py`, `app/dto/response/stock_decision.py`, `tests/test_prediction*.py` |
| `feature/training` | `training/**`, `data/*/meta.json`, `outputs/**/*.json`, `tests/test_training*.py` |

새 기능은 `app/api/`에 모듈만 추가하면 자동 등록된다. `app/main.py`는 수정하지 않는다.
머지 순서는 `feature/core` → `feature/prediction` / `feature/training`이다.
