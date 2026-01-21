@echo off
cd /d "C:\Users\ishwa\Desktop\taskgrid-worklog-management-system\taskgrid-worklog-management-system\taskgrid-worklog-management-system"

"C:\Program Files\Git\bin\git.exe" status

"C:\Program Files\Git\bin\git.exe" remote add origin https://github.com/IshwariPatil1904/taskgrid-worklog-database-management-system.git

"C:\Program Files\Git\bin\git.exe" branch -M main

"C:\Program Files\Git\bin\git.exe" push -u origin main

pause
