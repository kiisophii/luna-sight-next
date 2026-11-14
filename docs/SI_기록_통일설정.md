# AI(SI) 사용 기록 통일 설정 — Ginkgo Orbit

> 대회 규칙: AI(공식 용어 SI) 사용 내역 제출이 필수다. 6명이 각자 다른 AI를 써도 기록이 **같은 형식**으로 쌓이게, 09:00 전에 각자 AI에 아래 설정을 넣어 둔다.
> 기록은 제출용이라 **영어**로 쓴다(번역 시간 절약).

## 1. 모두 같은 기록 형식 (`docs/SI_USAGE.md`)

```
| Time (KST) | Member | Role | Tool & model | What we asked | Output (file / commit) | How a human checked it | Changed by human? |
|---|---|---|---|---|---|---|---|
```

- **Time**: `2026-11-14 10:35` 형식
- **Role**: 1 Lead/Submission · 2 Data · 3 3D/Map · 4 Compare UI · 5 Story/Video · 6 Verify/Korea
- **How a human checked it**: AI가 아니라 **사람이** 채운다. 예: "ran it, numbers match Horizons", "read and edited", "compared with PGDA map". AI는 `TO CHECK`로 비워 둔다.
- 큰 작업 1개 = 1줄. 사소한 질문은 적지 않아도 된다(코드·데이터·문장·그림이 결과물에 들어간 것만).

## 2. 각자 AI에 붙여 넣을 설정 문장 (복사용)

아래를 **자기 AI의 '지침/커스텀 지침/프로젝트 지침' 칸**에 그대로 넣는다. 그런 칸이 없으면 대화 첫 메시지로 넣는다. 대괄호 안만 자기 것으로 바꾼다.

```
You are helping team Ginkgo Orbit in NASA Space Apps Challenge 2026, challenge "Lunar Landing Site Navigator".
I am [이름 영문], role [번호 + 역할명].

Logging rule (required by the competition):
Whenever your answer produces code, data, text, or an image that may go into our project,
end your answer with exactly one log line in this format, inside a code block labelled SI-LOG:

| YYYY-MM-DD HH:MM (KST) | [이름 영문] | [역할 번호] | [tool and model name] | <one-sentence summary of what I asked> | <files or output you produced> | TO CHECK | TO CHECK |

Rules for the line: English, one line, no line breaks inside cells, do not invent a verification;
leave the last two cells as "TO CHECK" for me to fill in.
Also: always state the data source (with URL) for any number or dataset you use, and say "unverified" when you are not sure.
```

## 3. 쓰는 도구별 넣는 곳

| 도구 | 넣는 곳 |
|---|---|
| ChatGPT | 프로젝트를 하나 만들고 프로젝트 지침에 넣기(또는 맞춤 설정의 지침) |
| Claude (claude.ai) | 프로젝트를 만들고 프로젝트 지침에 넣기 |
| Gemini | Gem을 하나 만들어 지침에 넣기 |
| Claude Code · Cursor 등 코드 도구 | 09:00에 저장소에 `CLAUDE.md`·`AGENTS.md`를 두고 아래 4번 문장을 넣으면, AI가 `docs/SI_USAGE.md`에 **직접 한 줄씩 추가**한다 |

메뉴 이름은 도구 버전마다 조금 다를 수 있다. 칸을 못 찾으면 대화 첫 메시지에 붙여 넣으면 된다.

## 4. 코드 도구용(저장소에 넣을 문장)

```
## SI usage log (required)
After any task that changes files in this repo, append one row to docs/SI_USAGE.md:
| YYYY-MM-DD HH:MM (KST) | <member> | <role> | <tool/model> | <what was asked> | <files changed> | TO CHECK | TO CHECK |
Never edit or delete existing rows. Leave the last two cells for the human.
```

## 5. 모으는 방법
- 각자 SI-LOG 줄을 `docs/SI_USAGE.md` 맨 아래에 붙인다(자기 브랜치에서).
- **매 체크인 시간(11–12, 16–18, 19–22, 일 06–12, 15–20)마다** `TO CHECK` 칸을 채운다. 마지막 날 몰아서 하면 기억이 안 난다.
- 팀장(김동주) 또는 1번 역할이 일요일 20시에 최종 정리한다.
