
@echo off
echo [Mission] 1. Start Intensive AI Training...
python train_dl_model.py
if %ERRORLEVEL% NEQ 0 (
    echo [Fail] Training failed! Check logs.
    pause
    exit /b
)

echo [Mission] 2. Training Complete! Saving to Git...
git add DL_stock_model.pth
git commit -m "Feat: Update trained AI model (HunterTransformer)"
git push
if %ERRORLEVEL% NEQ 0 (
    echo [Warning] Git push failed (maybe generated file is too large or network issue). Continuing...
)

echo [Mission] 3. Starting System...
python start.py
