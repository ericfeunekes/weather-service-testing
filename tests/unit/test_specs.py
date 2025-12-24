import sys
from pathlib import Path

# Ensure src is importable without installation
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))

from wxbench import specs


def test_iter_paths_exposes_expected_templates():
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "msc_geomet_sample.json"
    spec = specs.load_spec(fixture_path)

    documented_paths = set(specs.iter_paths(spec))

    assert {
        "/",
        "/collections",
        "/collections/ahccd-annual",
        "/collections/ahccd-annual/items",
        "/collections/ahccd-annual/items/{featureId}",
    } <= documented_paths
