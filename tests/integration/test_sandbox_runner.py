"""Subprocess-backed host safety and WSB contracts; never run an installer."""

import hashlib
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(
    os.name != "nt" or not POWERSHELL, reason="Windows PowerShell host contracts"
)


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def fixture_args(tmp_path: Path) -> list[str]:
    core = tmp_path / "core.exe"
    down = tmp_path / "down.exe"
    core.write_bytes(b"NEVER EXECUTE synthetic Core")
    down.write_bytes(b"NEVER EXECUTE synthetic downstream")
    descriptor = tmp_path / "target.json"
    descriptor.write_text(
        json.dumps(
            {
                "app_dir": "PixelScopeTestEdition",
                "executable": "PixelScopeTestEdition.exe",
                "installer_app_id": "{A6C3E629-46AC-4061-841B-46F61ECD0AB3}",
                "release_revision": 1,
            }
        ),
        encoding="utf-8",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return [
        "-File",
        str(ROOT / "scripts/sandbox-runner.ps1"),
        "-PrepareOnly",
        "-CoreInstaller",
        str(core),
        "-DownstreamInstaller",
        str(down),
        "-Descriptor",
        str(descriptor),
        "-ExpectedHead",
        head,
        "-ExpectedDownstreamSha256",
        hashlib.sha256(down.read_bytes()).hexdigest(),
        "-OutputParent",
        str(tmp_path / "output"),
    ]


def test_prepare_only_stages_inert_inputs_and_isolates_case_outputs(tmp_path: Path) -> None:
    result = invoke(*fixture_args(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    runs = list((tmp_path / "output").iterdir())
    assert len(runs) == 1
    run = runs[0]
    assert {p.name for p in run.glob("*.wsb")} == {"B1.wsb", "B4.wsb", "C1.wsb"}
    for case in ("B1", "B4", "C1"):
        xml = ET.parse(run / f"{case}.wsb").getroot()
        mappings = xml.findall("MappedFolders/MappedFolder")
        assert len(mappings) == 2
        assert mappings[0].findtext("ReadOnly") == "true"
        assert Path(mappings[0].findtext("HostFolder", "")) == run / "input"
        assert mappings[1].findtext("ReadOnly") == "false"
        assert Path(mappings[1].findtext("HostFolder", "")) == run / case
        assert xml.findtext("Networking") == "Disable"
        assert xml.findtext("ClipboardRedirection") == "Disable"
        assert f"-Case {case}" in xml.findtext("LogonCommand/Command", "")
        assert not list((run / case).iterdir())  # no guest or installer execution
    config = json.loads((run / "input/config.json").read_text(encoding="utf-8-sig"))
    assert (
        config["CoreSha256"]
        == hashlib.sha256((tmp_path / "core.exe").read_bytes()).hexdigest().upper()
    )


@pytest.mark.parametrize("failure", ["hash", "head", "repository_output"])
def test_preflight_rejects_before_staging(tmp_path: Path, failure: str) -> None:
    args = fixture_args(tmp_path)
    option, value = {
        "hash": ("-ExpectedDownstreamSha256", "0" * 64),
        "head": ("-ExpectedHead", "0" * 40),
        "repository_output": ("-OutputParent", str(ROOT / "unsafe-sandbox-output")),
    }[failure]
    args[args.index(option) + 1] = value
    result = invoke(*args)
    assert result.returncode != 0
    expected = {
        "hash": "installer hash mismatch",
        "head": "HEAD mismatch",
        "repository_output": "outside the repository",
    }[failure]
    assert expected in result.stderr
    assert not (tmp_path / "output").exists()
    assert not (ROOT / "unsafe-sandbox-output").exists()


def test_guest_refuses_host_before_any_installation() -> None:
    result = invoke("-File", str(ROOT / "scripts/sandbox-guest.ps1"), "-Case", "B1")
    assert result.returncode != 0
    assert (
        "Guest isolation identity not established" in result.stderr
        or "Get-CimInstance" in result.stderr
    )


@pytest.mark.parametrize("case", ["D1", "D2", "D3", "D4", "D5", "D6", "D8", "D9"])
def test_extended_case_is_prepared_without_execution(tmp_path: Path, case: str) -> None:
    result = invoke(*fixture_args(tmp_path), "-Cases", case)
    assert result.returncode == 0, result.stdout + result.stderr
    run = next((tmp_path / "output").iterdir())
    assert [p.name for p in run.glob("*.wsb")] == [f"{case}.wsb"]
    assert not list((run / case).iterdir())


def test_upgrade_requires_separately_pinned_artifact(tmp_path: Path) -> None:
    result = invoke(*fixture_args(tmp_path), "-Cases", "D7")
    assert result.returncode != 0
    assert "separately reviewed revision 2 installer" in result.stderr
    assert not (tmp_path / "output").exists()


def test_upgrade_stages_only_matching_pinned_input(tmp_path: Path) -> None:
    upgrade = tmp_path / "upgrade.exe"
    upgrade.write_bytes(b"inert revision 2 fixture")
    args = [
        *fixture_args(tmp_path),
        "-Cases",
        "D7",
        "-UpgradeInstaller",
        str(upgrade),
        "-ExpectedUpgradeSha256",
        hashlib.sha256(upgrade.read_bytes()).hexdigest(),
    ]
    result = invoke(*args)
    assert result.returncode == 0, result.stdout + result.stderr
    run = next((tmp_path / "output").iterdir())
    assert (run / "input/upgrade-setup.exe").read_bytes() == upgrade.read_bytes()
    assert not list((run / "D7").iterdir())
