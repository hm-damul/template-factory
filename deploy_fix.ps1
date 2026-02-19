$ErrorActionPreference = "Continue"
Write-Host "Killing git processes..."
Stop-Process -Name "git" -Force -ErrorAction SilentlyContinue

Write-Host "Removing .git directory..."
if (Test-Path .git) { Remove-Item -Path .git -Recurse -Force }

Write-Host "Re-initializing git..."
git init
git remote add origin https://github.com/hm-damul/template-factory.git
git config user.email "auto-deploy@example.com"
git config user.name "AutoDeploy"

Write-Host "Adding files..."
for ($i=0; $i -lt 5; $i++) {
    Write-Host "Attempt $i to add files..."
    if (Test-Path .git/index.lock) { 
        Write-Host "Removing index.lock..."
        Remove-Item .git/index.lock -Force 
    }
    
    git add .
    if ($LASTEXITCODE -eq 0) { 
        Write-Host "Files added successfully."
        break 
    }
    Start-Sleep -Seconds 2
}

Write-Host "Committing..."
git commit -m "Deploy_v2"

Write-Host "Pushing to remote..."
git branch -M main
git push -u origin main --force

Write-Host "Done."
