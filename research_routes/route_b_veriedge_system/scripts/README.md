# Repository Maintenance Scripts

Run these utilities from any working directory.

```powershell
python research_routes/route_b_veriedge_system/scripts/update_file_manifest.py
```

`update_file_manifest.py` rebuilds the route-level SHA-256 manifest while
excluding files that should not be uploaded, such as Python caches, virtual
environments, archive metadata, and temporary validation outputs.
