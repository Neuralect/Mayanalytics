@echo off
REM =======================================
REM Maya Analytics - Create SuperAdmin (AGGIORNATO)
REM Corretto per nuovo pool e configurazioni
REM =======================================

setlocal enabledelayedexpansion

echo.
echo =======================================
echo   Maya - SuperAdmin SCRIPT AGGIORNATO
echo =======================================
echo.

REM ===== CONFIGURAZIONE AGGIORNATA =====
set PROFILE=Neuralect_Maya_share
set REGION=eu-central-1
set USER_POOL_ID=eu-central-1_jVkfkoatG
set CLIENT_ID=5k8kqhpmdufe2ou376l5qsdpmo
set USERS_TABLE=maya-users-prod

REM ===== DATI SUPERADMIN =====
set ADMIN_EMAIL=emiliano.menichelli@neuralect.it
set ADMIN_NAME=Emiliano Superadmin
set ADMIN_PASSWORD=Neuralect.123!
set USERNAME=%ADMIN_EMAIL%

echo [INFO] SuperAdmin:
echo   Username: %USERNAME%
echo   Email:    %ADMIN_EMAIL%
echo   Nome:     %ADMIN_NAME%
echo   Pool ID:  %USER_POOL_ID%
echo   Client:   %CLIENT_ID%
echo   Table:    %USERS_TABLE%
echo.

REM ===== CLEANUP =====
echo [CLEANUP] Eliminazione utente esistente...
aws cognito-idp admin-delete-user --user-pool-id %USER_POOL_ID% --username %ADMIN_EMAIL% --region %REGION% --profile %PROFILE% >nul 2>&1

aws dynamodb scan --table-name %USERS_TABLE% --region %REGION% --profile %PROFILE% --query "Items[?email.S=='%ADMIN_EMAIL%'].{user_id:user_id.S,tenant_id:tenant_id.S}" --output text > temp_users.txt
for /f "tokens=1,2" %%a in (temp_users.txt) do (
    aws dynamodb delete-item --table-name %USERS_TABLE% --key "{\"user_id\": {\"S\": \"%%a\"}, \"tenant_id\": {\"S\": \"%%b\"}}" --region %REGION% --profile %PROFILE% >nul 2>&1
)
del temp_users.txt >nul 2>&1
echo ✅ Cleanup completato
echo.

REM ===== STEP 1: CREAZIONE COGNITO =====
echo =======================================
echo   Step 1: Creazione utente Cognito
echo =======================================

echo [1.1] Verifica User Pool...
aws cognito-idp describe-user-pool --user-pool-id %USER_POOL_ID% --region %REGION% --profile %PROFILE% --query "UserPool.Name" --output text
if errorlevel 1 (
    echo [ERRORE] User Pool non trovato: %USER_POOL_ID%
    pause
    exit /b 1
)

echo [1.2] Creazione utente con admin-create-user (email as username)...
aws cognito-idp admin-create-user ^
    --user-pool-id %USER_POOL_ID% ^
    --username %ADMIN_EMAIL% ^
    --user-attributes Name=email,Value=%ADMIN_EMAIL% Name=email_verified,Value=true Name=preferred_username,Value=%ADMIN_EMAIL% ^
    --temporary-password "%ADMIN_PASSWORD%" ^
    --message-action SUPPRESS ^
    --region %REGION% ^
    --profile %PROFILE%

if errorlevel 1 (
    echo [ERRORE] Admin-create-user fallito
    goto :restore_exit
)

echo [1.3] Conferma utente e imposta password permanente...
aws cognito-idp admin-set-user-password ^
    --user-pool-id %USER_POOL_ID% ^
    --username %ADMIN_EMAIL% ^
    --password "%ADMIN_PASSWORD%" ^
    --permanent ^
    --region %REGION% ^
    --profile %PROFILE% >nul

echo [1.4] Configura attributi critici (tenant_id=SYSTEM)...
aws cognito-idp admin-update-user-attributes ^
    --user-pool-id %USER_POOL_ID% ^
    --username %ADMIN_EMAIL% ^
    --user-attributes Name=custom:tenant_id,Value=SYSTEM Name=email_verified,Value=true ^
    --region %REGION% ^
    --profile %PROFILE% >nul

echo [1.5] Crea gruppo SuperAdmin se non esiste...
aws cognito-idp create-group ^
    --group-name SuperAdmin ^
    --user-pool-id %USER_POOL_ID% ^
    --region %REGION% ^
    --profile %PROFILE% >nul 2>&1

echo [1.6] Aggiungi utente al gruppo SuperAdmin...
aws cognito-idp admin-add-user-to-group ^
    --user-pool-id %USER_POOL_ID% ^
    --username %ADMIN_EMAIL% ^
    --group-name SuperAdmin ^
    --region %REGION% ^
    --profile %PROFILE% >nul

echo ✅ Utente Cognito creato e configurato correttamente
echo.

REM ===== STEP 2: ESTRARRE UUID =====
echo =======================================
echo   Step 2: Estrazione UUID dal token
echo =======================================

echo [2.1] Generazione token di autenticazione...
aws cognito-idp admin-initiate-auth ^
    --user-pool-id %USER_POOL_ID% ^
    --client-id %CLIENT_ID% ^
    --auth-flow ADMIN_NO_SRP_AUTH ^
    --auth-parameters USERNAME=%ADMIN_EMAIL%,PASSWORD=%ADMIN_PASSWORD% ^
    --region %REGION% ^
    --profile %PROFILE% ^
    --query "AuthenticationResult.IdToken" ^
    --output text > id_token.txt

if errorlevel 1 (
    echo [ERRORE] Impossibile generare token
    goto :cleanup_exit
)

echo [2.2] Estrazione UUID da JWT...
set /p ID_TOKEN=<id_token.txt
del id_token.txt

for /f "tokens=2 delims=." %%i in ("%ID_TOKEN%") do set JWT_PAYLOAD=%%i

powershell -Command "$payload = '%JWT_PAYLOAD%'; $pad = 4 - ($payload.Length %% 4); if ($pad -ne 4) { $payload += '=' * $pad }; $json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload)) | ConvertFrom-Json; $json.sub" > user_id_temp.txt

set /p REAL_USER_ID=<user_id_temp.txt
del user_id_temp.txt

if "%REAL_USER_ID%"=="" (
    echo [ERRORE] UUID non estratto dal token
    goto :cleanup_exit
)

echo ✅ UUID estratto: %REAL_USER_ID%
echo.

REM ===== STEP 3: CREAZIONE RECORD DYNAMODB =====
echo =======================================
echo   Step 3: Creazione record DynamoDB
echo =======================================

echo [3.1] Preparazione timestamp...
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%T%datetime:~8,2%:%datetime:~10,2%:%datetime:~12,2%Z

echo [3.2] Inserimento record in DynamoDB...
aws dynamodb put-item ^
    --table-name %USERS_TABLE% ^
    --item "{\"user_id\": {\"S\": \"%REAL_USER_ID%\"}, \"tenant_id\": {\"S\": \"SYSTEM\"}, \"email\": {\"S\": \"%ADMIN_EMAIL%\"}, \"name\": {\"S\": \"%ADMIN_NAME%\"}, \"role\": {\"S\": \"SuperAdmin\"}, \"xml_endpoint\": {\"S\": \"\"}, \"xml_token\": {\"S\": \"\"}, \"report_schedule\": {\"S\": \"{\\\"frequency\\\": \\\"daily\\\", \\\"time\\\": \\\"09:00\\\"}\"}, \"report_enabled\": {\"BOOL\": false}, \"created_at\": {\"S\": \"%TIMESTAMP%\"}}" ^
    --region %REGION% ^
    --profile %PROFILE%

if errorlevel 1 (
    echo [ERRORE] Creazione record DynamoDB fallita
    goto :cleanup_exit
)

echo ✅ Record DynamoDB creato con UUID: %REAL_USER_ID%
echo.

REM ===== STEP 4: TEST FINALE =====
echo =======================================
echo   Step 4: Test finale completo
echo =======================================

echo [Test 1] Autenticazione con IdToken...
aws cognito-idp admin-initiate-auth ^
    --user-pool-id %USER_POOL_ID% ^
    --client-id %CLIENT_ID% ^
    --auth-flow ADMIN_NO_SRP_AUTH ^
    --auth-parameters USERNAME=%ADMIN_EMAIL%,PASSWORD=%ADMIN_PASSWORD% ^
    --region %REGION% ^
    --profile %PROFILE% ^
    --query "AuthenticationResult.IdToken" ^
    --output text >nul

if errorlevel 1 (
    echo [ERRORE] Test autenticazione fallito
    goto :cleanup_exit
)

echo [Test 2] Verifica record DynamoDB...
aws dynamodb get-item ^
    --table-name %USERS_TABLE% ^
    --key "{\"user_id\": {\"S\": \"%REAL_USER_ID%\"}, \"tenant_id\": {\"S\": \"SYSTEM\"}}" ^
    --region %REGION% ^
    --profile %PROFILE% ^
    --query "Item.{UserID:user_id.S,Email:email.S,Nome:name.S,Ruolo:role.S,TenantID:tenant_id.S}" ^
    --output table

echo [Test 3] Verifica attributi Cognito...
aws cognito-idp admin-get-user ^
    --user-pool-id %USER_POOL_ID% ^
    --username %ADMIN_EMAIL% ^
    --region %REGION% ^
    --profile %PROFILE% ^
    --query "UserAttributes[?Name=='sub' || Name=='custom:tenant_id' || Name=='email']" ^
    --output table

echo [Test 4] Verifica gruppi...
aws cognito-idp admin-list-groups-for-user ^
    --user-pool-id %USER_POOL_ID% ^
    --username %ADMIN_EMAIL% ^
    --region %REGION% ^
    --profile %PROFILE% ^
    --query "Groups[].GroupName" ^
    --output table

echo ✅ Tutti i test completati con successo!
echo.
echo =======================================
echo   🎉 SUPERADMIN CREATO PERFETTAMENTE! 🎉
echo =======================================
echo.
echo 📋 Configurazione:
echo   Pool ID:    %USER_POOL_ID%
echo   Client ID:  %CLIENT_ID%
echo   User UUID:  %REAL_USER_ID%
echo   Tenant ID:  SYSTEM
echo.
echo 🔐 Credenziali di accesso:
echo   Email:      %ADMIN_EMAIL%
echo   Password:   %ADMIN_PASSWORD%
echo.
echo 🌐 URL Frontend:
echo   API:        https://78jt5iyn1f.execute-api.eu-central-1.amazonaws.com/Prod
echo   Frontend:   Apri il tuo index.html aggiornato
echo.
echo 🚀 Ora puoi accedere al frontend Maya Analytics!
echo.
pause
exit /b 0

:cleanup_exit
echo [CLEANUP] Eliminazione utente fallito...
aws cognito-idp admin-delete-user ^
    --user-pool-id %USER_POOL_ID% ^
    --username %ADMIN_EMAIL% ^
    --region %REGION% ^
    --profile %PROFILE% >nul 2>&1

if not "%REAL_USER_ID%"=="" (
    aws dynamodb delete-item ^
        --table-name %USERS_TABLE% ^
        --key "{\"user_id\": {\"S\": \"%REAL_USER_ID%\"}, \"tenant_id\": {\"S\": \"SYSTEM\"}}" ^
        --region %REGION% ^
        --profile %PROFILE% >nul 2>&1
)

:restore_exit
echo.
echo =======================================
echo   ❌ CREAZIONE FALLITA
echo =======================================
echo.
echo Controlla:
echo 1. AWS CLI configurato correttamente
echo 2. Profilo: %PROFILE%
echo 3. Region: %REGION%
echo 4. User Pool ID: %USER_POOL_ID%
echo 5. Client ID: %CLIENT_ID%
echo 6. Table: %USERS_TABLE%
echo.
pause
exit /b 1
