@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  WeatherMenuApp.exe ビルドスクリプト
echo ============================================
echo.
echo 必要なライブラリをインストールしています...
python -m pip install --upgrade pyinstaller requests beautifulsoup4 pillow openai
if errorlevel 1 goto :error

echo.
echo WeatherMenuApp.exe をビルドしています...
python -m PyInstaller --onefile --noconsole --name WeatherMenuApp weathermenu_app.py
if errorlevel 1 goto :error

echo.
echo 在庫ファイルを dist フォルダにコピーしています...
copy /Y "stock_input.csv" "dist\stock_input.csv" >nul

echo.
echo ============================================
echo  ビルド完了！
echo  dist フォルダの WeatherMenuApp.exe をご確認ください。
echo  （stock_input.csv も同じフォルダに配置済みです）
echo.
echo  在庫を更新したいときは、dist フォルダの
echo  stock_input.csv をメモ帳やExcelで編集してから
echo  アプリを再起動してください。
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
