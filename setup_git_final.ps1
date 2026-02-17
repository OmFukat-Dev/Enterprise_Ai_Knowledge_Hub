
Start-Transcript -Path setup.log
git add .
git commit -m "Initial clean commit"
git branch -M main
git remote add origin https://github.com/OmFukat-Dev/Enterprise_Ai_Knowledge_Hub.git
git push -u origin main
Stop-Transcript
