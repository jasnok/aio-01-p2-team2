# Legal 단기 프로젝트 Docker Compose 종합 가이드

## 1. 목적

이 구성은 3일 단기 프로젝트에서 PostgreSQL/pgvector와 Redis를 Docker로 실행하고, 다른 팀원의 PC에서도 접근할 수 있도록 만든 최소 구성이다.

| 구분 | Docker PC 외부 포트 | 컨테이너 내부 포트 |
|---|---:|---:|
| PostgreSQL/pgvector | `5434` | `5432` |
| Redis | `6380` | `6379` |

현재 확인된 Docker PC의 IPv4 주소는 `192.100.200.99`이다.

외부 PC의 접속 대상은 다음과 같다.

```text
PostgreSQL: 192.100.200.99:5434
Redis:      192.100.200.99:6380
```

## 2. Compose 파일의 역할

`docker-compose.yml`은 PostgreSQL과 Redis 컨테이너의 이미지, 이름, 포트, 비밀번호, 데이터 볼륨 및 재시작 정책을 한 파일에서 관리한다.

처음 설치할 때만 사용하는 파일은 아니다. 이후에도 같은 설정을 이용해 컨테이너를 실행하거나 중지하고 재생성할 수 있다.

기본 명령은 다음과 같다.

```powershell
# 생성 및 실행
docker compose up -d

# 실행 상태 확인
docker compose ps

# 로그 확인
docker compose logs

# 중지
docker compose stop

# 다시 시작
docker compose start

# 컨테이너와 Compose 네트워크 제거
docker compose down
```

파일명은 다음 중 하나를 사용한다.

```text
compose.yml
docker-compose.yml
```

`docker_compose.yml`처럼 밑줄을 사용하면 기본 파일로 자동 인식되지 않는다. 그런 이름을 사용하려면 매번 `-f` 옵션으로 파일을 지정해야 한다.

## 3. 현재 PC와 신규 팀원의 실행 방법 차이

### 현재 PC

현재 PC에는 `docker run`으로 만든 `legal-pgvector` 컨테이너가 이미 존재한다. 따라서 Compose로 PostgreSQL까지 생성하려 하면 다음 이름이 충돌한다.

```text
legal-pgvector
```

현재 PC에서는 Redis만 생성한다.

```powershell
$env:REDIS_PASSWORD = '실제로-사용할-Redis-비밀번호'
docker compose up -d redis
```

Compose 파일의 PostgreSQL 설정에 필수 비밀번호 검증이 들어 있지만, `redis` 서비스만 지정해 실행할 때는 PostgreSQL을 생성하지 않는다.

기존 PostgreSQL 컨테이너는 그대로 사용하고 데이터 백업 없이 삭제하지 않는다.

### 신규 팀원 PC

PostgreSQL과 Redis가 모두 없는 신규 팀원은 두 비밀번호를 먼저 지정한 후 전체 서비스를 생성한다.

```powershell
$env:POSTGRES_PASSWORD = '실제로-사용할-DB-비밀번호'
$env:REDIS_PASSWORD = '실제로-사용할-Redis-비밀번호'
docker compose up -d
```

비밀번호 환경변수가 없으면 Compose가 실행을 중단한다. 이는 실수로 `change-me` 같은 기본 비밀번호를 사용하는 것을 막기 위한 설정이다.

PowerShell 창을 닫으면 위 방식으로 지정한 환경변수는 해당 세션에서 사라진다. 다시 Compose 설정을 변경하거나 컨테이너를 재생성할 때는 같은 비밀번호를 다시 설정해야 한다.

## 4. 포트 매핑

다음 PostgreSQL 설정은 Docker PC의 `5434` 포트를 컨테이너의 `5432` 포트로 전달한다.

```yaml
ports:
  - "5434:5432"
```

Redis도 같은 방식이다.

```yaml
ports:
  - "6380:6379"
```

형식은 다음과 같다.

```text
호스트 포트:컨테이너 내부 포트
```

호스트 주소를 생략한 포트 공개는 일반적으로 모든 호스트 인터페이스에 바인딩된다. 따라서 외부 PC가 Docker PC의 IPv4로 접근할 수 있다.

## 5. 볼륨 매핑

볼륨은 컨테이너 내부의 데이터 저장 폴더를 Docker가 별도로 관리하는 영구 저장 공간에 연결한다.

PostgreSQL 볼륨 설정:

```yaml
volumes:
  - legal-pgvector-data:/var/lib/postgresql/data
```

Redis 볼륨 설정:

```yaml
volumes:
  - legal-redis-data:/data
```

볼륨이 없어도 두 서버는 실행된다. 하지만 컨테이너를 삭제하면 컨테이너 내부에 저장된 데이터도 함께 사라질 수 있다.

| 작업 | 볼륨 없음 | 볼륨 있음 |
|---|---|---|
| 컨테이너 중지 및 재시작 | 데이터 유지 | 데이터 유지 |
| Docker Desktop 재시작 | 일반적으로 유지 | 유지 |
| 컨테이너 삭제 및 재생성 | 데이터 손실 가능 | 같은 볼륨을 연결하면 유지 |

단기 프로젝트에서도 임베딩 생성이나 데이터 입력을 다시 수행하는 데 시간이 들 수 있으므로 신규 컨테이너에는 볼륨을 적용하는 것이 안전하다.

다만 볼륨을 기존 컨테이너에 나중에 추가할 수는 없다. 기존 컨테이너를 볼륨 기반으로 변경하려면 다음 절차가 필요하다.

1. `pg_dump`로 기존 DB를 백업한다.
2. 기존 컨테이너를 중지하고 이름을 변경해 보관한다.
3. 볼륨이 연결된 새 컨테이너를 생성한다.
4. `pg_restore`로 데이터를 복원한다.
5. 모든 데이터가 정상인지 확인한 다음 기존 컨테이너의 삭제 여부를 결정한다.

현재 프로젝트 기간이 짧고 기존 PostgreSQL이 정상 동작한다면 급하게 재생성하지 않고 기존 컨테이너를 유지하면서 백업만 받는 방법도 현실적이다.

## 6. Redis 비밀번호

수업에서는 기본 동작을 빠르게 확인하기 위해 Redis 비밀번호를 생략했을 가능성이 크다. 인증 없는 Redis도 정상적으로 작동하지만, 포트에 접근할 수 있는 다른 PC가 임의로 데이터를 읽거나 변경할 수 있다.

이 구성은 외부 PC 접근을 허용하므로 다음 옵션을 적용한다.

```text
--requirepass
```

Compose 파일에는 비밀번호 자체를 직접 적지 않고 다음 환경변수를 참조한다.

```yaml
${REDIS_PASSWORD:?REDIS_PASSWORD must be set}
```

따라서 실제 비밀번호가 Git에 올라가는 것을 피할 수 있다.

## 7. 실행 상태 확인

현재 PC에서 Redis만 만든 후 확인한다.

```powershell
docker compose ps
docker logs legal-redis
docker port legal-redis
```

정상적인 Redis 포트 출력 예시는 다음과 같다.

```text
6379/tcp -> 0.0.0.0:6380
6379/tcp -> [::]:6380
```

Docker PC 내부에서 Redis를 확인하려면 비밀번호를 화면의 명령 인수에 직접 노출하지 않도록 다음과 같이 실행한다.

```powershell
docker exec -it legal-redis redis-cli --askpass
```

비밀번호를 입력한 후 다음을 확인한다.

```redis
PING
SET project:test hello
GET project:test
CONFIG GET appendonly
```

주요 정상 결과는 다음과 같다.

```text
PONG
OK
"hello"
appendonly
yes
```

## 8. 외부 PC 연결 확인

외부 PC의 PowerShell에서 먼저 TCP 포트를 확인한다.

```powershell
Test-NetConnection 192.100.200.99 -Port 5434
Test-NetConnection 192.100.200.99 -Port 6380
```

`TcpTestSucceeded : True`이면 해당 포트까지의 네트워크 연결이 성공한 것이다. 이 테스트는 Redis 인증까지 확인하지는 않는다.

외부 PC에 Docker가 설치되어 있다면 임시 Redis CLI 컨테이너로 인증까지 확인할 수 있다.

```powershell
docker run --rm -it redis:7 `
  redis-cli -h 192.100.200.99 -p 6380 --askpass PING
```

비밀번호를 입력한 뒤 `PONG`이 나오면 외부 네트워크 연결과 Redis 인증이 모두 정상이다.

외부 PC에 `redis-cli`가 직접 설치되어 있다면 다음 명령을 사용한다.

```powershell
redis-cli -h 192.100.200.99 -p 6380 --askpass PING
```

## 9. Windows 방화벽

Compose의 `ports`는 Docker 포트를 공개하고 컨테이너로 전달한다. Windows 방화벽 인바운드 규칙을 직접 생성하거나 관리하는 설정은 아니다.

현재 PostgreSQL은 별도 인바운드 규칙 없이 외부 PC에서 테이블 조회까지 성공했다. 이는 Docker Desktop 관련 허용 경로나 기존 방화벽 정책을 통해 연결이 이미 통과하고 있다는 뜻이다.

Redis도 먼저 다음 명령으로 확인한다.

```powershell
Test-NetConnection 192.100.200.99 -Port 6380
```

결과가 `True`이면 연결을 위해 별도 인바운드 규칙을 추가할 필요는 없다. 결과가 `False`일 때만 Docker PC의 관리자 PowerShell에서 팀원 PC의 IPv4로 범위를 제한해 허용한다.

```powershell
New-NetFirewallRule `
  -DisplayName "Legal Redis 6380" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 6380 `
  -RemoteAddress <팀원-PC의-IPv4> `
  -Profile Private `
  -Action Allow
```

좁은 허용 규칙을 추가해도 기존에 더 넓은 허용 규칙이 있으면 다른 PC의 접근이 자동으로 차단되는 것은 아니다. 보안 범위를 엄격하게 관리해야 한다면 기존 Docker 및 포트 관련 방화벽 규칙도 함께 점검해야 한다.

## 10. 데이터 삭제 관련 주의사항

다음 명령은 컨테이너와 Compose 네트워크를 제거하지만 이름 있는 볼륨은 일반적으로 유지한다.

```powershell
docker compose down
```

다음 명령은 Compose가 생성한 볼륨도 함께 삭제하므로 DB와 Redis 데이터가 사라진다.

```powershell
docker compose down -v
```

또한 기존 PostgreSQL 컨테이너에는 볼륨이 없으므로 다음 명령으로 삭제하지 않도록 주의한다.

```text
docker rm legal-pgvector
docker container prune
docker system prune
```

## 11. 최종 권장 방식

- 현재 PC에서는 기존 PostgreSQL을 그대로 유지하고 `docker compose up -d redis`로 Redis만 생성한다.
- 신규 팀원은 비밀번호 환경변수를 지정한 뒤 `docker compose up -d`로 전체 환경을 생성한다.
- 신규 PostgreSQL과 Redis에는 볼륨을 연결한다.
- Redis는 외부 PC 접근이 가능하므로 비밀번호 인증을 적용한다.
- 외부 접속은 `192.100.200.99:5434`와 `192.100.200.99:6380`을 사용한다.
- Windows 방화벽 규칙은 실제 연결 테스트가 실패할 때 추가한다.
- PostgreSQL과 Redis를 공유기 포트포워딩으로 공인 인터넷에 직접 공개하지 않는다.
- 기존 PostgreSQL은 데이터 백업 없이 삭제하지 않는다.
