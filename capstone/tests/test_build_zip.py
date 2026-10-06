import importlib.util
import zipfile
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"


def _load():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("build_zip", DEPLOY / "build_zip.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree(root: Path) -> Path:
    package = root / "payments_rag"
    (package / "__pycache__").mkdir(parents=True)
    (package / "sub").mkdir()
    (package / "__init__.py").write_text("x = 1\n")
    (package / "sub" / "mod.py").write_text("y = 2\n")
    (package / "__pycache__" / "mod.cpython-311.pyc").write_bytes(b"\x00")
    (package / "stale.pyc").write_bytes(b"\x00")
    (root / ".env").write_text("AZURE_OPENAI_ENDPOINT=https://x\n")
    (root / "requirements.txt").write_bytes(b"numpy==1\n")
    return package


def test_the_zip_holds_the_package_and_requirements_and_nothing_else(tmp_path: Path) -> None:
    package = _tree(tmp_path)
    out = tmp_path / "out" / "app.zip"

    names = _load().build(out, package, tmp_path / "requirements.txt")

    assert sorted(names) == [
        "payments_rag/__init__.py",
        "payments_rag/sub/mod.py",
        "requirements.txt",
    ]
    with zipfile.ZipFile(out) as archive:
        assert sorted(archive.namelist()) == sorted(names)
        assert archive.read("requirements.txt") == b"numpy==1\n"


def test_no_secret_cache_or_unrelated_file_can_end_up_in_the_zip(tmp_path: Path) -> None:
    package = _tree(tmp_path)

    names = _load().build(tmp_path / "app.zip", package, tmp_path / "requirements.txt")

    assert not any(n.endswith((".env", ".pyc")) or "__pycache__" in n for n in names)


def test_a_missing_requirements_file_is_an_error_not_a_silent_empty_deployment(
    tmp_path: Path,
) -> None:
    package = _tree(tmp_path)

    try:
        _load().build(tmp_path / "app.zip", package, tmp_path / "nope.txt")
    except FileNotFoundError as error:
        assert "requirements" in str(error)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_the_real_package_zip_contains_the_api_and_no_environment_file(tmp_path: Path) -> None:
    module = _load()

    names = module.build(tmp_path / "real.zip")

    assert "payments_rag/api.py" in names and "requirements.txt" in names
    assert not any(n.endswith(".env") or n.startswith("tests/") for n in names)
