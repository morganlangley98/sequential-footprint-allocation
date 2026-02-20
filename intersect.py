import os
from pathlib import Path
import geopandas as gpd
import pandas as pd


def _read_any_vector(path: str) -> gpd.GeoDataFrame:
    """Read a shapefile (or other vector) and keep only valid geometries."""
    gdf = gpd.read_file(path)
    gdf = gdf[gdf.geometry.notnull()].copy()
    if len(gdf) == 0:
        return gdf
    # Fix common invalid geometry issues (Shapely 2+)
    gdf["geometry"] = gdf.geometry.make_valid()
    gdf = gdf[gdf.geometry.notnull()].copy()
    return gdf


def _find_shapefiles(root_folder: str) -> list[str]:
    """Recursively find .shp files under root_folder."""
    root = Path(root_folder)
    return [str(p) for p in root.rglob("*.shp")]


def _ensure_projected_equal_area(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Ensure gdf is in a projected CRS suitable for area calculation.
    Strategy:
      - If already projected: keep it.
      - If geographic: reproject to World Cylindrical Equal Area (EPSG:6933).
    """
    if gdf.crs is None:
        raise ValueError("Input layer has no CRS defined. Please define CRS before running.")

    if gdf.crs.is_geographic:
        return gdf.to_crs("EPSG:5551")  # equal-area global projection
    return gdf


def allocate_non_overlapping_areas(
    components_root: str,
    master_path: str,
    layer_name_from: str = "parent_folder",  # or "filename"
    sort_layers: bool = True
) -> pd.DataFrame:
    """
    Sequentially allocate master footprint area to component layers without double counting.

    Parameters
    ----------
    components_root : str
        Folder containing component shapefiles (recursive search).
    master_path : str
        Path to master footprint shapefile (or any vector supported by fiona).
    layer_name_from : str
        'parent_folder' -> use shapefile parent directory name as Layer name
        'filename'      -> use shapefile stem name as Layer name
    sort_layers : bool
        If True, process layers in alphabetical order for reproducibility.

    Returns
    -------
    pd.DataFrame with columns: ['Layer', 'area_ha']
    """

    # ---- read master ----
    master = _read_any_vector(master_path)
    if len(master) == 0:
        raise ValueError("Master footprint is empty.")

    master = _ensure_projected_equal_area(master)
    # Dissolve master into one geometry to simplify allocation
    master_union = master.union_all()

    # ---- find components ----
    shp_paths = _find_shapefiles(components_root)
    if sort_layers:
        shp_paths = sorted(shp_paths)

    results = []

    # ---- sequential allocation ----
    for shp in shp_paths:
        # determine layer name
        p = Path(shp)
        if layer_name_from == "filename":
            layer_name = p.stem
        else:  # parent_folder
            layer_name = p.parent.name

        comp = _read_any_vector(shp)
        if len(comp) == 0:
            results.append({"Layer": layer_name, "area_ha": 0.0})
            continue

        # Reproject components to master's CRS for correct overlay & area
        if comp.crs is None:
            raise ValueError(f"Component has no CRS: {shp}")
        if comp.crs != master.crs:
            comp = comp.to_crs(master.crs)

        comp = _ensure_projected_equal_area(comp)
        comp_union = comp.union_all()

        # Intersect component with remaining master
        allocated_geom = comp_union.intersection(master_union)

        if allocated_geom.is_empty:
            allocated_area_ha = 0.0
        else:
            # area in m² -> ha
            allocated_area_ha = allocated_geom.area / 10_000.0
            # subtract allocated from master so next layers can't double count
            master_union = master_union.difference(allocated_geom)

        results.append({"Layer": layer_name, "area_ha": float(allocated_area_ha)})

        # Optional: if master is fully exhausted, break early
        if master_union.is_empty:
            break

    df = pd.DataFrame(results)

    # If the same Layer name appears multiple times (e.g., multiple shapefiles per folder),
    # aggregate to keep the requested final format.
    df = df.groupby("Layer", as_index=False)["area_ha"].sum()

    df["area_ha"] = df["area_ha"].round(1)

    return df


if __name__ == "__main__":
    components_root = r"/path/to/components_root_folder"
    master_path = r"/path/to/master_footprint.shp"

    df = allocate_non_overlapping_areas(
        components_root=components_root,
        master_path=master_path,
        layer_name_from="parent_folder",
        sort_layers=True
    )

    print(df.sort_values("area_ha", ascending=False))
    df.to_csv(r"allocated_areas.csv", index=False)