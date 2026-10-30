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
# EC2 보안 그룹에서 TCP 22 인바운드를 맥의 공인 IP로 제한한 뒤 실행
# Amazon Linux 기본 사용자: ec2-user, Ubuntu AMI: ubuntu
ssh -i <EC2_KEY.pem> -N -R 8000:127.0.0.1:8000 ec2-user@<EC2_PUBLIC_IP>
```

이 연결은 **맥에서 EC2로 나가는 SSH 연결**이다. EC2 보안 그룹에 AI 포트(8000)를 인터넷 대상으로
열 필요는 없다. SSH 인바운드 TCP 22는 가능한 한 맥의 현재 공인 IP(`/32`)로 제한한다.
그러면 **EC2 호스트의 `127.0.0.1:8000`** 로 오는 요청이 맥의 uvicorn으로 간다.
Spring이 EC2 호스트에서 직접 실행되면 `MODEL_BASE_URL=http://127.0.0.1:8000`으로 호출하면 된다.

**Spring이 Docker Compose 컨테이너 안에서 실행되는 경우**, 컨테이너의 `127.0.0.1`은 컨테이너
자신이다. 또한 위의 기본 `ssh -R 8000:...`은 EC2 호스트의 loopback에만 리스닝하므로,
`host.docker.internal`로 바꾸는 것만으로 컨테이너에서 접근할 수 있는 것은 아니다. 권장 순서는
Spring을 EC2 호스트 네트워크에서 실행하거나 Cloudflare Tunnel URL을 쓰는 것이다. Docker를 쓸 경우
Spring이 EC2 호스트로 연결할 수 있도록 호스트 게이트웨이를 설정할 수 있지만, SSH 원격 포트가
loopback 전용이면 이 설정만으로는 접근이 되지 않는다.

보안팀이 허용하고 네트워크 접근을 제한할 수 있을 때만 SSH 원격 포트를 EC2 사설 IP에 바인딩하도록
sshd의 `GatewayPorts clientspecified` 설정을 검토한다. 이 경우 `ssh -R <EC2_PRIVATE_IP>:8000:127.0.0.1:8000`
형태를 사용하고, 보안 그룹/호스트 방화벽에서 해당 포트를 필요한 소스에만 허용한다.
`MODEL_API_KEY`도 반드시 설정하며 공개 인터페이스에 무제한으로 바인딩하지 않는다.

EC2의 포트가 이미 사용 중이면 `-R`의 원격 포트와 Spring의 `MODEL_BASE_URL` 포트를 같은 값으로
바꾼다. SSH 접속이 끊기면 터널도 종료되므로 `autossh` 또는 서비스 관리자의 재시작 정책 등으로
연결을 유지한다.

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
| `MODEL_BASE_URL` | 호스트 네트워크/역터널: `http://127.0.0.1:8000`; Cloudflare: `https://<...>.trycloudflare.com`; 허용된 EC2 사설 인터페이스 바인딩: `http://<EC2_PRIVATE_IP>:8000` | AI 서버의 base URL. 요청 경로는 `/api/v1/predict` |
| `MODEL_API_KEY` | 맥 AI 서버의 `MODEL_API_KEY`와 **동일한 값** | Spring이 요청 헤더 `X-API-KEY`로 전달 |
| `model.enabled` | `true` | Spring AI 호출 기능 on/off (application 설정) |

양쪽 키가 다르면 전부 401이다. Spring이 401을 받으면 모델 호출을 건너뛰므로
신호가 아예 안 나오는 증상으로 나타날 수 있다. Spring의 HTTP 클라이언트는 base URL 뒤에
`/api/v1/predict`를 붙여 POST하고, JSON 캔들 배열을 보내면서 `X-API-KEY` 헤더를 전달해야 한다.

EC2에서는 키를 Git 저장소나 커밋된 `application.yml`에 넣지 않는다. AWS Systems Manager
Parameter Store의 SecureString 또는 Secrets Manager 등에서 배포 시점에 가져와 Spring 프로세스의
`MODEL_API_KEY` 환경변수로 주입한다. EC2 인스턴스 역할에는 해당 시크릿을 읽는 데 필요한 권한만
부여하고, 키는 로그에 출력하지 않는다. Compose를 쓴다면 `.env` 파일을 Compose의
`environment:`에서 명시적으로 컨테이너에 전달해야 한다 (`.env`만 두는 것으로 컨테이너에 자동 전달되지 않는다).

```yaml
# compose 설정 예시: 실제 키는 compose 파일에 쓰지 않는다.
services:
  spring:
    environment:
      MODEL_API_KEY: ${MODEL_API_KEY:?MODEL_API_KEY must be set}
```

아래 `application.yml`은 설정 키 구조 예시다. 실제 Spring 프로젝트의 설정 클래스가 읽는
프로퍼티 이름 및 환경변수 바인딩 규칙과 일치하는지 그 저장소에서도 확인해야 한다.

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
  이로써 실제 첫 요청에서 모델의 cold-start 지연이 발생하는 것을 줄인다. 다만 실제 요청 시간은
  입력·디바이스·서버 부하에 따라 달라지므로, 모든 요청이 500ms 이내임을 보장하는 것은 아니다.

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
