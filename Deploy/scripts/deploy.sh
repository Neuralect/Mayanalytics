#!/bin/bash

# Maya Multitenant - Deploy Script
# Automatizza il processo di build e deploy su AWS

set -e  # Exit on error

echo "🤖 Maya Multitenant - Deploy Script"
echo "===================================="

# Configuration
PROFILE="AdministratorAccess-960902921831"
REGION="eu-central-1"
STACK_NAME="maya-multitenant"
ENVIRONMENT="prod"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: AWS SSO Login
log_info "Step 1: AWS SSO Login"
aws sso login --profile $PROFILE
if [ $? -ne 0 ]; then
    log_error "AWS SSO login failed"
    exit 1
fi

# Step 2: Install Python dependencies
log_info "Step 2: Installing Python dependencies"
pip install -r src/requirements.txt --target src/api/ --upgrade
pip install -r src/requirements.txt --target src/report-generator/ --upgrade
pip install -r src/requirements.txt --target src/email-sender/ --upgrade

# Step 3: SAM Build
log_info "Step 3: Building SAM application"
sam build --use-container --region $REGION
if [ $? -ne 0 ]; then
    log_error "SAM build failed"
    exit 1
fi

# Step 4: SAM Deploy
log_info "Step 4: Deploying to AWS"
sam deploy \
    --stack-name $STACK_NAME \
    --resolve-s3 \
    --s3-prefix $STACK_NAME \
    --region $REGION \
    --profile $PROFILE \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides Environment=$ENVIRONMENT \
    --no-confirm-changeset
if [ $? -ne 0 ]; then
    log_error "SAM deploy failed"
    exit 1
fi

# Step 5: Get Stack Outputs
log_info "Step 5: Retrieving Stack Outputs"
API_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
    --output text)

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
    --output text)

USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
    --output text)

log_info "API URL: $API_URL"
log_info "User Pool ID: $USER_POOL_ID"
log_info "User Pool Client ID: $USER_POOL_CLIENT_ID"

# Step 6: Update Frontend Environment Variables
log_info "Step 6: Updating Frontend Configuration"
cat > frontend/.env.production << EOF
NEXT_PUBLIC_API_URL=$API_URL
NEXT_PUBLIC_USER_POOL_ID=$USER_POOL_ID
NEXT_PUBLIC_USER_POOL_CLIENT_ID=$USER_POOL_CLIENT_ID
NEXT_PUBLIC_REGION=$REGION
EOF

log_info "Frontend .env.production created"

# Step 7: Build Frontend
log_info "Step 7: Building Frontend"
cd frontend
npm install
npm run build
if [ $? -ne 0 ]; then
    log_error "Frontend build failed"
    exit 1
fi
cd ..

# Step 8: Create ZIP for Amplify
log_info "Step 8: Creating Amplify ZIP"
cd frontend/out
zip -r ../maya-frontend-amplify.zip .
cd ../..

log_info "Amplify ZIP created: frontend/maya-frontend-amplify.zip"

# Step 9: Display Deployment Summary
echo ""
echo "===================================="
echo "✅ Deployment Completed Successfully!"
echo "===================================="
echo ""
echo "📋 Deployment Summary:"
echo "  Stack Name: $STACK_NAME"
echo "  Region: $REGION"
echo "  Environment: $ENVIRONMENT"
echo ""
echo "🔗 API Endpoint:"
echo "  $API_URL"
echo ""
echo "👤 Cognito User Pool:"
echo "  Pool ID: $USER_POOL_ID"
echo "  Client ID: $USER_POOL_CLIENT_ID"
echo ""
echo "📦 Next Steps:"
echo "  1. Upload frontend/maya-frontend-amplify.zip to AWS Amplify"
echo "  2. Create SuperAdmin user: ./scripts/create-superadmin.sh"
echo "  3. Configure SES sender identity (already verified: noreply@neuralect.it)"
echo ""
echo "📖 Documentation: See README.md for more details"
echo ""
