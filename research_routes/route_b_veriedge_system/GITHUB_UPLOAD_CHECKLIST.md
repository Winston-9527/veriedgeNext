# Route B Private GitHub Upload Checklist

This snapshot is intended for a private research repository. Complete the
mechanical checks below before the first push; the public-release section is a
future reminder and does not block private collaboration.

## Repository Hygiene

- [x] Add a root README with scope, status, directory map, and quick start.
- [x] Add README files at the main directory boundaries.
- [x] Add Python dependencies, `.gitignore`, and `.gitattributes`.
- [x] Confirm that no individual file exceeds GitHub's 100 MB hard limit.
- [x] Replace author-machine absolute paths in active PACT result metadata.
- [x] Preserve active experiments and mark PCRA and EuroSys assets as historical.
- [x] Keep generated evidence files visible instead of hiding all `results/` data.
- [ ] Confirm the GitHub repository visibility is **Private** before pushing.
- [ ] Stage `research_routes/README.md` and Route B explicitly; do not stage the
  local Route A/C directories yet.
- [ ] Invite collaborators with the minimum required repository role.

## Final Mechanical Check

Run from the project root immediately before `git add`:

```powershell
rg -n "wangt|admin-edghj|Dropbox|ProjectsWorkingSpace" research_routes/route_b_veriedge_system --glob "!GITHUB_UPLOAD_CHECKLIST.md" --glob "!**/tmp/**"
rg --files -g "*.pem" -g "*.key" -g ".env*" research_routes/route_b_veriedge_system

python research_routes/route_b_veriedge_system/shared/accountedge_runtime_and_captures/scripts/validate_raw_captures.py
python research_routes/route_b_veriedge_system/experiments/pact_offline/validate_gaussian_sampler.py
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_g16_protocol.py
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_g16_state_machine.py
python research_routes/route_b_veriedge_system/scripts/update_file_manifest.py
```

After initializing Git, verify what will be uploaded:

```powershell
git add research_routes/README.md research_routes/route_b_veriedge_system
git status --short -- research_routes
git diff --cached --name-only
git check-ignore -v research_routes/route_b_veriedge_system/experiments/pact_offline/__pycache__/*
git ls-files | Select-String "(__MACOSX|/\._|__pycache__|\.pyc$)"
git diff --cached --name-only | Select-String "research_routes/route_[ac]_"
```

If archive metadata or Python caches were already committed before the new
`.gitignore`, remove them from the Git index and review the staged diff again.

## Before Any Future Public Release

- [ ] Choose explicit software and data licenses. The current nested `LICENSE`
  is an anonymous artifact notice, not an open-source license.
- [ ] Replace redistributed literature PDFs with links unless redistribution is
  permitted.
- [ ] Review old manuscripts, reviews, hardware inventory, internal plans, and
  delivery manuals for disclosure constraints.
- [ ] Confirm capture data contains no personal information, provider secrets,
  model weights, or contractually restricted material.
- [ ] Resolve double-blind anonymity and add author/contact/citation metadata.
