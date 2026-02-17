
git status | Out-File -Encoding utf8 git_status.log
git remote -v | Out-File -Encoding utf8 -Append git_status.log
