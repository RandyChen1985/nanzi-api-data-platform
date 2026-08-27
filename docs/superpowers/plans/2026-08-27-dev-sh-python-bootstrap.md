# dev.sh Python 3.11 Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the data platform's local `dev.sh` startup experience with the sibling platform by printing safe environment details, automatically preparing a Python 3.11 `.venv` with uv, and providing safe daemon status/stop commands.

**Architecture:** Keep the existing script as the single startup entrypoint and preserve its port, frontend build, daemon, and log contracts. Add isolated helpers for uv discovery/bootstrap, Python version validation, safe runtime-environment summaries, uv-backed dependency synchronization, and PID/port-aware daemon control; test them through source-only shell checks and fake-command subprocesses.

**Tech Stack:** Bash, uv, Python 3.11, npm, pytest subprocess tests.

---

### Task 1: Lock the bootstrap and environment-summary contract with offline tests

**Files:**
- Modify: `tests/scripts/test_dev_sh.sh`
- Create: `tests/scripts/test_dev_sh_bootstrap.py`

- [x] **Step 1: Assert that the backend environment directory is always `.venv`**

Create both `venv/bin/python` and `.venv/bin/python` in the source-only shell test and assert that `backend_env_dir` returns the repository's `.venv` path.

- [x] **Step 2: Add a fake-command first-run subprocess test**

The test copies `dev.sh` into a temporary repository, supplies fake `curl`, `uv`, `npm`, `lsof`, and `python3` commands, and asserts that the script installs uv, runs `uv python install 3.11`, creates `.venv`, installs requirements through `uv pip`, prints the environment summary, and never prints a password.

- [x] **Step 3: Add unchanged-dependency and wrong-version rebuild cases**

Run the fake repository twice and assert that the second run calls `uv pip check` without a second install. Seed `.venv/bin/python` reporting 3.13 and assert that the script invokes `uv venv --clear --python 3.11 .venv`.

- [x] **Step 4: Run the new tests and observe the expected RED failures**

Run:

```bash
pytest tests/scripts/test_dev_sh_bootstrap.py -q
bash tests/scripts/test_dev_sh.sh
```

Expected: the new bootstrap assertions fail because the current script does not discover/install uv, does not enforce `.venv`/Python 3.11, and does not print the environment summary.

### Task 2: Implement the minimal uv/Python/environment-summary behavior

**Files:**
- Modify: `dev.sh`

- [x] **Step 1: Add fixed Python 3.11 `.venv` configuration and uv discovery**

Use `PYTHON_VERSION=3.11`, `VENV_DIR=.venv`, and `VENV_PYTHON=.venv/bin/python`; discover uv from PATH or common user install paths and install it via curl/wget only when absent.

- [x] **Step 2: Prepare and validate `.venv`**

Use `uv python install 3.11`, create or safely clear/recreate a non-symlink `.venv` with `uv venv --python 3.11`, and fail closed for symlink or post-create version mismatch.

- [x] **Step 3: Print non-sensitive runtime configuration**

Print uv/Python/venv/index details plus effective MySQL and Redis host/port/database values. Read only non-sensitive `.env` keys and preserve the current default port `8000`.

- [x] **Step 4: Synchronize dependencies with uv**

Use `uv pip install --python .venv/bin/python --default-index ... -r requirements.txt` when the requirements hash changes or FastAPI/Uvicorn cannot import; otherwise run `uv pip check` and retain the import check.

### Task 3: Verify the integrated script contract

**Files:**
- Modify: `README.md`

- [x] **Step 1: Update the local-development description**

Document automatic uv installation, Python 3.11 `.venv` preparation, safe summary output, `PYPI_INDEX_URL` with `PIP_INDEX_URL` compatibility, and the fact that passwords are not printed.

- [x] **Step 2: Run focused validation**

Run:

```bash
bash -n dev.sh
bash tests/scripts/test_dev_sh.sh
PYTHONPATH=. venv/bin/python -m pytest tests/scripts/test_dev_sh_bootstrap.py -q -p no:warnings
git diff --check -- dev.sh README.md tests/scripts/test_dev_sh.sh tests/scripts/test_dev_sh_bootstrap.py
```

Expected: syntax and focused tests pass; no real uv download, npm install, database connection, Redis connection, or service startup is claimed by these tests.

### Task 4: Add safe daemon status and stop commands

**Files:**
- Modify: `dev.sh`
- Modify: `stop-dev.sh`
- Modify: `tests/scripts/test_dev_sh.sh`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `.gitignore`

- [x] **Step 1: Add managed-service detection and lifecycle commands**

Record the daemon PID in `.dev-server.pid`, add `./dev.sh status` and `./dev.sh stop`, use the configured `.env` port, recognize only matching Uvicorn processes, refuse to stop unrelated listeners, and preserve `stop-dev.sh` as a compatibility wrapper.

- [x] **Step 2: Cover status, graceful stop, force-stop, and unrelated-process refusal**

Extend the source-only shell test with managed and foreign-process cases while filtering stale listener PIDs.

- [x] **Step 3: Document the daemon controls**

Update Chinese and English local-development sections with status/stop commands, shared port configuration, and the safety behavior.
