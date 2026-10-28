# 맥(MPS)에서 AI 서버 로컬 실행 & EC2 Spring 연동

발표용으로 맥에서 AI 서버를 띄우고, EC2의 Spring Boot가 터널로 호출하는 구성이다.
Spring의 첫 호출 타임아웃(500ms)을 넘지 않도록 서버 시작 시 워밍업이 자동으로 돌아간다.

## 1. 맥에서 실행

```bash
cd <ai-sever 저장소 루트>
.venv/bin/python -m uvicorn app.main:app --reload
```

시작 로그에서 아래 두 줄이 나오면 준비된 것이다.

```
워밍업 완료: BUY (interval=1d)
준비 완료: <model_path> (mps)
```

- 디바이스는 기본이 `auto` → 맥이면 `mps`로 자동 선택된다 (`LAYA_DEVICE=cpu`로 강제 가능).
- 모델은 `models/Laya-finance` → `outputs/laya-trading` → `models/Laya` → HuggingFace 순으로 찾는다.
- **워밍업 실패해도 서버는 뜬다.** 로그에 `워밍업 실패(무시하고 계속 시작)`만 남고 계속 구동된다.

## 2. MODEL_API_KEY 설정 (인증)

이 서버는 기본이 **fail-closed**다. `MODEL_API_KEY`가 비어 있으면 **모든 요청이 401**이다.

```bash
# 키 생성 (값은 임의의 긴 랜덤 문자열이면 된다)
openssl rand -hex 32

# 같은 터미널에서 키를 넣고 서버를 띄운다
export MODEL_API_KEY="<생성한 키>"
.venv/bin/python -m uvicorn app.main:app --reload
```

호출부(Spring)는 요청 헤더에 **같은 값**을 `X-API-KEY`로 실어보낸다.

```bash
# 401이 떠야 정상 (인증이 걸려있다는 뜻)
curl -X POST http://127.0.0.1:8000/api/v1/predict \
  -H "Content-Type: application/json" -d '<본문>'

# 200이 떠야 정상
curl -X POST http://127.0.0.1:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <생성한 키>" \
  -d '<본문>'
```

주의:

- `export`는 **서버를 띄운 그 셸에만** 적용된다. 다른 터미널에서 실행하면 키가 없다.
- `.env` 파일은 **읽히지 않는다** (`load_dotenv()`가 없다). 꼭 셸 환경변수로 넣어야 한다.
- 키는 코드·Git에 절대 넣지 않는다 (`.gitignore`에도 있으나 커밋 자체를 금지한다).

### 로컬에서 인증 끄기 (개발용 전용)

```bash
export ALLOW_INSECURE_NO_AUTH=1
```

이걸로만 인증을 해제할 수 있다. **발표/운영 환경에서는 쓰지 않는다.**

## 3. 터널 열기 (EC2 Spring이 맥을 호출하도록)

### 방안 A. SSH 역터널 (별도 서버 불필요)

맥(클라이언트)에서 실행한다. EC2의 8000 포트로 오는 요청을 내 맥의 8000으로 보낸다.

```bash
# 맥에서 실행 (-N: 쉘만 열고 명령은 안 돌림)
ssh -N -R 8000:127.0.0.1:8000 ec2-user@<EC2_PUBLIC_IP>
```

그러면 **EC2의 `127.0.0.1:8000`** 로 오는 요청이 맥의 uvicorn으로 간다.
Spring은 공인 IP 없이 `http://127.0.0.1:8000` 으로 호출하면 된다.

> EC2의 8000 포트가 비어있어야 한다. EC2에서 이미 다른 서비스가 8000을 쓰면 포트를 바꾸고
> 양쪽(`-R <포트>`와 Spring의 `MODEL_BASE_URL`)을 같은 값으로 맞춘다.
> 접속이 끊기면 터널도 죽으므로 `autossh`로 유지하거나 재연결 스크립트를 쓴다.

### 방안 B. Cloudflare Tunnel (터널 유지가 쉬움)

```bash
# 맥에서 (cloudflared 설치 후)
cloudflared tunnel --url http://127.0.0.1:8000
```

출력된 `https://<서브도메인>.trycloudflare.com` 주소를 Spring의 `MODEL_BASE_URL`에 넣는다.

- 맥을 재시작해도 같은 주소를 유지하려면 named tunnel을 만들어야 한다.
- **이 주소는 누구나 알면 접근 가능**하므로 `MODEL_API_KEY`를 반드시 설정한다.
  (역터널은 EC2 안에서만 보이므로 공개 노출이 없다.)

## 4. Spring 쪽 환경변수

| 이름 | 값 | 설명 |
| --- | --- | --- |
| `MODEL_BASE_URL` | `http://127.0.0.1:8000` (역터널) 또는 `https://<...>.trycloudflare.com` | AI 서버 주소 |
| `MODEL_API_KEY` | 맥의 `MODEL_API_KEY`와 **같은 값** | `X-API-KEY` 헤더로 보낸다 |
| `model.enabled` | `true` | AI 호출 기능 on/off |

양쪽 키가 다르면 전부 401이다. Spring이 401을 받으면 모델 호출을 건너뛰므로
신호가 아예 안 나오는 증상으로 나타날 수 있다.

`application.yml` 예시:

```yaml
model:
  enabled: true
  base-url: ${MODEL_BASE_URL:http://127.0.0.1:8000}
  api-key: ${MODEL_API_KEY:}
```

## 5. 워밍업이 왜 필요한가

- 첫 추론 호출은 모델 준비 때문에 약 **3초**가 걸린다.
- Spring의 HTTP 타임아웃은 **500ms** → 첫 호출이 500으로 실패한다.
- 그래서 서버 시작(lifespan) 때 더미 캔들 15개로 `predict`를 1회 호출해 예열한다.
  이후 요청부터는 준비된 모델을 써서 500ms 안에 답한다.

```bash
# 워밍업을 끄고 싶을 때 (디버깅용)
export LAYA_WARMUP=0
```

기본값은 `1`(켜짐)이다.

## 6. 발표 전 점검 순서

1. `git pull origin dev` — 최신 코드인지 확인
2. `MODEL_API_KEY` 설정 → 서버 기동
3. 로그에 `워밍업 완료` 확인 (실패해도 진행하되, 뜨면 가장 안전)
4. `curl`로 401 → 올바른 키로 200 확인
5. 터널 열기 (역터널이면 SSH, 아니면 cloudflared)
6. Spring의 `MODEL_BASE_URL` / `MODEL_API_KEY` / `model.enabled` 확인
7. Spring에서 실제 신호 1건 정상 발행되는지 확인
8. 발표 중 맥 절전 해제 및 터널 생존 여부 확인

문제 날 때:

| 증상 | 원인 |
| --- | --- |
| 전부 401 | `MODEL_API_KEY` 미설정이거나 양쪽 키 불일치, 헤더명 `X-API-KEY` 오타 |
| 첫 호출만 실패 | 워밍업이 꺼져 있다 (`LAYA_WARMUP` 확인) |
| 연결 거부 | 터널이 죽었거나 `MODEL_BASE_URL` 포트 불일치 |
| 500 | 로그의 `prediction_failed` 확인 (모델 경로/디바이스 문제일 가능성) |
