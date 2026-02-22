@echo off
echo Pushing to Git...
git push --set-upstream origin main
if %errorlevel% neq 0 (
    echo Git push failed. Trying to pull first...
    git pull origin main --rebase
    git push --set-upstream origin main
)

echo Running WP Link Update...
python update_wp_link.py

echo Done.
