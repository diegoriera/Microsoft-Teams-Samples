# PowerShell helper to enable the commit hooks for this repository
# Run this from the repository root (where .githooks exists)

Write-Host "Setting repository hooks path to .githooks"
git config core.hooksPath .githooks
Write-Host "Done. Hooks will run for this repo. You can commit as usual."

Write-Host "Tip: to block commits instead of auto-redacting, set environment variable BLOCK_ON_SECRET=1 before committing."
