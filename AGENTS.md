# AGENTS.md

This file provides guidance to AI coding agents (e.g. OpenAI Codex, Claude Code) when working with code in this repository.

## Status

Source code exists for the serving app (core), the prediction endpoint, and the training script.
Commands:

```bash
.venv/bin/python -m uvicorn app.main:app --reload   # run the API (from repo root)
.venv/bin/python -m pytest                          # tests
.venv/bin/python -m training.train --help           # training/prepare CLI
```

There is no lint/format command configured yet (Black + isort + Ruff are the agreed tools). There is no build CI yet.

## Project: OvE AI model server

Internal-only FastAPI server for the OvE (AI 의사결정 기반 실시간 투자 보조 서비스) project. Spring Boot sends recent candles to `POST /api/v1/predict`; the model returns BUY / HOLD / SELL probabilities and a confidence value. The server is never public and checks the internal `X-API-KEY` header (separate from user-facing `ove_` API keys). Real trading is out of scope.

Source of truth is the Notion "OvE" project page (project plan, 팀 컨벤션, API 명세서).

## Folder structure

- `app/`: serving code
  - `app/main.py`: app creation, `/health`, router auto-registration
  - `app/api/`: one module per feature; each exposes `router = APIRouter(...)` and is registered automatically. **Do not edit `app/main.py` to add a feature** — it is the shared file every branch would conflict on.
  - `app/core/`: config, logging, lifespan, exceptions/handlers, dependency injection, model loading
  - `app/dto/`: pydantic request/response models
  - `app/services/`: feature logic
- `common/`: the contract shared by training and serving (state format, question schema, labels)
- `training/`: training code (data loading, state building, time-ordered split, training, ONNX export), `.py` only. Run as a module from the repo root (`python -m training.train`) so `common` imports resolve.
- `notebooks/`: experiments only, not for production logic
- `models/`: local checkpoints (`models/Laya`, `models/Laya-finance`), ignored by Git (model files live in S3)
- `data/`: local datasets, raw files ignored by Git (only `meta.json` is tracked)
- `outputs/`: training artifacts, weights/checkpoints ignored by Git (config JSON is tracked)
- `tests/`: tests

## Path ownership per branch

PRs must not touch paths owned by another feature branch. Merge order is `feature/core` → `feature/prediction` / `feature/training`.

| Branch | Owned paths |
| --- | --- |
| `feature/core` | `app/main.py`, `app/api/model_status.py`, `app/core/**`, `app/dto/**/__init__.py`, `common/**`, `tests/conftest.py`, `tests/test_contract.py`, `tests/test_health.py`, `.gitignore`, `README.md`, `AGENTS.md`, `requirements.txt` |
| `feature/prediction` | `app/api/prediction.py`, `app/services/**`, `app/dto/request/stock_data.py`, `app/dto/response/stock_decision.py`, `tests/test_prediction*.py` |
| `feature/training` | `training/**`, `data/*/meta.json`, `outputs/**/*.json`, `tests/test_training*.py` |

Never delete `app/`, `README.md` or `requirements.txt` on a feature branch. A branch that removes shared files cannot be merged back without breaking the others.

## Python rules

- PEP 8, Black + isort + Ruff. Add type hints.
- Training code lives in `.py` files. Notebooks are for experiments only.
- Split train/validation/test in time order to avoid leakage. Fit scalers on the training split only.
- Never commit model files, datasets, or secrets (`X-API-KEY` value, `MODEL_API_KEY`).

## Shared contract

`common/contract.py` defines `NUM_CANDLES`, `LABELS`, `QUESTIONS` and `build_state()`. Training data and serving inference must produce byte-identical state strings, so both sides import this module; never copy the format into a second place. Changing these values invalidates existing checkpoints — retrain instead of patching one side.

`tests/test_contract.py` pins the state layout. Run it before and after touching `common/contract.py`.

## Git workflow

- Branches: `main` (deploy, no direct push), `dev` (integration), `feature/{domainName}-{detail}`, `fix/{domainName}-{detail}`. Open PRs against `dev`. Each PR needs at least one review before merge.
- Commit format: `type: 작업 내용`. Types: feat, fix, docs, style, refactor, test, chore, design, comment, rename, remove, !HOTFIX.
- PR title format: `[타입] #이슈번호 제목`. Create a GitHub issue before starting work. Labels: FE / BE / AI / APP / 3D / DOC.

## PR review with Claude

- Claude runs only when someone mentions `@claude` in a PR comment, review comment, or review (`.github/workflows/claude-review.yml`). There is no automatic review on PR open or push.
- Each run uses the user's Claude subscription quota. Call it only when needed.
- The bot review is for reference only. It does not replace the one teammate review required before merge.
