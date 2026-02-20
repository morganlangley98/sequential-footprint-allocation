# Sequential Footprint Allocation (No Double Counting)

## What this is
This script solves a **classic problem that arises in large infrastructure project impact calculations**: you have a **master footprint** (the total project area) and a set of **component layers** (often delivered as many shapefiles), and you need to calculate how much of the master footprint is attributable to each component **without double counting overlaps**.

It does this by **sequentially allocating** space:
1. Intersect a component with the *remaining* master footprint.
2. Compute the area allocated to that component.
3. Remove that allocated geometry from the master footprint so later components can’t claim it.

Output is a simple table: **Layer name → allocated area (ha)**.

---

## Inputs
1. **Components root folder**  
   A folder containing many shapefiles (`.shp`), potentially nested. Common pattern: *one folder per layer*, with the shapefile inside.

2. **Master footprint layer**  
   A shapefile (or any vector supported by GeoPandas/Fiona) representing the total footprint available for allocation.

---

## Output
A pandas dataframe with:

- `Layer` — derived from either the shapefile’s parent folder name (default) or filename
- `area_ha` — allocated area in hectares, **rounded to 1 decimal place**

You can also save it as CSV.

---

## How allocation works (important)
- **Order matters.** If component A overlaps component B, whichever is processed first gets the overlap.
- By default, shapefiles are processed **alphabetically by path** for reproducibility.
- If you need a priority order (e.g. “permanent works before temporary works”), adjust the sort logic.

---

## CRS and area correctness
- All area calculations are done in a **projected CRS**.
- If the master is in a geographic CRS (lat/long), the script reprojects to **EPSG:6933 (World Cylindrical Equal Area)** to ensure area is meaningful.
- Components are reprojected to match the master CRS before overlay operations.

---

## Requirements
- Python 3.9+ recommended
- `geopandas`
- `shapely`
- `pandas`

Example install:

```bash
pip install geopandas shapely pandas
```

## Usage
Edit the paths at the bottom of the intersect script:

```python
components_root = r"/path/to/components_root_folder"
master_path = r"/path/to/master_footprint.shp"

df = allocate_non_overlapping_areas(
    components_root=components_root,
    master_path=master_path,
    layer_name_from="parent_folder",  # or "filename"
    sort_layers=True
)

print(df)
df.to_csv("allocated_areas.csv", index=False)
```

## Layer naming
`layer_name_from` controls how `Layer` is populated:

- `"parent_folder"` (default): uses the shapefile’s parent directory name  
  Useful when you have `components/<LayerName>/<LayerName>.shp`

- `"filename"`: uses the shapefile name without extension

If multiple shapefiles resolve to the same `Layer` name, results are **summed** into one row.

---

## Notes / assumptions
- Geometries are run through `make_valid()` to handle common topology issues.
- Master footprint is dissolved into a single geometry for clean allocation.
- If a component does not intersect the remaining master, its allocated area is `0.0`.
- The script stops early if the master footprint becomes fully exhausted.

---

## Typical use cases
- Construction footprint breakdown (roads, laydown areas, buildings, utilities)
- Environmental impact accounting (habitat types, landcover classes) within a project boundary
- Carbon/land-use accounting where overlaps must not be counted twice