@echo off
REM Maya Multitenant - Deploy Script (Windows)
REM Automatizza il processo di build e deploy su AWS

setlocal enabledelayedexpansion

echo.
echo =======================================
echo   Maya Multitenant - Deploy Script
echo =======================================
echo.

REM Configuration
set PROFILE=AdministratorAccess-960902921831
set REGION=eu-central-1
set STACK_NAME=maya-multitenant
set ENVIRONMENT=prod

REM Step 1: AWS SSO Login
echo [STEP 1] AWS SSO Login
aws sso login --profile %PROFILE%
if errorlevel 1 (
    echo [ERROR] AWS SSO login failed
    exit /b 1
)

REM Step 2: Install Python dependencies
echo.
echo [STEP 2] Installing Python dependencies
pip install -r src\requirements.txt --target src\api\ --upgrade
pip install -r src\requirements.txt --target src\report-generator\ --upgrade
pip install -r src\requirements.txt --target src\email-sender\ --upgrade

REM Step 3: SAM Build
echo.
echo [STEP 3] Building SAM application
sam build --use-container --region %REGION%
if errorlevel 1 (
    echo [ERROR] SAM build failed
    exit /b 1
)

REM Step 4: SAM Deploy
echo.
echo [STEP 4] Deploying to AWS
sam deploy --stack-name %STACK_NAME% --resolve-s3 --s3-prefix %STACK_NAME% --region %REGION% --profile %PROFILE% --capabilities CAPABILITY_IAM --parameter-overrides Environment=%ENVIRONMENT% --no-confirm-changeset
if errorlevel 1 (
    echo [ERROR] SAM deploy failed
    exit /b 1
)

REM Step 5: Get Stack Outputs
echo.
echo [STEP 5] Retrieving Stack Outputs
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name %STACK_NAME% --region %REGION% --profile %PROFILE% --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text') do set API_URL=%%i
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name %STACK_NAME% --region %REGION% --profile %PROFILE% --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text') do set USER_POOL_ID=%%i
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name %STACK_NAME% --region %REGION% --profile %PROFILE% --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text') do set USER_POOL_CLIENT_ID=%%i

echo API URL: %API_URL%
echo User Pool ID: %USER_POOL_ID%
echo User Pool Client ID: %USER_POOL_CLIENT_ID%

REM Step 6: Update Frontend Environment Variables
echo.
echo [STEP 6] Updating Frontend Configuration
(
echo NEXT_PUBLIC_API_URL=%API_URL%
echo NEXT_PUBLIC_USER_POOL_ID=%USER_POOL_ID%
echo NEXT_PUBLIC_USER_POOL_CLIENT_ID=%USER_POOL_CLIENT_ID%
echo NEXT_PUBLIC_REGION=%REGION%
) > frontend\.env.production

echo Frontend .env.production created

REM Step 7: Build Frontend
echo.
echo [STEP 7] Building Frontend
cd frontend
call npm install
call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed
    cd ..
    exit /b 1
)
cd ..

REM Step 8: Create ZIP for Amplify
echo.
echo [STEP 8] Creating Amplify ZIP
cd frontend\out
powershell -command "Compress-Archive -Path * -DestinationPath ..\maya-frontend-amplify.zip -Force"
cd ..\..

echo Amplify ZIP created: frontend\maya-frontend-amplify.zip

REM Step 9: Display Deployment Summary
echo.
echo =======================================
echo  Deployment Completed Successfully!
echo =======================================
echo.
echo Deployment Summary:
echo   Stack Name: %STACK_NAME%
echo   Region: %REGION%
echo   Environment: %ENVIRONMENT%
echo.
echo API Endpoint:
echo   %API_URL%
echo.
echo Cognito User Pool:
echo   Pool ID: %USER_POOL_ID%
echo   Client ID: %USER_POOL_CLIENT_ID%
echo.
echo Next Steps:
echo   1. Upload frontend\maya-frontend-amplify.zip to AWS Amplify
echo   2. Create SuperAdmin user: scripts\create-superadmin.bat
echo   3. Configure SES sender identity (already verified: noreply@neuralect.it)
echo.
echo Documentation: See README.md for more details
echo.

endlocal
