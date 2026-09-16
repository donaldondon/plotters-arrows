@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  TomorrowsWeather.exe ビルドスクリプト
echo ============================================
echo.
echo 必要なライブラリをインストールしています...
python -m pip install --upgrade pyinstaller requests beautifulsoup4
if errorlevel 1 goto :error

echo.
echo TomorrowsWeather.exe をビルドしています...
python -m PyInstaller --onefile --noconsole --name TomorrowsWeather weather_app.py
if errorlevel 1 goto :error

echo.
echo ============================================
echo  ビルド完了！
echo  dist フォルダの TomorrowsWeather.exe をご確認ください。
echo ============================================
pause
exit /b 0

:error
echo.
echo ビルドに失敗しました。上のメッセージをご確認ください。
echo （python が見つからない場合は、Python をインストールし
echo   「PATHに追加」にチェックを入れてから再実行してください）
pause
exit /b 1
