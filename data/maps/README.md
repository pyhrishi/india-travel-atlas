# Global administrative map data

Country-level first administrative divisions are built from the **geoBoundaries gbOpen** dataset.

- API documentation: https://www.geoboundaries.org/api.html
- Release: `gbOpen`
- Requested layer: `ADM1` (first-level administrative divisions)
- Output: one normalized GeoJSON FeatureCollection per ISO-3166-1 alpha-2 country code
- Index: `index.json`
- Attribution: geoBoundaries (William & Mary geoLab), with original source and licence retained in each country's metadata
- Licence: gbOpen is CC-BY 4.0 compatible; the source licence varies by country and is stored per map

The M49 entity registry remains the source of the atlas country/area list. A map is not marked ready until the downloaded boundary layer passes identity, feature-count, naming, geometry and coordinate validation. The map index does not imply sovereignty, political affiliation or a position on disputed borders.

## Build a batch

```sh
python3 tools/build_global_maps.py --iso2 BD,BT,LK,MV,MM --dry-run
python3 tools/build_global_maps.py --iso2 BD,BT,LK,MV,MM
python3 tools/bump_sw.py
```

Batches are limited to ten countries. A failed country aborts the batch before its own output file is replaced. The GitHub workflow runs manually and commits only validated map files.
