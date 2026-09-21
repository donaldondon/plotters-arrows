@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  AIWeatherReportTool.exe ビルドスクリプト
echo ============================================
echo.
echo 必要なライブラリをインストールしています...
python -m pip install --upgrade pyinstaller openai
if errorlevel 1 goto :error

echo.
echo AIWeatherReportTool.exe をビルドしています...
python -m PyInstaller --onefile --noconsole --name AIWeatherReportTool ai_weather_report_tool.py
if errorlevel 1 goto :error

echo.
echo データベースファイルを dist フォルダにコピーしています...
copy /Y "tochigi_weather_mock.db" "dist\tochigi_weather_mock.db" >nul

echo.
echo ============================================
echo  ビルド完了！
echo  dist フォルダの AIWeatherReportTool.exe をご確認ください。
echo  （tochigi_weather_mock.db も同じフォルダに配置済みです）
echo  起動後、画面にOpenAIのAPIキーを入力してご利用ください。
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
