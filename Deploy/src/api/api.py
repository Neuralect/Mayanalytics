import json
import boto3
import os
from datetime import datetime
from decimal import Decimal
import logging
from typing import Dict, List, Optional
import uuid

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')
cognito = boto3.client('cognito-idp')

# Environment variables
REGION = os.environ['REGION']
TENANTS_TABLE = os.environ['TENANTS_TABLE']
USERS_TABLE = os.environ['USERS_TABLE']
REPORTS_TABLE = os.environ.get('REPORTS_TABLE', '')
USER_POOL_ID = os.environ['USER_POOL_ID']

# DynamoDB tables
tenants_table = dynamodb.Table(TENANTS_TABLE)
users_table = dynamodb.Table(USERS_TABLE)
if REPORTS_TABLE:
    reports_table = dynamodb.Table(REPORTS_TABLE)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def get_user_from_event(event: Dict) -> Dict:
    """Extract user info from API Gateway authorizer context"""
    logger.info(f"Full event: {json.dumps(event)}")
    
    request_context = event.get('requestContext', {})
    authorizer = request_context.get('authorizer', {})
    
    logger.info(f"Authorizer context: {json.dumps(authorizer)}")
    
    claims = authorizer.get('claims', {})
    
    if not claims or not claims.get('sub'):
        logger.info("No claims from authorizer, decoding JWT from Authorization header")
        
        headers = event.get('headers', {})
        auth_header = headers.get('Authorization', headers.get('authorization', ''))
        
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            
            try:
                import base64
                parts = token.split('.')
                if len(parts) == 3:
                    payload = parts[1]
                    padding = len(payload) % 4
                    if padding:
                        payload += '=' * (4 - padding)
                    
                    decoded = base64.urlsafe_b64decode(payload)
                    claims = json.loads(decoded)
                    logger.info(f"Decoded JWT claims: {json.dumps(claims)}")
            except Exception as e:
                logger.error(f"Error decoding JWT: {str(e)}")
                claims = {}
    
    logger.info(f"Claims: {json.dumps(claims)}")
    
    # Extract user info
    user_id = claims.get('sub') or claims.get('cognito:username', '')
    email = claims.get('email', '')
    tenant_id = claims.get('custom:tenant_id', '')
    
    # Handle groups
    groups_value = claims.get('cognito:groups', '')
    if isinstance(groups_value, str):
        groups = groups_value.split(',') if groups_value else []
    elif isinstance(groups_value, list):
        groups = groups_value
    else:
        groups = []
    
    # CRITICAL FIX: If tenant_id is empty but user is SuperAdmin, set to SYSTEM
    if not tenant_id and 'SuperAdmin' in groups:
        tenant_id = 'SYSTEM'
        logger.info(f"SuperAdmin detected, setting tenant_id to SYSTEM")
    
    user_data = {
        'user_id': user_id,
        'email': email,
        'tenant_id': tenant_id,
        'groups': groups
    }
    
    logger.info(f"Extracted user data: {json.dumps(user_data)}")
    
    return user_data

def is_super_admin(user: Dict) -> bool:
    """Check if user is SuperAdmin"""
    return 'SuperAdmin' in user.get('groups', [])

def is_admin(user: Dict) -> bool:
    """Check if user is Admin"""
    return 'Admin' in user.get('groups', [])

def response(status_code: int, body: Dict) -> Dict:
    """Create API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Requested-With',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

# ========================================
# PROFILE MANAGEMENT - FIXED FOR EMPTY TENANT_ID
# ========================================

def get_profile(user: Dict) -> Dict:
    """Get current user's profile - FIXED to handle empty tenant_id"""
    try:
        user_id = user['user_id']
        tenant_id = user.get('tenant_id', '')
        
        logger.info(f"Getting profile for user_id: {user_id}, tenant_id: '{tenant_id}'")
        
        # CRITICAL FIX: If tenant_id is empty or missing, search by user_id only
        if not tenant_id:
            logger.info("tenant_id is empty, searching by user_id only")
            result = users_table.query(
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
        else:
            # Normal case with both keys
            result = users_table.query(
                KeyConditionExpression='user_id = :uid AND tenant_id = :tid',
                ExpressionAttributeValues={
                    ':uid': user_id,
                    ':tid': tenant_id
                }
            )
        
        if not result.get('Items'):
            logger.error(f"User profile not found for user_id: {user_id}, tenant_id: '{tenant_id}'")
            return response(404, {'error': 'User profile not found'})
        
        user_profile = result['Items'][0]
        
        # Add role from groups
        user_profile['role'] = 'SuperAdmin' if is_super_admin(user) else ('Admin' if is_admin(user) else 'User')
        
        return response(200, {'user': user_profile})
        
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        return response(500, {'error': str(e)})

def update_profile(event: Dict, user: Dict) -> Dict:
    """Update current user's profile - FIXED to handle empty tenant_id"""
    try:
        body = json.loads(event.get('body', '{}'))
        user_id = user['user_id']
        tenant_id = user.get('tenant_id', '')
        
        # Get existing user first to get the correct tenant_id
        if not tenant_id:
            result = users_table.query(
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
        else:
            result = users_table.query(
                KeyConditionExpression='user_id = :uid AND tenant_id = :tid',
                ExpressionAttributeValues={
                    ':uid': user_id,
                    ':tid': tenant_id
                }
            )
        
        if not result.get('Items'):
            return response(404, {'error': 'User profile not found'})
        
        user_item = result['Items'][0]
        actual_tenant_id = user_item['tenant_id']
        
        # Update fields
        update_expression = "SET "
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        updateable_fields = ['name', 'xml_endpoint', 'xml_token', 'report_enabled', 'report_schedule']
        updates = []
        
        for field in updateable_fields:
            if field in body:
                attr_name = f"#{field}"
                attr_value = f":{field}"
                updates.append(f"{attr_name} = {attr_value}")
                expression_attribute_names[attr_name] = field
                expression_attribute_values[attr_value] = body[field]
        
        if updates:
            update_expression += ", ".join(updates)
            
            users_table.update_item(
                Key={
                    'user_id': user_id,
                    'tenant_id': actual_tenant_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
        
        return response(200, {'message': 'Profile updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return response(500, {'error': str(e)})

# ========================================
# USER MANAGEMENT
# ========================================

def create_user(event: Dict, user: Dict) -> Dict:
    """Create new user within tenant (Admin only)"""
    if not is_admin(user) and not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: Admin only'})
    
    try:
        tenant_id = event['pathParameters']['tenant_id']
        
        # Authorization check - Admin can only manage their own tenant
        if is_admin(user) and user['tenant_id'] != tenant_id:
            return response(403, {'error': 'Unauthorized: Cannot manage other tenants'})
        
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        required_fields = ['name', 'email', 'xml_endpoint']
        for field in required_fields:
            if not body.get(field):
                return response(400, {'error': f'Missing required field: {field}'})
        
        timestamp = datetime.utcnow().isoformat()
        temp_password = 'TempPass123!'  # Will be changed on first login
        
        # Create Cognito user
        cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=body['email'],
            UserAttributes=[
                {'Name': 'email', 'Value': body['email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:tenant_id', 'Value': tenant_id}
            ],
            TemporaryPassword=temp_password,
            MessageAction='SUPPRESS'
        )
        
        # Set permanent password (optional, or let user change on first login)
        if body.get('password'):
            cognito.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=body['email'],
                Password=body['password'],
                Permanent=True
            )
        
        # Get real UUID from Cognito
        user_response = cognito.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=body['email']
        )
        
        real_user_id = None
        for attr in user_response['UserAttributes']:
            if attr['Name'] == 'sub':
                real_user_id = attr['Value']
                break
        
        if not real_user_id:
            raise Exception('Could not extract user UUID from Cognito')
        
        # Create user record in DynamoDB
        user_item = {
            'user_id': real_user_id,
            'tenant_id': tenant_id,
            'email': body['email'],
            'name': body['name'],
            'role': 'User',
            'created_at': timestamp,
            'xml_endpoint': body['xml_endpoint'],
            'xml_token': body.get('xml_token', ''),
            'report_enabled': True,  # Enable reports by default
            'report_schedule': body.get('report_schedule', json.dumps({
                'frequency': 'daily',
                'time': '09:00'
            })),
            'report_email': body.get('report_email', '')  # Optional: email for reports (can be duplicated)
        }
        
        users_table.put_item(Item=user_item)
        
        logger.info(f"Created user {real_user_id} for tenant {tenant_id}")
        
        return response(201, {
            'message': 'User created successfully',
            'user_id': real_user_id,
            'temporary_password': temp_password if not body.get('password') else None
        })
        
    except cognito.exceptions.UsernameExistsException:
        return response(400, {'error': 'User with this email already exists'})
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return response(500, {'error': str(e)})

def list_users(event: Dict, user: Dict) -> Dict:
    """List users within tenant (Admin only)"""
    if not is_admin(user) and not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: Admin only'})
    
    try:
        tenant_id = event['pathParameters']['tenant_id']
        
        # Authorization check - Admin can only see their own tenant
        if is_admin(user) and user['tenant_id'] != tenant_id:
            return response(403, {'error': 'Unauthorized: Cannot access other tenants'})
        
        # Query users by tenant_id using GSI
        result = users_table.query(
            IndexName='tenant-index',
            KeyConditionExpression='tenant_id = :tid',
            ExpressionAttributeValues={':tid': tenant_id}
        )
        
        users_list = result.get('Items', [])
        
        # Filter out admin users for cleaner display
        regular_users = [u for u in users_list if u.get('role') == 'User']
        
        return response(200, {'users': regular_users})
        
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        return response(500, {'error': str(e)})

def get_user(event: Dict, user: Dict) -> Dict:
    """Get user details"""
    try:
        user_id = event['pathParameters']['user_id']
        
        # Find user record
        result = users_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        if not result.get('Items'):
            return response(404, {'error': 'User not found'})
        
        target_user = result['Items'][0]
        
        # Authorization check
        if not is_super_admin(user):
            if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
                return response(403, {'error': 'Unauthorized'})
            elif not is_admin(user) and user['user_id'] != user_id:
                return response(403, {'error': 'Unauthorized'})
        
        return response(200, {'user': target_user})
        
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        return response(500, {'error': str(e)})

def update_user(event: Dict, user: Dict) -> Dict:
    """Update user details"""
    try:
        user_id = event['pathParameters']['user_id']
        body = json.loads(event.get('body', '{}'))
        
        # Find existing user
        result = users_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        if not result.get('Items'):
            return response(404, {'error': 'User not found'})
        
        target_user = result['Items'][0]
        
        # Authorization check
        if not is_super_admin(user):
            if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
                return response(403, {'error': 'Unauthorized'})
            elif not is_admin(user) and user['user_id'] != user_id:
                return response(403, {'error': 'Unauthorized'})
        
        # Update fields
        update_expression = "SET "
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        # Allow updating name, xml_endpoint, xml_token, report_enabled, report_schedule, and report_email
        # report_email can be duplicated across users (for multiple users receiving reports at same email)
        updateable_fields = ['name', 'xml_endpoint', 'xml_token', 'report_enabled', 'report_schedule', 'report_email']
        updates = []
        
        for field in updateable_fields:
            if field in body:
                attr_name = f"#{field}"
                attr_value = f":{field}"
                updates.append(f"{attr_name} = {attr_value}")
                expression_attribute_names[attr_name] = field
                expression_attribute_values[attr_value] = body[field]
        
        if updates:
            update_expression += ", ".join(updates)
            
            users_table.update_item(
                Key={
                    'user_id': user_id,
                    'tenant_id': target_user['tenant_id']
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
        
        return response(200, {'message': 'User updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return response(500, {'error': str(e)})

def delete_user(event: Dict, user: Dict) -> Dict:
    """Delete user (Admin only)"""
    if not is_admin(user) and not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: Admin only'})
    
    try:
        user_id = event['pathParameters']['user_id']
        
        # Find user to delete
        result = users_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        if not result.get('Items'):
            return response(404, {'error': 'User not found'})
        
        target_user = result['Items'][0]
        
        # Authorization check
        if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
            return response(403, {'error': 'Unauthorized: Cannot delete users from other tenants'})
        
        # Delete from Cognito
        cognito.admin_delete_user(
            UserPoolId=USER_POOL_ID,
            Username=target_user['email']
        )
        
        # Delete from DynamoDB
        users_table.delete_item(
            Key={
                'user_id': user_id,
                'tenant_id': target_user['tenant_id']
            }
        )
        
        return response(200, {'message': 'User deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        return response(500, {'error': str(e)})

# ========================================
# TENANT MANAGEMENT
# ========================================

def create_tenant(event: Dict, user: Dict) -> Dict:
    """Create new tenant with admin user (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        required_fields = ['name', 'admin_email', 'admin_name', 'admin_password']
        for field in required_fields:
            if not body.get(field):
                return response(400, {'error': f'Missing required field: {field}'})
        
        tenant_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Create Cognito user for tenant admin
        cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=body['admin_email'],
            UserAttributes=[
                {'Name': 'email', 'Value': body['admin_email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:tenant_id', 'Value': tenant_id}
            ],
            TemporaryPassword=body['admin_password'],
            MessageAction='SUPPRESS'
        )
        
        # Add to Admin group
        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID,
            Username=body['admin_email'],
            GroupName='Admin'
        )
        
        # Set permanent password
        cognito.admin_set_user_password(
            UserPoolId=USER_POOL_ID,
            Username=body['admin_email'],
            Password=body['admin_password'],
            Permanent=True
        )
        
        # CRITICAL FIX: Get real UUID from Cognito
        admin_user_response = cognito.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=body['admin_email']
        )
        
        # Extract UUID from UserAttributes
        real_user_id = None
        for attr in admin_user_response['UserAttributes']:
            if attr['Name'] == 'sub':
                real_user_id = attr['Value']
                break
        
        if not real_user_id:
            raise Exception('Could not extract user UUID from Cognito')
        
        logger.info(f"Admin user real UUID: {real_user_id}")
        
        # Create tenant record
        tenant_item = {
            'tenant_id': tenant_id,
            'name': body['name'],
            'admin_email': body['admin_email'],
            'admin_name': body['admin_name'],
            'created_at': timestamp,
            'status': 'active'
        }
        
        tenants_table.put_item(Item=tenant_item)
        
        # Create admin user record in DynamoDB with REAL UUID
        admin_user_item = {
            'user_id': real_user_id,  # FIXED: Use real UUID from Cognito
            'tenant_id': tenant_id,
            'email': body['admin_email'],
            'name': body['admin_name'],
            'role': 'Admin',
            'created_at': timestamp,
            'xml_endpoint': '',
            'xml_token': '',
            'report_enabled': False,
            'report_schedule': json.dumps({
                'frequency': 'daily',
                'time': '09:00'
            })
        }
        
        users_table.put_item(Item=admin_user_item)
        
        logger.info(f"Created admin user with UUID {real_user_id} for tenant {tenant_id}")
        
        return response(201, {
            'message': 'Tenant created successfully',
            'tenant_id': tenant_id,
            'admin_user_id': real_user_id  # Return the real UUID for verification
        })
        
    except cognito.exceptions.UsernameExistsException:
        return response(400, {'error': 'User with this email already exists'})
    except Exception as e:
        logger.error(f"Error creating tenant: {str(e)}")
        return response(500, {'error': str(e)})

def list_tenants(user: Dict) -> Dict:
    """List all tenants (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        result = tenants_table.scan()
        tenants = result.get('Items', [])
        return response(200, {'tenants': tenants})
        
    except Exception as e:
        logger.error(f"Error listing tenants: {str(e)}")
        return response(500, {'error': str(e)})

def get_tenant(event: Dict, user: Dict) -> Dict:
    """Get tenant details"""
    tenant_id = event['pathParameters']['tenant_id']
    
    # Authorization check
    if not is_super_admin(user):
        if not is_admin(user) or user['tenant_id'] != tenant_id:
            return response(403, {'error': 'Unauthorized'})
    
    try:
        result = tenants_table.get_item(Key={'tenant_id': tenant_id})
        
        if 'Item' not in result:
            return response(404, {'error': 'Tenant not found'})
        
        return response(200, {'tenant': result['Item']})
        
    except Exception as e:
        logger.error(f"Error getting tenant: {str(e)}")
        return response(500, {'error': str(e)})

# ========================================
# MAIN HANDLER
# ========================================

def lambda_handler(event, context):
    """Main Lambda handler - route requests"""
    logger.info(f"Event: {json.dumps(event)}")
    
    try:
        # Handle OPTIONS requests for CORS
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Requested-With',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
                },
                'body': json.dumps({'message': 'OK'})
            }
        
        # Get user from authorizer
        user = get_user_from_event(event)
        
        # Get HTTP method and path
        method = event.get('httpMethod')
        path = event.get('path', '')
        
        # Route requests
        if path == '/tenants':
            if method == 'POST':
                return create_tenant(event, user)
            elif method == 'GET':
                return list_tenants(user)
        
        elif path.startswith('/tenants/') and path.endswith('/users'):
            if method == 'POST':
                return create_user(event, user)
            elif method == 'GET':
                return list_users(event, user)
        
        elif path.startswith('/tenants/') and '/users' not in path and '/reports' not in path:
            if method == 'GET':
                return get_tenant(event, user)
        
        elif path.startswith('/users/') and not path.endswith('/reports'):
            if method == 'GET':
                return get_user(event, user)
            elif method == 'PUT':
                return update_user(event, user)
            elif method == 'DELETE':
                return delete_user(event, user)
        
        elif path == '/profile':
            if method == 'GET':
                return get_profile(user)
            elif method == 'PUT':
                return update_profile(event, user)
        
        return response(404, {'error': 'Not found'})
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return response(500, {'error': str(e)})