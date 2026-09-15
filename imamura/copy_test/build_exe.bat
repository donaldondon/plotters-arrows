@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  Osero.exe ビルドスクリプト
echo ============================================
echo.
echo PyInstaller と pygame をインストールしています...
python -m pip install --upgrade pyinstaller pygame
if errorlevel 1 goto :error

echo.
echo Osero.exe をビルドしています...
python -m PyInstaller --onefile --noconsole --name Osero osero_kai1.py
if errorlevel 1 goto :error

echo.
echo ============================================
echo  ビルド完了！
echo  dist フォルダの Osero.exe をご確認ください。
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
