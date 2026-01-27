@echo off
setlocal
cd /d "%~dp0"
echo Démarrage du serveur LeTempsEstCompté...
echo L'application sera disponible à l'adresse : http://127.0.0.1:5000
echo.

:: Lancer le serveur en arrière-plan
start /b cmd /c ".\venv\Scripts\python.exe app.py"

:: Attendre que le serveur soit prêt (2 secondes)
timeout /t 2 /nobreak > nul

:: Ouvrir l'application dans Edge en mode "App" (fenêtre dédiée)
:: Si Edge n'est pas utilisé, vous pouvez remplacer par chrome.exe
start msedge --app=http://127.0.0.1:5000

echo Application lancée ! Vous pouvez fermer cette fenêtre, mais ne fermez pas la fenêtre du serveur si elle apparaît.
pause
