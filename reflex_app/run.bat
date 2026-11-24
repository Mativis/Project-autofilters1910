@echo off
setlocal
set PATH=C:\Program Files\nodejs;%PATH%
set REACT_ROUTER_DEV_RESTARTED=true

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"
)

if "%VFCLOUD_URL%"=="" set /p VFCLOUD_URL=URL do Web App (/exec): 
if "%VFCLOUD_USUARIO%"=="" set /p VFCLOUD_USUARIO=Usuario: 
if "%VFCLOUD_SENHA%"=="" set /p VFCLOUD_SENHA=Senha: 

echo.
echo Iniciando Visualfil Reflex em http://localhost:3000
python -m reflex run
