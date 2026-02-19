@echo off
echo Killing git processes...
taskkill /F /IM git.exe >nul 2>&1

echo Removing .git directory...
if exist .git (
    powershell -Command "Remove-Item -Path .git -Recurse -Force"
)

echo Re-initializing git...
git init
git remote add origin https://github.com/hm-damul/template-factory.git
git config user.email "auto-deploy@example.com"
git config user.name "AutoDeploy"

echo Adding files...
git add .

echo Committing...
git commit -m "Deploy_v2"

echo Pushing to remote...
git branch -M main
git push -u origin main --force

echo Done.
