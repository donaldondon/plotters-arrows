@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  WeatherHistory.exe ビルドスクリプト
echo ============================================
echo.
echo PyInstaller をインストールしています...
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

echo.
echo WeatherHistory.exe をビルドしています...
python -m PyInstaller --onefile --noconsole --name WeatherHistory weather_history_app.py
if errorlevel 1 goto :error

echo.
echo データベースファイルを dist フォルダにコピーしています...
copy /Y "tochigi_weather_mock.db" "dist\tochigi_weather_mock.db" >nul

echo.
echo ============================================
echo  ビルド完了！
echo  dist フォルダの WeatherHistory.exe をご確認ください。
echo  （tochigi_weather_mock.db も同じフォルダに配置済みです）
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
