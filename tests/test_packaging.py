from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_setuptools_discovers_the_school_ai_src_package() -> None:
    configuration = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())

    assert configuration["tool"]["setuptools"]["package-dir"] == {"": "src"}
    assert configuration["tool"]["setuptools"]["packages"]["find"]["where"] == [
        "src"
    ]
    assert (PROJECT_ROOT / "src" / "school_ai" / "__init__.py").is_file()
    assert (PROJECT_ROOT / "requirements.txt").read_text().strip() == "."
