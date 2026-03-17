from pathlib import Path

from tarapath_core.catalog import StarCatalog


def test_catalog_loads_and_filters(tmp_path: Path):
    data_dir = Path("data/star_catalog")
    csv_path = data_dir / "hyg_stars.csv"
    catalog = StarCatalog(csv_path)

    df = catalog.dataframe
    assert not df.empty
    for col in ["hip", "ra", "dec", "mag", "name"]:
        assert col in df.columns

