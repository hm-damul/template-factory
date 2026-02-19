$ErrorActionPreference = "Stop"
Write-Host "Killing git processes..."
Stop-Process -Name "git" -Force -ErrorAction SilentlyContinue

Write-Host "Removing .git directory..."
if (Test-Path .git) { Remove-Item -Path .git -Recurse -Force }

Write-Host "Re-initializing git..."
git init
git remote add origin https://github.com/hm-damul/template-factory.git
git config user.email "auto-deploy@example.com"
git config user.name "AutoDeploy"

# Use a custom index file to avoid locking issues with IDE/background processes
$env:GIT_INDEX_FILE = ".git/index_custom"

Write-Host "Adding files using custom index..."
git add .

Write-Host "Committing..."
git commit -m "Deploy_v2"

Write-Host "Pushing to remote..."
git branch -M main
git push -u origin main --force

Write-Host "Done."
