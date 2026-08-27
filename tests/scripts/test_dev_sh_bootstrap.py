"""Offline regression tests for dev.sh's local Python bootstrap contract."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_fake_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    (repo / "frontend").mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()
    shutil.copy(ROOT / "dev.sh", repo / "dev.sh")
    (repo / "requirements.txt").write_text("example-package==1.0\n", encoding="utf-8")
    (repo / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    (repo / ".env").write_text(
        "MYSQL_HOST=mysql.example.internal\n"
        "MYSQL_PORT=3307\n"
        "MYSQL_DB=nanzi_test\n"
        "MYSQL_PASSWORD=do-not-print-this\n"
        "REDIS_HOST=redis.example.internal\n"
        "REDIS_PORT=6380\n"
        "REDIS_DB=4\n",
        encoding="utf-8",
    )
    return repo, fake_bin, home


def _install_fake_commands(fake_bin: Path, *, uv_in_path: bool) -> None:
    uv_source = fake_bin / "uv-source"
    _write_executable(
        uv_source,
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$HOME/uv.log"

case "${1:-}" in
  --version)
    printf '%s\n' 'uv 0.9.15'
    ;;
  python)
    ;;
  venv)
    target=""
    clear=false
    for arg in "$@"; do
      if [ "$arg" = "--clear" ]; then
        clear=true
      elif [ "$arg" != "venv" ] && [ "$arg" != "--python" ] && [ "$arg" != "3.11" ] && [ "${arg#-}" = "$arg" ]; then
        target="$arg"
      fi
    done
    if [ "$clear" = true ]; then
      rm -rf "$target"
    fi
    mkdir -p "$target/bin"
    printf '%s\n' '#!/bin/sh' \
      'if [ "${1:-}" = "-c" ]; then printf "%s\\n" "3.11"; fi' \
      'exit 0' > "$target/bin/python"
    chmod +x "$target/bin/python"
    ;;
  pip)
    ;;
  *)
    exit 1
    ;;
esac
""",
    )
    if uv_in_path:
        shutil.copy(uv_source, fake_bin / "uv")
        (fake_bin / "uv").chmod(0o755)

    _write_executable(
        fake_bin / "curl",
        """#!/bin/sh
set -eu
printf '%s\n' curl >> "$HOME/installer.log"
printf '%s\n' 'mkdir -p "$HOME/.local/bin"' \
  'cp "$FAKE_UV_SOURCE" "$HOME/.local/bin/uv"' \
  'chmod +x "$HOME/.local/bin/uv"'
""",
    )
    _write_executable(
        fake_bin / "npm",
        """#!/bin/sh
printf '%s\n' "$*" >> "$HOME/npm.log"
exit 0
""",
    )
    _write_executable(fake_bin / "lsof", """#!/bin/sh
exit 1
""")
    _write_executable(fake_bin / "python3", """#!/bin/sh
exit 0
""")


def _run_dev(repo: Path, fake_bin: Path, home: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYPI_INDEX_URL", None)
    environment.pop("PIP_INDEX_URL", None)
    environment.update(
        {
            "HOME": str(home),
            "FAKE_UV_SOURCE": str(fake_bin / "uv-source"),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
        }
    )
    return subprocess.run(
        ["bash", str(repo / "dev.sh")],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_dev_sh_bootstraps_uv_python_requirements_and_safe_summary(tmp_path: Path):
    repo, fake_bin, home = _prepare_fake_repo(tmp_path)
    _install_fake_commands(fake_bin, uv_in_path=False)

    result = _run_dev(repo, fake_bin, home)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert (home / "installer.log").read_text(encoding="utf-8").strip() == "curl"
    uv_log = (home / "uv.log").read_text(encoding="utf-8")
    assert "python install 3.11" in uv_log
    assert any(line.startswith("venv --python 3.11 ") and line.endswith("/.venv") for line in uv_log.splitlines())
    assert "pip install" in uv_log and "requirements.txt" in uv_log
    assert (repo / ".venv" / ".requirements.hash").is_file()
    assert "启动环境信息" in output
    assert "uv: 未安装（启动时自动安装）" in output
    assert "Python 目标版本: 3.11" in output
    assert "虚拟环境: .venv" in output
    assert "PyPI 镜像: https://pypi.tuna.tsinghua.edu.cn/simple" in output
    assert "DATABASE_TYPE: mysql (effective: mysql)" in output
    assert "数据库地址: mysql.example.internal:3307/nanzi_test" in output
    assert "Redis 地址: redis.example.internal:6380/4" in output
    assert "do-not-print-this" not in output
    assert "[1/4]" in output


def test_dev_sh_checks_instead_of_reinstalling_unchanged_requirements(tmp_path: Path):
    repo, fake_bin, home = _prepare_fake_repo(tmp_path)
    _install_fake_commands(fake_bin, uv_in_path=True)

    first_result = _run_dev(repo, fake_bin, home)
    second_result = _run_dev(repo, fake_bin, home)

    assert first_result.returncode == 0, first_result.stdout + first_result.stderr
    assert second_result.returncode == 0, second_result.stdout + second_result.stderr
    log_lines = (home / "uv.log").read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("pip install") for line in log_lines) == 1
    assert any(line.startswith("pip check") for line in log_lines)
    assert "后端依赖未变化且环境检查通过，跳过安装" in second_result.stdout + second_result.stderr


def test_dev_sh_rebuilds_existing_non_311_venv(tmp_path: Path):
    repo, fake_bin, home = _prepare_fake_repo(tmp_path)
    _install_fake_commands(fake_bin, uv_in_path=True)
    old_python = repo / ".venv" / "bin" / "python"
    old_python.parent.mkdir(parents=True)
    _write_executable(
        old_python,
        """#!/bin/sh
if [ "${1:-}" = "-c" ]; then printf '%s\\n' '3.13'; fi
exit 0
""",
    )

    result = _run_dev(repo, fake_bin, home)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    uv_log = (home / "uv.log").read_text(encoding="utf-8")
    assert any(
        line.startswith("venv --clear --python 3.11 ") and line.endswith("/.venv")
        for line in uv_log.splitlines()
    )
    assert "3.11" in old_python.read_text(encoding="utf-8")
