# Deploy Master Syllabus to GitHub
# Copies files from Projects folder to repo, commits, and pushes

$projectsPath = "c:\Users\brons\Projects"
$repoPath = "c:\Users\brons\master-syllabus-repo"

Write-Host "Copying files to repo..." -ForegroundColor Cyan
Copy-Item "$projectsPath\index.html" "$repoPath\" -Force
Copy-Item "$projectsPath\Master_Syllabus_Spring_2026.html" "$repoPath\" -Force

Write-Host "Checking git status..." -ForegroundColor Cyan
Set-Location $repoPath
git status

Write-Host "`nFiles copied. Review changes above." -ForegroundColor Yellow
Write-Host "To commit and push, run:" -ForegroundColor Yellow
Write-Host "  cd $repoPath" -ForegroundColor White
Write-Host "  git add index.html Master_Syllabus_Spring_2026.html" -ForegroundColor White
Write-Host "  git commit -m 'Your commit message'" -ForegroundColor White
Write-Host "  git push origin main" -ForegroundColor White
