"""Install built wheel and sdist artifacts into fresh environments and smoke-test them."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def run(command: list[str | Path], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    normalized = [str(argument) for argument in command]
    print("+", " ".join(normalized), flush=True)
    return subprocess.run(
        normalized,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def python_in(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def command_in(venv_path: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    directory = "Scripts" if os.name == "nt" else "bin"
    return venv_path / directory / f"{name}{suffix}"


def verify_artifact(artifact: Path, scratch: Path, index: int) -> None:
    environment_path = scratch / f"env-{index}"
    environment_path.parent.mkdir(parents=True, exist_ok=True)
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment_path)
    python = python_in(environment_path)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    install = run([python, "-m", "pip", "install", artifact.resolve()], scratch, env)
    print(install.stdout, end="")

    installed_location = run(
        [
            python,
            "-c",
            "from importlib.metadata import distribution; "
            "print(distribution('pixel-art-skill-toolkit').locate_file('pixel_art_skill_toolkit'))",
        ],
        scratch,
        env,
    )
    location = Path(installed_location.stdout.strip().splitlines()[-1]).resolve()
    if environment_path.resolve() not in location.parents:
        raise RuntimeError(f"Package imported outside its clean environment: {location}")

    metadata = run(
        [
            python,
            "-c",
            "from importlib.metadata import entry_points; "
            "found={entry.name: entry.value for entry in entry_points(group='console_scripts')}; "
            "required={'pixel-art-toolkit','pixel-art-render','pixel-art-gui'}; "
            "missing=required-found.keys(); "
            "assert not missing, f'missing entry points: {sorted(missing)}'; "
            "print({name:found[name] for name in sorted(required)})",
        ],
        scratch,
        env,
    )
    print(metadata.stdout, end="")

    source = scratch / f"sprite-{index}.json"
    source.write_text(
        json.dumps(
            {
                "version": "0.1",
                "canvas": {"width": 2, "height": 2, "background": None},
                "palette": {"red": "#ff0000"},
                "operations": [
                    {"op": "rect", "color": "red", "x": 0, "y": 0, "w": 1, "h": 1}
                ],
            }
        ),
        encoding="utf-8",
    )
    validate = run(
        [command_in(environment_path, "pixel-art-toolkit"), "validate", source],
        scratch,
        env,
    )
    result = json.loads(validate.stdout)
    if result != {"ok": True, "width": 2, "height": 2, "mode": "RGBA"}:
        raise RuntimeError(f"Unexpected installed validate result: {result!r}")

    output = scratch / f"sprite-{index}.png"
    render = run(
        [
            command_in(environment_path, "pixel-art-render"),
            source,
            "-o",
            output,
            "--scale",
            "3",
        ],
        scratch,
        env,
    )
    if render.stdout:
        print(render.stdout, end="")
    check_png = run(
        [
            python,
            "-c",
            "from PIL import Image; import sys; "
            "im=Image.open(sys.argv[1]); "
            "assert im.size == (6,6) and im.mode == 'RGBA'; "
            "assert im.getpixel((0,0)) == (255,0,0,255); print(im.size, im.mode)",
            output,
        ],
        scratch,
        env,
    )
    print(check_png.stdout, end="")
    print(f"Verified {artifact.name} in {environment_path}", flush=True)


def main() -> int:
    artifacts_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "dist").resolve()
    artifacts = sorted(
        [*artifacts_dir.glob("*.whl"), *artifacts_dir.glob("*.tar.gz")],
        key=lambda path: path.name,
    )
    wheels = [path for path in artifacts if path.suffix == ".whl"]
    source_distributions = [path for path in artifacts if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(source_distributions) != 1:
        raise RuntimeError(
            "Expected exactly one wheel and one .tar.gz source distribution in "
            f"{artifacts_dir}; found {len(wheels)} wheel(s) and "
            f"{len(source_distributions)} source distribution(s)."
        )

    with tempfile.TemporaryDirectory(prefix="pixel-art-package-check-") as temporary:
        scratch = Path(temporary)
        for index, artifact in enumerate([wheels[0], source_distributions[0]], start=1):
            verify_artifact(artifact, scratch, index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
