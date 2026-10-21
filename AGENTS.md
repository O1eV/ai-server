# AGENTS.md

This file provides guidance to AI coding agents (e.g. OpenAI Codex, Claude Code) when working with code in this repository.

## Status

No source code yet. There are no build, lint, or test commands to run yet. When code is added, update this file with the real commands.

## Project: OvE AI model server

Internal-only FastAPI server for the OvE (AI 의사결정 기반 실시간 투자 보조 서비스) project. Spring Boot sends recent candles to `POST /predict`; the model returns BUY / HOLD / SELL probabilities and a confidence value. The server is never public and checks the internal `X-API-KEY` header (separate from user-facing `ove_` API keys). Real trading is out of scope.

Source of truth is the Notion "OvE" project page (project plan, 팀 컨벤션, API 명세서).

## Folder structure

- `app/`: serving code (FastAPI app, /predict, /health)
- `training/`: training code (data loading, features, time-ordered split, training, ONNX export), `.py` only
- `notebooks/`: experiments only, not for production logic
- `models/`: local model files, ignored by Git (model files live in S3)
- `data/`: local datasets, ignored by Git
- `tests/`: tests

## Python rules

- PEP 8, Black + isort + Ruff. Add type hints.
- Training code lives in `.py` files. Notebooks are for experiments only.
- Split train/validation/test in time order to avoid leakage. Fit scalers on the training split only.
- Never commit model files, datasets, or secrets (`X-API-KEY` value, `MODEL_API_KEY`).

## Git workflow

- Branches: `main` (deploy, no direct push), `dev` (integration), `feature/{domainName}-{detail}`, `fix/{domainName}-{detail}`. Open PRs against `dev`. Each PR needs at least one review before merge.
- Commit format: `type: 작업 내용`. Types: feat, fix, docs, style, refactor, test, chore, design, comment, rename, remove, !HOTFIX.
- PR title format: `[타입] #이슈번호 제목`. Create a GitHub issue before starting work. Labels: FE / BE / AI / APP / 3D / DOC.

## PR review with Claude

- Claude runs only when someone mentions `@claude` in a PR comment, review comment, or review (`.github/workflows/claude-review.yml`). There is no automatic review on PR open or push.
- Each run uses the user's Claude subscription quota. Call it only when needed.
- The bot review is for reference only. It does not replace the one teammate review required before merge.
- This repository has no build CI yet.
