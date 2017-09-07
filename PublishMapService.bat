@echo off
cd /D %~dp0
set py=C:\Python27\ArcGIS10.2\python.exe
for %%a in ( 10.2 10.3 10.4 10.5) do (
	if EXIST C:\Python27\ArcGIS%%a\python.exe SET py=C:\Python27\ArcGIS%%a\python.exe
)
echo %py%
set pypgm=%~dp0\PublishMapService.py
"%PY%" "%PYPGM%" %*