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
RESELLER_TENANTS_TABLE = os.environ.get('RESELLER_TENANTS_TABLE', '')
RESELLER_ORGANIZATIONS_TABLE = os.environ.get('RESELLER_ORGANIZATIONS_TABLE', '')
RESELLER_USER_ORGANIZATIONS_TABLE = os.environ.get('RESELLER_USER_ORGANIZATIONS_TABLE', '')
RESELLER_ORG_TENANTS_TABLE = os.environ.get('RESELLER_ORG_TENANTS_TABLE', '')
USER_POOL_ID = os.environ['USER_POOL_ID']

# DynamoDB tables
tenants_table = dynamodb.Table(TENANTS_TABLE)
users_table = dynamodb.Table(USERS_TABLE)
if REPORTS_TABLE:
    reports_table = dynamodb.Table(REPORTS_TABLE)
if RESELLER_TENANTS_TABLE:
    reseller_tenants_table = dynamodb.Table(RESELLER_TENANTS_TABLE)
if RESELLER_ORGANIZATIONS_TABLE:
    reseller_organizations_table = dynamodb.Table(RESELLER_ORGANIZATIONS_TABLE)
if RESELLER_USER_ORGANIZATIONS_TABLE:
    reseller_user_organizations_table = dynamodb.Table(RESELLER_USER_ORGANIZATIONS_TABLE)
if RESELLER_ORG_TENANTS_TABLE:
    reseller_org_tenants_table = dynamodb.Table(RESELLER_ORG_TENANTS_TABLE)

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
    
    # CRITICAL FIX: If tenant_id is empty but user is SuperAdmin or Reseller, set to SYSTEM
    if not tenant_id and ('SuperAdmin' in groups or 'Reseller' in groups):
        tenant_id = 'SYSTEM'
        logger.info(f"SuperAdmin or Reseller detected, setting tenant_id to SYSTEM")
    
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

def is_reseller(user: Dict) -> bool:
    """Check if user is Reseller"""
    return 'Reseller' in user.get('groups', [])

def is_admin(user: Dict) -> bool:
    """Check if user is Admin"""
    return 'Admin' in user.get('groups', [])

def get_reseller_organizations(reseller_user_id: str) -> List[str]:
    """Get list of organization IDs for a reseller user"""
    if not RESELLER_USER_ORGANIZATIONS_TABLE:
        return []
    
    try:
        result = reseller_user_organizations_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': reseller_user_id}
        )
        return [item['org_id'] for item in result.get('Items', [])]
    except Exception as e:
        logger.error(f"Error getting reseller organizations: {str(e)}")
        return []

def get_organization_tenants(org_id: str) -> List[str]:
    """Get list of tenant IDs assigned to a reseller organization"""
    if not RESELLER_ORG_TENANTS_TABLE:
        return []
    
    try:
        result = reseller_org_tenants_table.query(
            KeyConditionExpression='reseller_org_id = :oid',
            ExpressionAttributeValues={':oid': org_id}
        )
        return [item['tenant_id'] for item in result.get('Items', [])]
    except Exception as e:
        logger.error(f"Error getting organization tenants: {str(e)}")
        return []

def get_reseller_tenants(reseller_id: str) -> List[str]:
    """Get list of tenant IDs assigned to a reseller (direct + via organizations)"""
    tenant_ids = set()
    
    # Get direct tenant assignments (retrocompatibilità)
    if RESELLER_TENANTS_TABLE:
        try:
            result = reseller_tenants_table.query(
                KeyConditionExpression='reseller_id = :rid',
                ExpressionAttributeValues={':rid': reseller_id}
            )
            for item in result.get('Items', []):
                tenant_ids.add(item['tenant_id'])
        except Exception as e:
            logger.error(f"Error getting direct reseller tenants: {str(e)}")
    
    # Get tenant assignments via organizations
    org_ids = get_reseller_organizations(reseller_id)
    for org_id in org_ids:
        org_tenants = get_organization_tenants(org_id)
        tenant_ids.update(org_tenants)
    
    return list(tenant_ids)

def is_tenant_assigned_to_reseller(tenant_id: str, reseller_id: str) -> bool:
    """Check if a tenant is assigned to a reseller (direct or via organizations)"""
    # Check direct assignment (retrocompatibilità)
    if RESELLER_TENANTS_TABLE:
        try:
            result = reseller_tenants_table.get_item(
                Key={
                    'reseller_id': reseller_id,
                    'tenant_id': tenant_id
                }
            )
            if 'Item' in result:
                return True
        except Exception as e:
            logger.error(f"Error checking direct tenant assignment: {str(e)}")
    
    # Check via organizations
    org_ids = get_reseller_organizations(reseller_id)
    for org_id in org_ids:
        org_tenants = get_organization_tenants(org_id)
        if tenant_id in org_tenants:
            return True
    
    return False

def can_reseller_access_tenant(user: Dict, tenant_id: str) -> bool:
    """Check if reseller can access a specific tenant (direct or via organizations)"""
    if not is_reseller(user):
        return False
    
    reseller_id = user['user_id']
    return is_tenant_assigned_to_reseller(tenant_id, reseller_id)

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
        if is_super_admin(user):
            user_profile['role'] = 'SuperAdmin'
        elif is_reseller(user):
            user_profile['role'] = 'Reseller'
        elif is_admin(user):
            user_profile['role'] = 'Admin'
        else:
            user_profile['role'] = 'User'
        
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
    """Create new user within tenant (Admin, Reseller, or SuperAdmin only)
    
    NOTE: End-users (role='User') do NOT have Cognito accounts.
    They only receive email reports. No login required.
    """
    if not is_admin(user) and not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: Admin, Reseller, or SuperAdmin only'})
    
    try:
        tenant_id = event['pathParameters']['tenant_id']
        
        # Authorization check - Admin can only manage their own tenant
        if is_admin(user) and user['tenant_id'] != tenant_id:
            return response(403, {'error': 'Unauthorized: Cannot manage other tenants'})
        
        # Authorization check - Reseller can only manage their assigned tenants
        if is_reseller(user) and not can_reseller_access_tenant(user, tenant_id):
            return response(403, {'error': 'Unauthorized: Cannot manage tenants not assigned to you'})
        
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields - SIMPLIFIED: only name and email required
        required_fields = ['name', 'email']
        for field in required_fields:
            if not body.get(field):
                return response(400, {'error': f'Missing required field: {field}'})
        
        timestamp = datetime.utcnow().isoformat()
        
        # Generate UUID locally (NO Cognito for end-users)
        user_id = str(uuid.uuid4())
        
        # NOTE: Email can be duplicated across users (multiple users can receive reports at same email)
        # No uniqueness check needed - users are identified by user_id, not email
        
        # Create user record in DynamoDB (NO Cognito)
        # Use report_email if provided, otherwise use email
        report_email = body.get('report_email', '') or body['email']
        
        user_item = {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'email': body['email'],
            'name': body['name'],
            'role': 'User',
            'created_at': timestamp,
            'report_email': report_email,
            # Default: no connectors, will be added separately
            'connectors': body.get('connectors', [])  # Array of XML connectors
        }
        
        # If xml_endpoint provided (backward compatibility), create first connector
        if body.get('xml_endpoint'):
            connector = {
                'connector_id': str(uuid.uuid4()),
                'name': body.get('connector_name', 'Report Principale'),
                'xml_endpoint': body['xml_endpoint'],
                'xml_token': body.get('xml_token', ''),
                'report_enabled': True,
                'report_schedule': body.get('report_schedule', json.dumps({
                    'frequency': 'daily',
                    'time': '09:00'
                }))
            }
            user_item['connectors'] = [connector]
        
        users_table.put_item(Item=user_item)
        
        logger.info(f"Created end-user {user_id} for tenant {tenant_id} (NO Cognito account)")
        
        return response(201, {
            'message': 'User created successfully (email-only, no login)',
            'user_id': user_id,
            'email': body['email']
        })
        
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return response(500, {'error': str(e)})

def list_users(event: Dict, user: Dict) -> Dict:
    """List users within tenant (Admin, Reseller, or SuperAdmin only)"""
    if not is_admin(user) and not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: Admin, Reseller, or SuperAdmin only'})
    
    try:
        tenant_id = event['pathParameters']['tenant_id']
        
        # Authorization check - Admin can only see their own tenant
        if is_admin(user) and user['tenant_id'] != tenant_id:
            return response(403, {'error': 'Unauthorized: Cannot access other tenants'})
        
        # Authorization check - Reseller can only see their assigned tenants
        if is_reseller(user) and not can_reseller_access_tenant(user, tenant_id):
            return response(403, {'error': 'Unauthorized: Cannot access tenants not assigned to you'})
        
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
        if not is_super_admin(user) and not is_reseller(user):
            if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
                return response(403, {'error': 'Unauthorized'})
            elif not is_admin(user) and user['user_id'] != user_id:
                return response(403, {'error': 'Unauthorized'})
        elif is_reseller(user) and not can_reseller_access_tenant(user, target_user['tenant_id']):
            return response(403, {'error': 'Unauthorized: Cannot access users from tenants not assigned to you'})
        
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
        if not is_super_admin(user) and not is_reseller(user):
            if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
                return response(403, {'error': 'Unauthorized'})
            elif not is_admin(user) and user['user_id'] != user_id:
                return response(403, {'error': 'Unauthorized'})
        elif is_reseller(user) and not can_reseller_access_tenant(user, target_user['tenant_id']):
            return response(403, {'error': 'Unauthorized: Cannot update users from tenants not assigned to you'})
        
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
    """Delete user (Admin, Reseller, or SuperAdmin only)"""
    if not is_admin(user) and not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: Admin, Reseller, or SuperAdmin only'})
    
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
        
        # Authorization check - Reseller can only delete users from their assigned tenants
        if is_reseller(user) and not can_reseller_access_tenant(user, target_user['tenant_id']):
            return response(403, {'error': 'Unauthorized: Cannot delete users from tenants not assigned to you'})
        
        # Delete from Cognito ONLY if user has Cognito account (Admin/SuperAdmin/Reseller)
        # End-users (role='User') don't have Cognito accounts
        if target_user.get('role') != 'User':
            try:
                cognito.admin_delete_user(
                    UserPoolId=USER_POOL_ID,
                    Username=target_user['email']
                )
                logger.info(f"Deleted Cognito account for user {user_id}")
            except Exception as e:
                logger.warning(f"Could not delete Cognito account (may not exist): {str(e)}")
        
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
# CONNECTOR MANAGEMENT
# ========================================

def create_connector(event: Dict, user: Dict) -> Dict:
    """Add connector to user (Admin, Reseller, or SuperAdmin only)"""
    if not is_admin(user) and not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: Admin, Reseller, or SuperAdmin only'})
    
    try:
        user_id = event['pathParameters']['user_id']
        
        # Find user
        result = users_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        if not result.get('Items'):
            return response(404, {'error': 'User not found'})
        
        target_user = result['Items'][0]
        
        # Authorization check
        if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
            return response(403, {'error': 'Unauthorized: Cannot manage users from other tenants'})
        
        if is_reseller(user) and not can_reseller_access_tenant(user, target_user['tenant_id']):
            return response(403, {'error': 'Unauthorized: Cannot manage users from tenants not assigned to you'})
        
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        if not body.get('xml_endpoint'):
            return response(400, {'error': 'Missing required field: xml_endpoint'})
        
        # Create connector
        connector = {
            'connector_id': str(uuid.uuid4()),
            'name': body.get('name', 'Report'),
            'xml_endpoint': body['xml_endpoint'],
            'xml_token': body.get('xml_token', ''),
            'report_enabled': body.get('report_enabled', True),
            'report_schedule': body.get('report_schedule', json.dumps({
                'frequency': 'daily',
                'time': '09:00'
            }))
        }
        
        # Get existing connectors or create new array
        connectors = target_user.get('connectors', [])
        connectors.append(connector)
        
        # Update user with new connector
        users_table.update_item(
            Key={
                'user_id': user_id,
                'tenant_id': target_user['tenant_id']
            },
            UpdateExpression='SET connectors = :connectors',
            ExpressionAttributeValues={':connectors': connectors}
        )
        
        logger.info(f"Added connector {connector['connector_id']} to user {user_id}")
        
        return response(201, {
            'message': 'Connector added successfully',
            'connector': connector
        })
        
    except Exception as e:
        logger.error(f"Error creating connector: {str(e)}")
        return response(500, {'error': str(e)})

def list_connectors(event: Dict, user: Dict) -> Dict:
    """List connectors for a user"""
    try:
        user_id = event['pathParameters']['user_id']
        
        # Find user
        result = users_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        if not result.get('Items'):
            return response(404, {'error': 'User not found'})
        
        target_user = result['Items'][0]
        
        # Authorization check
        if not is_super_admin(user) and not is_reseller(user):
            if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
                return response(403, {'error': 'Unauthorized'})
        
        if is_reseller(user) and not can_reseller_access_tenant(user, target_user['tenant_id']):
            return response(403, {'error': 'Unauthorized'})
        
        connectors = target_user.get('connectors', [])
        
        # Backward compatibility: if old format (xml_endpoint on user), convert to connector
        if not connectors and target_user.get('xml_endpoint'):
            connectors = [{
                'connector_id': 'legacy',
                'name': 'Report Principale',
                'xml_endpoint': target_user.get('xml_endpoint', ''),
                'xml_token': target_user.get('xml_token', ''),
                'report_enabled': target_user.get('report_enabled', True),
                'report_schedule': target_user.get('report_schedule', json.dumps({
                    'frequency': 'daily',
                    'time': '09:00'
                }))
            }]
        
        return response(200, {'connectors': connectors})
        
    except Exception as e:
        logger.error(f"Error listing connectors: {str(e)}")
        return response(500, {'error': str(e)})

def update_connector(event: Dict, user: Dict) -> Dict:
    """Update connector for a user"""
    if not is_admin(user) and not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: Admin, Reseller, or SuperAdmin only'})
    
    try:
        user_id = event['pathParameters']['user_id']
        connector_id = event['pathParameters']['connector_id']
        
        # Find user
        result = users_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        if not result.get('Items'):
            return response(404, {'error': 'User not found'})
        
        target_user = result['Items'][0]
        
        # Authorization check
        if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
            return response(403, {'error': 'Unauthorized'})
        
        if is_reseller(user) and not can_reseller_access_tenant(user, target_user['tenant_id']):
            return response(403, {'error': 'Unauthorized'})
        
        body = json.loads(event.get('body', '{}'))
        
        # Get connectors
        connectors = target_user.get('connectors', [])
        
        # Find connector to update
        connector_index = None
        for i, conn in enumerate(connectors):
            if conn.get('connector_id') == connector_id:
                connector_index = i
                break
        
        if connector_index is None:
            return response(404, {'error': 'Connector not found'})
        
        # Update connector fields
        if 'name' in body:
            connectors[connector_index]['name'] = body['name']
        if 'xml_endpoint' in body:
            connectors[connector_index]['xml_endpoint'] = body['xml_endpoint']
        if 'xml_token' in body:
            connectors[connector_index]['xml_token'] = body.get('xml_token', '')
        if 'report_enabled' in body:
            connectors[connector_index]['report_enabled'] = body['report_enabled']
        if 'report_schedule' in body:
            connectors[connector_index]['report_schedule'] = body['report_schedule']
        
        # Update user
        users_table.update_item(
            Key={
                'user_id': user_id,
                'tenant_id': target_user['tenant_id']
            },
            UpdateExpression='SET connectors = :connectors',
            ExpressionAttributeValues={':connectors': connectors}
        )
        
        logger.info(f"Updated connector {connector_id} for user {user_id}")
        
        return response(200, {
            'message': 'Connector updated successfully',
            'connector': connectors[connector_index]
        })
        
    except Exception as e:
        logger.error(f"Error updating connector: {str(e)}")
        return response(500, {'error': str(e)})

def delete_connector(event: Dict, user: Dict) -> Dict:
    """Delete connector from user"""
    if not is_admin(user) and not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: Admin, Reseller, or SuperAdmin only'})
    
    try:
        user_id = event['pathParameters']['user_id']
        connector_id = event['pathParameters']['connector_id']
        
        # Find user
        result = users_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        if not result.get('Items'):
            return response(404, {'error': 'User not found'})
        
        target_user = result['Items'][0]
        
        # Authorization check
        if is_admin(user) and user['tenant_id'] != target_user['tenant_id']:
            return response(403, {'error': 'Unauthorized'})
        
        if is_reseller(user) and not can_reseller_access_tenant(user, target_user['tenant_id']):
            return response(403, {'error': 'Unauthorized'})
        
        # Get connectors
        connectors = target_user.get('connectors', [])
        
        # Remove connector
        connectors = [c for c in connectors if c.get('connector_id') != connector_id]
        
        if len(connectors) == len(target_user.get('connectors', [])):
            return response(404, {'error': 'Connector not found'})
        
        # Update user
        users_table.update_item(
            Key={
                'user_id': user_id,
                'tenant_id': target_user['tenant_id']
            },
            UpdateExpression='SET connectors = :connectors',
            ExpressionAttributeValues={':connectors': connectors}
        )
        
        logger.info(f"Deleted connector {connector_id} from user {user_id}")
        
        return response(200, {'message': 'Connector deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting connector: {str(e)}")
        return response(500, {'error': str(e)})

# ========================================
# TENANT MANAGEMENT
# ========================================

def create_tenant(event: Dict, user: Dict) -> Dict:
    """Create new tenant (SuperAdmin or Reseller) - Admin can be created separately"""
    if not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin or Reseller only'})
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields - ONLY name is required
        if not body.get('name'):
            return response(400, {'error': 'Missing required field: name'})
        
        tenant_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Create tenant record (without admin)
        tenant_item = {
            'tenant_id': tenant_id,
            'name': body['name'],
            'created_at': timestamp,
            'status': 'active'
        }
        
        tenants_table.put_item(Item=tenant_item)
        
        # If created by Reseller, automatically assign tenant to reseller
        if is_reseller(user):
            reseller_id = user['user_id']
            try:
                reseller_tenants_table.put_item(
                    Item={
                        'reseller_id': reseller_id,
                        'tenant_id': tenant_id,
                        'assigned_at': timestamp,
                        'assigned_by': 'self'  # Self-assigned by reseller
                    }
                )
                logger.info(f"Auto-assigned tenant {tenant_id} to reseller {reseller_id}")
            except Exception as e:
                logger.error(f"Error auto-assigning tenant to reseller: {str(e)}")
                # Don't fail the tenant creation if assignment fails
        
        logger.info(f"Created tenant {tenant_id} without admin")
        
        return response(201, {
            'message': 'Tenant created successfully',
            'tenant_id': tenant_id
        })
        
    except cognito.exceptions.UsernameExistsException:
        return response(400, {'error': 'User with this email already exists'})
    except Exception as e:
        logger.error(f"Error creating tenant: {str(e)}")
        return response(500, {'error': str(e)})

def list_tenants(user: Dict) -> Dict:
    """List tenants (SuperAdmin sees all, Reseller sees only assigned)"""
    if not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin or Reseller only'})
    
    try:
        if is_super_admin(user):
            # SuperAdmin sees all tenants
            result = tenants_table.scan()
            tenants = result.get('Items', [])
        else:
            # Reseller sees only assigned tenants
            reseller_id = user['user_id']
            assigned_tenant_ids = get_reseller_tenants(reseller_id)
            
            if not assigned_tenant_ids:
                return response(200, {'tenants': []})
            
            # Fetch tenant details for assigned tenants
            tenants = []
            for tenant_id in assigned_tenant_ids:
                try:
                    result = tenants_table.get_item(Key={'tenant_id': tenant_id})
                    if 'Item' in result:
                        tenants.append(result['Item'])
                except Exception as e:
                    logger.error(f"Error fetching tenant {tenant_id}: {str(e)}")
        
        return response(200, {'tenants': tenants})
        
    except Exception as e:
        logger.error(f"Error listing tenants: {str(e)}")
        return response(500, {'error': str(e)})

def get_tenant(event: Dict, user: Dict) -> Dict:
    """Get tenant details"""
    tenant_id = event['pathParameters']['tenant_id']
    
    # Authorization check
    if not is_super_admin(user) and not is_reseller(user):
        if not is_admin(user) or user['tenant_id'] != tenant_id:
            return response(403, {'error': 'Unauthorized'})
    elif is_reseller(user) and not can_reseller_access_tenant(user, tenant_id):
        return response(403, {'error': 'Unauthorized: Cannot access tenant not assigned to you'})
    
    try:
        result = tenants_table.get_item(Key={'tenant_id': tenant_id})
        
        if 'Item' not in result:
            return response(404, {'error': 'Tenant not found'})
        
        return response(200, {'tenant': result['Item']})
        
    except Exception as e:
        logger.error(f"Error getting tenant: {str(e)}")
        return response(500, {'error': str(e)})

def delete_tenant(event: Dict, user: Dict) -> Dict:
    """Delete tenant (SuperAdmin or Reseller only)"""
    if not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin or Reseller only'})
    
    try:
        tenant_id = event['pathParameters']['tenant_id']
        
        # Verify tenant exists
        tenant_result = tenants_table.get_item(Key={'tenant_id': tenant_id})
        if 'Item' not in tenant_result:
            return response(404, {'error': 'Tenant not found'})
        
        tenant = tenant_result['Item']
        
        # Authorization check - Reseller can only delete their assigned tenants
        if is_reseller(user) and not can_reseller_access_tenant(user, tenant_id):
            return response(403, {'error': 'Unauthorized: Cannot delete tenants not assigned to you'})
        
        # Get all users for this tenant
        users_result = users_table.query(
            IndexName='tenant-index',
            KeyConditionExpression='tenant_id = :tid',
            ExpressionAttributeValues={':tid': tenant_id}
        )
        
        users_to_delete = users_result.get('Items', [])
        
        # Delete all users from Cognito and DynamoDB
        for user_item in users_to_delete:
            try:
                # Delete from Cognito
                cognito.admin_delete_user(
                    UserPoolId=USER_POOL_ID,
                    Username=user_item['email']
                )
                
                # Delete from DynamoDB
                users_table.delete_item(
                    Key={
                        'user_id': user_item['user_id'],
                        'tenant_id': tenant_id
                    }
                )
                
                logger.info(f"Deleted user {user_item['user_id']} for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Error deleting user {user_item.get('user_id', 'unknown')}: {str(e)}")
                # Continue even if user deletion fails
        
        # Delete all tenant assignments from resellers
        if RESELLER_TENANTS_TABLE:
            try:
                # Query all reseller assignments for this tenant
                assignments_result = reseller_tenants_table.query(
                    IndexName='tenant-index',
                    KeyConditionExpression='tenant_id = :tid',
                    ExpressionAttributeValues={':tid': tenant_id}
                )
                
                assignments = assignments_result.get('Items', [])
                for assignment in assignments:
                    try:
                        reseller_tenants_table.delete_item(
                            Key={
                                'reseller_id': assignment['reseller_id'],
                                'tenant_id': tenant_id
                            }
                        )
                        logger.info(f"Removed tenant {tenant_id} assignment from reseller {assignment['reseller_id']}")
                    except Exception as e:
                        logger.error(f"Error removing tenant assignment: {str(e)}")
                        # Continue even if assignment deletion fails
            except Exception as e:
                logger.error(f"Error querying tenant assignments: {str(e)}")
                # Continue even if assignment query fails
        
        # Delete tenant from DynamoDB
        tenants_table.delete_item(Key={'tenant_id': tenant_id})
        
        logger.info(f"Deleted tenant {tenant_id}")
        
        return response(200, {'message': 'Tenant deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting tenant: {str(e)}")
        return response(500, {'error': str(e)})

def create_tenant_admin(event: Dict, user: Dict) -> Dict:
    """Create admin user for a tenant (SuperAdmin or Reseller only)"""
    if not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin or Reseller only'})
    
    try:
        tenant_id = event['pathParameters']['tenant_id']
        
        # Verify tenant exists
        tenant_result = tenants_table.get_item(Key={'tenant_id': tenant_id})
        if 'Item' not in tenant_result:
            return response(404, {'error': 'Tenant not found'})
        
        tenant = tenant_result['Item']
        
        # Check if tenant already has an admin
        if tenant.get('admin_email'):
            return response(400, {'error': 'Tenant already has an admin'})
        
        # Authorization check - Reseller can only manage their assigned tenants
        if is_reseller(user) and not can_reseller_access_tenant(user, tenant_id):
            return response(403, {'error': 'Unauthorized: Cannot manage tenants not assigned to you'})
        
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        required_fields = ['email', 'name', 'password']
        for field in required_fields:
            if not body.get(field):
                return response(400, {'error': f'Missing required field: {field}'})
        
        timestamp = datetime.utcnow().isoformat()
        
        # Create Cognito user for tenant admin
        cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=body['email'],
            UserAttributes=[
                {'Name': 'email', 'Value': body['email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:tenant_id', 'Value': tenant_id}
            ],
            TemporaryPassword=body['password'],
            MessageAction='SUPPRESS'
        )
        
        # Add to Admin group
        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID,
            Username=body['email'],
            GroupName='Admin'
        )
        
        # Set permanent password
        cognito.admin_set_user_password(
            UserPoolId=USER_POOL_ID,
            Username=body['email'],
            Password=body['password'],
            Permanent=True
        )
        
        # Get real UUID from Cognito
        admin_user_response = cognito.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=body['email']
        )
        
        real_user_id = None
        for attr in admin_user_response['UserAttributes']:
            if attr['Name'] == 'sub':
                real_user_id = attr['Value']
                break
        
        if not real_user_id:
            raise Exception('Could not extract user UUID from Cognito')
        
        # Update tenant record with admin info
        tenants_table.update_item(
            Key={'tenant_id': tenant_id},
            UpdateExpression='SET admin_email = :email, admin_name = :name',
            ExpressionAttributeValues={
                ':email': body['email'],
                ':name': body['name']
            }
        )
        
        # Create admin user record in DynamoDB
        admin_user_item = {
            'user_id': real_user_id,
            'tenant_id': tenant_id,
            'email': body['email'],
            'name': body['name'],
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
            'message': 'Admin created successfully for tenant',
            'tenant_id': tenant_id,
            'admin_user_id': real_user_id
        })
        
    except cognito.exceptions.UsernameExistsException:
        return response(400, {'error': 'User with this email already exists'})
    except Exception as e:
        logger.error(f"Error creating tenant admin: {str(e)}")
        return response(500, {'error': str(e)})

# ========================================
# RESELLER MANAGEMENT
# ========================================

def create_reseller(event: Dict, user: Dict) -> Dict:
    """Create new reseller user (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        required_fields = ['email', 'name', 'password']
        for field in required_fields:
            if not body.get(field):
                return response(400, {'error': f'Missing required field: {field}'})
        
        timestamp = datetime.utcnow().isoformat()
        
        # Create Cognito user for reseller with temporary password
        # The user will be required to change password on first login
        cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=body['email'],
            UserAttributes=[
                {'Name': 'email', 'Value': body['email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:tenant_id', 'Value': 'SYSTEM'}  # Reseller has SYSTEM tenant_id like SuperAdmin
            ],
            TemporaryPassword=body['password'],
            MessageAction='SUPPRESS'  # Don't send email, we'll provide password manually
        )
        
        # Create Reseller group if it doesn't exist, then add user to it
        try:
            # Try to get the group first
            cognito.get_group(
                UserPoolId=USER_POOL_ID,
                GroupName='Reseller'
            )
        except cognito.exceptions.ResourceNotFoundException:
            # Group doesn't exist, create it
            logger.info('Creating Reseller group in Cognito')
            cognito.create_group(
                UserPoolId=USER_POOL_ID,
                GroupName='Reseller',
                Description='Reseller users with admin privileges for assigned tenants'
            )
        
        # Add to Reseller group
        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID,
            Username=body['email'],
            GroupName='Reseller'
        )
        
        # NOTE: We do NOT set permanent password here
        # The user will be required to change password on first login
        # This is the standard Cognito flow for new users
        
        # Get real UUID from Cognito
        reseller_response = cognito.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=body['email']
        )
        
        real_user_id = None
        for attr in reseller_response['UserAttributes']:
            if attr['Name'] == 'sub':
                real_user_id = attr['Value']
                break
        
        if not real_user_id:
            raise Exception('Could not extract user UUID from Cognito')
        
        # Create reseller user record in DynamoDB
        reseller_user_item = {
            'user_id': real_user_id,
            'tenant_id': 'SYSTEM',  # Reseller has SYSTEM tenant_id
            'email': body['email'],
            'name': body['name'],
            'role': 'Reseller',
            'created_at': timestamp,
            'xml_endpoint': '',
            'xml_token': '',
            'report_enabled': False,
            'report_schedule': json.dumps({
                'frequency': 'daily',
                'time': '09:00'
            })
        }
        
        users_table.put_item(Item=reseller_user_item)
        
        logger.info(f"Created reseller user with UUID {real_user_id}")
        
        return response(201, {
            'message': 'Reseller created successfully',
            'reseller_id': real_user_id,
            'email': body['email'],
            'temporary_password': body['password'],  # Return password so SuperAdmin can provide it to reseller
            'note': 'User must change password on first login'
        })
        
    except cognito.exceptions.UsernameExistsException:
        return response(400, {'error': 'User with this email already exists'})
    except Exception as e:
        logger.error(f"Error creating reseller: {str(e)}")
        return response(500, {'error': str(e)})

def assign_tenant_to_reseller(event: Dict, user: Dict) -> Dict:
    """Assign tenant to reseller (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        if not body.get('reseller_id') or not body.get('tenant_id'):
            return response(400, {'error': 'Missing required fields: reseller_id, tenant_id'})
        
        reseller_id = body['reseller_id']
        tenant_id = body['tenant_id']
        
        # Verify tenant exists
        tenant_result = tenants_table.get_item(Key={'tenant_id': tenant_id})
        if 'Item' not in tenant_result:
            return response(404, {'error': 'Tenant not found'})
        
        # Verify reseller exists
        reseller_result = users_table.query(
            KeyConditionExpression='user_id = :uid AND tenant_id = :tid',
            ExpressionAttributeValues={
                ':uid': reseller_id,
                ':tid': 'SYSTEM'
            }
        )
        if not reseller_result.get('Items') or reseller_result['Items'][0].get('role') != 'Reseller':
            return response(404, {'error': 'Reseller not found'})
        
        # Check if already assigned
        if is_tenant_assigned_to_reseller(tenant_id, reseller_id):
            return response(400, {'error': 'Tenant already assigned to this reseller'})
        
        # Assign tenant to reseller
        timestamp = datetime.utcnow().isoformat()
        reseller_tenants_table.put_item(
            Item={
                'reseller_id': reseller_id,
                'tenant_id': tenant_id,
                'assigned_at': timestamp,
                'assigned_by': user['user_id']  # SuperAdmin who assigned
            }
        )
        
        logger.info(f"Assigned tenant {tenant_id} to reseller {reseller_id}")
        
        return response(200, {
            'message': 'Tenant assigned to reseller successfully',
            'reseller_id': reseller_id,
            'tenant_id': tenant_id
        })
        
    except Exception as e:
        logger.error(f"Error assigning tenant to reseller: {str(e)}")
        return response(500, {'error': str(e)})

def remove_tenant_from_reseller(event: Dict, user: Dict) -> Dict:
    """Remove tenant from reseller (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        if not body.get('reseller_id') or not body.get('tenant_id'):
            return response(400, {'error': 'Missing required fields: reseller_id, tenant_id'})
        
        reseller_id = body['reseller_id']
        tenant_id = body['tenant_id']
        
        # Check if assigned
        if not is_tenant_assigned_to_reseller(tenant_id, reseller_id):
            return response(404, {'error': 'Tenant not assigned to this reseller'})
        
        # Remove assignment
        reseller_tenants_table.delete_item(
            Key={
                'reseller_id': reseller_id,
                'tenant_id': tenant_id
            }
        )
        
        logger.info(f"Removed tenant {tenant_id} from reseller {reseller_id}")
        
        return response(200, {
            'message': 'Tenant removed from reseller successfully',
            'reseller_id': reseller_id,
            'tenant_id': tenant_id
        })
        
    except Exception as e:
        logger.error(f"Error removing tenant from reseller: {str(e)}")
        return response(500, {'error': str(e)})

def list_resellers(user: Dict) -> Dict:
    """List all resellers (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        # Query all users with role Reseller
        result = users_table.scan(
            FilterExpression='#role = :role',
            ExpressionAttributeNames={'#role': 'role'},
            ExpressionAttributeValues={':role': 'Reseller'}
        )
        
        resellers = result.get('Items', [])
        
        # For each reseller, get their assigned tenants
        for reseller in resellers:
            reseller_id = reseller['user_id']
            assigned_tenant_ids = get_reseller_tenants(reseller_id)
            reseller['assigned_tenants'] = assigned_tenant_ids
            reseller['assigned_tenants_count'] = len(assigned_tenant_ids)
        
        return response(200, {'resellers': resellers})
        
    except Exception as e:
        logger.error(f"Error listing resellers: {str(e)}")
        return response(500, {'error': str(e)})

def delete_reseller(event: Dict, user: Dict) -> Dict:
    """Delete reseller (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        reseller_id = event['pathParameters']['reseller_id']
        
        # Verify reseller exists
        reseller_result = users_table.query(
            KeyConditionExpression='user_id = :uid AND tenant_id = :tid',
            ExpressionAttributeValues={
                ':uid': reseller_id,
                ':tid': 'SYSTEM'
            }
        )
        
        if not reseller_result.get('Items'):
            return response(404, {'error': 'Reseller not found'})
        
        reseller = reseller_result['Items'][0]
        
        # Verify it's actually a reseller
        if reseller.get('role') != 'Reseller':
            return response(400, {'error': 'User is not a reseller'})
        
        # Delete all tenant assignments for this reseller
        if RESELLER_TENANTS_TABLE:
            assigned_tenant_ids = get_reseller_tenants(reseller_id)
            for tenant_id in assigned_tenant_ids:
                try:
                    reseller_tenants_table.delete_item(
                        Key={
                            'reseller_id': reseller_id,
                            'tenant_id': tenant_id
                        }
                    )
                except Exception as e:
                    logger.error(f"Error removing tenant assignment {tenant_id}: {str(e)}")
                    # Continue even if assignment deletion fails
        
        # Delete from Cognito
        cognito.admin_delete_user(
            UserPoolId=USER_POOL_ID,
            Username=reseller['email']
        )
        
        # Delete from DynamoDB
        users_table.delete_item(
            Key={
                'user_id': reseller_id,
                'tenant_id': 'SYSTEM'
            }
        )
        
        logger.info(f"Deleted reseller {reseller_id}")
        
        return response(200, {'message': 'Reseller deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting reseller: {str(e)}")
        return response(500, {'error': str(e)})

def dissociate_reseller(event: Dict, user: Dict) -> Dict:
    """Dissociate user from reseller role (remove from Reseller group but keep Cognito account) (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        reseller_id = event['pathParameters']['reseller_id']
        
        # Verify reseller exists
        reseller_result = users_table.query(
            KeyConditionExpression='user_id = :uid AND tenant_id = :tid',
            ExpressionAttributeValues={
                ':uid': reseller_id,
                ':tid': 'SYSTEM'
            }
        )
        
        if not reseller_result.get('Items'):
            return response(404, {'error': 'Reseller not found'})
        
        reseller = reseller_result['Items'][0]
        
        # Verify it's actually a reseller
        if reseller.get('role') != 'Reseller':
            return response(400, {'error': 'User is not a reseller'})
        
        # Remove from Reseller group in Cognito
        try:
            cognito.admin_remove_user_from_group(
                UserPoolId=USER_POOL_ID,
                Username=reseller['email'],
                GroupName='Reseller'
            )
            logger.info(f"Removed user {reseller['email']} from Reseller group in Cognito")
        except Exception as e:
            logger.warning(f"Could not remove user from Reseller group (may not be in group): {str(e)}")
        
        # Remove all tenant assignments for this reseller
        if RESELLER_TENANTS_TABLE:
            assigned_tenant_ids = get_reseller_tenants(reseller_id)
            for tenant_id in assigned_tenant_ids:
                try:
                    reseller_tenants_table.delete_item(
                        Key={
                            'reseller_id': reseller_id,
                            'tenant_id': tenant_id
                        }
                    )
                except Exception as e:
                    logger.error(f"Error removing tenant assignment {tenant_id}: {str(e)}")
        
        # Remove all organization associations
        if RESELLER_USER_ORGANIZATIONS_TABLE:
            try:
                # Scan and filter to find all organizations this user is associated with
                scan_result = reseller_user_organizations_table.scan(
                    FilterExpression='user_id = :uid',
                    ExpressionAttributeValues={':uid': reseller_id}
                )
                
                for item in scan_result.get('Items', []):
                    try:
                        reseller_user_organizations_table.delete_item(
                            Key={
                                'user_id': reseller_id,
                                'org_id': item['org_id']
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error removing organization association {item['org_id']}: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not remove organization associations: {str(e)}")
        
        # Delete from DynamoDB (user is no longer a reseller)
        users_table.delete_item(
            Key={
                'user_id': reseller_id,
                'tenant_id': 'SYSTEM'
            }
        )
        
        logger.info(f"Dissociated reseller {reseller_id} from reseller role")
        
        return response(200, {
            'message': 'Reseller dissociated successfully',
            'reseller_id': reseller_id,
            'email': reseller['email'],
            'note': 'User removed from Reseller group and all associations. Cognito account still exists but user cannot login without a role.'
        })
        
    except Exception as e:
        logger.error(f"Error dissociating reseller: {str(e)}")
        return response(500, {'error': str(e)})

def get_reseller_tenants_list(event: Dict, user: Dict) -> Dict:
    """Get list of tenants assigned to a reseller (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        reseller_id = event['pathParameters']['reseller_id']
        
        # Verify reseller exists
        reseller_result = users_table.query(
            KeyConditionExpression='user_id = :uid AND tenant_id = :tid',
            ExpressionAttributeValues={
                ':uid': reseller_id,
                ':tid': 'SYSTEM'
            }
        )
        if not reseller_result.get('Items') or reseller_result['Items'][0].get('role') != 'Reseller':
            return response(404, {'error': 'Reseller not found'})
        
        # Get assigned tenants
        assigned_tenant_ids = get_reseller_tenants(reseller_id)
        
        # Fetch tenant details
        tenants = []
        for tenant_id in assigned_tenant_ids:
            try:
                result = tenants_table.get_item(Key={'tenant_id': tenant_id})
                if 'Item' in result:
                    tenants.append(result['Item'])
            except Exception as e:
                logger.error(f"Error fetching tenant {tenant_id}: {str(e)}")
        
        return response(200, {
            'reseller_id': reseller_id,
            'tenants': tenants,
            'count': len(tenants)
        })
        
    except Exception as e:
        logger.error(f"Error getting reseller tenants: {str(e)}")
        return response(500, {'error': str(e)})

# ========================================
# RESELLER ORGANIZATIONS MANAGEMENT
# ========================================
def create_reseller_organization(event: Dict, user: Dict) -> Dict:
    """Create new reseller organization (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    if not RESELLER_ORGANIZATIONS_TABLE:
        return response(500, {'error': 'Reseller organizations table not configured'})
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        if not body.get('name'):
            return response(400, {'error': 'Missing required field: name'})
        
        # Generate organization ID
        org_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Create organization record
        org_item = {
            'org_id': org_id,
            'name': body['name'],
            'description': body.get('description', ''),
            'created_at': timestamp,
            'created_by': user['user_id']
        }
        
        reseller_organizations_table.put_item(Item=org_item)
        
        logger.info(f"Created reseller organization {org_id}")
        
        return response(201, {
            'message': 'Reseller organization created successfully',
            'organization': org_item
        })
        
    except Exception as e:
        logger.error(f"Error creating reseller organization: {str(e)}")
        return response(500, {'error': str(e)})

def list_reseller_organizations(user: Dict) -> Dict:
    """List all reseller organizations (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    if not RESELLER_ORGANIZATIONS_TABLE:
        return response(500, {'error': 'Reseller organizations table not configured'})
    
    try:
        result = reseller_organizations_table.scan()
        organizations = result.get('Items', [])
        
        # For each organization, get associated users and tenants
        for org in organizations:
            org_id = org['org_id']
            
            # Get associated users
            if RESELLER_USER_ORGANIZATIONS_TABLE:
                users_result = reseller_user_organizations_table.query(
                    IndexName='org-index',
                    KeyConditionExpression='org_id = :oid',
                    ExpressionAttributeValues={':oid': org_id}
                )
                org['users'] = [item['user_id'] for item in users_result.get('Items', [])]
                org['users_count'] = len(org['users'])
            else:
                org['users'] = []
                org['users_count'] = 0
            
            # Get assigned tenants
            if RESELLER_ORG_TENANTS_TABLE:
                tenants_result = reseller_org_tenants_table.query(
                    KeyConditionExpression='reseller_org_id = :oid',
                    ExpressionAttributeValues={':oid': org_id}
                )
                org['tenants'] = [item['tenant_id'] for item in tenants_result.get('Items', [])]
                org['tenants_count'] = len(org['tenants'])
            else:
                org['tenants'] = []
                org['tenants_count'] = 0
            org['tenants'] = [item['tenant_id'] for item in tenants_result.get('Items', [])]
            org['tenants_count'] = len(org['tenants'])
        
        return response(200, {'organizations': organizations})
        
    except Exception as e:
        logger.error(f"Error listing reseller organizations: {str(e)}")
        return response(500, {'error': str(e)})

def delete_reseller_organization(event: Dict, user: Dict) -> Dict:
    """Delete reseller organization (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    if not RESELLER_ORGANIZATIONS_TABLE:
        return response(500, {'error': 'Reseller organizations table not configured'})
    
    try:
        org_id = event['pathParameters']['org_id']
        
        # Verify organization exists
        org_result = reseller_organizations_table.get_item(Key={'org_id': org_id})
        if 'Item' not in org_result:
            return response(404, {'error': 'Organization not found'})
        
        # Delete all user associations
        if RESELLER_USER_ORGANIZATIONS_TABLE:
            users_result = reseller_user_organizations_table.query(
                IndexName='org-index',
                KeyConditionExpression='org_id = :oid',
                ExpressionAttributeValues={':oid': org_id}
            )
            for item in users_result.get('Items', []):
                reseller_user_organizations_table.delete_item(
                    Key={
                        'user_id': item['user_id'],
                        'org_id': org_id
                    }
                )
        
        # Delete all tenant assignments
        if RESELLER_ORG_TENANTS_TABLE:
            tenants_result = reseller_org_tenants_table.query(
                KeyConditionExpression='reseller_org_id = :oid',
                ExpressionAttributeValues={':oid': org_id}
            )
            for item in tenants_result.get('Items', []):
                reseller_org_tenants_table.delete_item(
                    Key={
                        'reseller_org_id': org_id,
                        'tenant_id': item['tenant_id']
                    }
                )
        
        # Delete organization
        reseller_organizations_table.delete_item(Key={'org_id': org_id})
        
        logger.info(f"Deleted reseller organization {org_id}")
        
        return response(200, {'message': 'Reseller organization deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting reseller organization: {str(e)}")
        return response(500, {'error': str(e)})

def add_user_to_reseller_organization(event: Dict, user: Dict) -> Dict:
    """Add reseller user to organization (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    if not RESELLER_ORGANIZATIONS_TABLE or not RESELLER_USER_ORGANIZATIONS_TABLE:
        return response(500, {'error': 'Reseller organizations tables not configured'})
    
    try:
        org_id = event['pathParameters']['org_id']
        body = json.loads(event.get('body', '{}'))
        
        if not body.get('user_id'):
            return response(400, {'error': 'Missing required field: user_id'})
        
        user_id = body['user_id']
        
        # Verify organization exists
        org_result = reseller_organizations_table.get_item(Key={'org_id': org_id})
        if 'Item' not in org_result:
            return response(404, {'error': 'Organization not found'})
        
        # Verify user exists and is a Reseller
        user_result = users_table.query(
            KeyConditionExpression='user_id = :uid AND tenant_id = :tid',
            ExpressionAttributeValues={
                ':uid': user_id,
                ':tid': 'SYSTEM'
            }
        )
        if not user_result.get('Items') or user_result['Items'][0].get('role') != 'Reseller':
            return response(404, {'error': 'Reseller user not found'})
        
        # Check if already associated
        try:
            existing = reseller_user_organizations_table.get_item(
                Key={
                    'user_id': user_id,
                    'org_id': org_id
                }
            )
            if 'Item' in existing:
                return response(400, {'error': 'User already associated with this organization'})
        except:
            pass
        
        # Add association
        timestamp = datetime.utcnow().isoformat()
        reseller_user_organizations_table.put_item(
            Item={
                'user_id': user_id,
                'org_id': org_id,
                'associated_at': timestamp,
                'associated_by': user['user_id']
            }
        )
        
        logger.info(f"Added user {user_id} to organization {org_id}")
        
        return response(200, {
            'message': 'User added to organization successfully',
            'user_id': user_id,
            'org_id': org_id
        })
        
    except Exception as e:
        logger.error(f"Error adding user to organization: {str(e)}")
        return response(500, {'error': str(e)})

def remove_user_from_reseller_organization(event: Dict, user: Dict) -> Dict:
    """Remove reseller user from organization (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    if not RESELLER_USER_ORGANIZATIONS_TABLE:
        return response(500, {'error': 'Reseller user organizations table not configured'})
    
    try:
        org_id = event['pathParameters']['org_id']
        user_id = event['pathParameters']['user_id']
        
        # Remove association
        reseller_user_organizations_table.delete_item(
            Key={
                'user_id': user_id,
                'org_id': org_id
            }
        )
        
        logger.info(f"Removed user {user_id} from organization {org_id}")
        
        return response(200, {
            'message': 'User removed from organization successfully',
            'user_id': user_id,
            'org_id': org_id
        })
        
    except Exception as e:
        logger.error(f"Error removing user from organization: {str(e)}")
        return response(500, {'error': str(e)})

def assign_tenant_to_reseller_organization(event: Dict, user: Dict) -> Dict:
    """Assign tenant to reseller organization (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    if not RESELLER_ORGANIZATIONS_TABLE or not RESELLER_ORG_TENANTS_TABLE:
        return response(500, {'error': 'Reseller organizations tables not configured'})
    
    try:
        org_id = event['pathParameters']['org_id']
        body = json.loads(event.get('body', '{}'))
        
        if not body.get('tenant_id'):
            return response(400, {'error': 'Missing required field: tenant_id'})
        
        tenant_id = body['tenant_id']
        
        # Verify organization exists
        org_result = reseller_organizations_table.get_item(Key={'org_id': org_id})
        if 'Item' not in org_result:
            return response(404, {'error': 'Organization not found'})
        
        # Verify tenant exists
        tenant_result = tenants_table.get_item(Key={'tenant_id': tenant_id})
        if 'Item' not in tenant_result:
            return response(404, {'error': 'Tenant not found'})
        
        # Check if already assigned
        try:
            existing = reseller_org_tenants_table.get_item(
                Key={
                    'reseller_org_id': org_id,
                    'tenant_id': tenant_id
                }
            )
            if 'Item' in existing:
                return response(400, {'error': 'Tenant already assigned to this organization'})
        except:
            pass
        
        # Assign tenant
        timestamp = datetime.utcnow().isoformat()
        reseller_org_tenants_table.put_item(
            Item={
                'reseller_org_id': org_id,
                'tenant_id': tenant_id,
                'assigned_at': timestamp,
                'assigned_by': user['user_id']
            }
        )
        
        logger.info(f"Assigned tenant {tenant_id} to organization {org_id}")
        
        return response(200, {
            'message': 'Tenant assigned to organization successfully',
            'org_id': org_id,
            'tenant_id': tenant_id
        })
        
    except Exception as e:
        logger.error(f"Error assigning tenant to organization: {str(e)}")
        return response(500, {'error': str(e)})

def remove_tenant_from_reseller_organization(event: Dict, user: Dict) -> Dict:
    """Remove tenant from reseller organization (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    if not RESELLER_ORG_TENANTS_TABLE:
        return response(500, {'error': 'Reseller org tenants table not configured'})
    
    try:
        org_id = event['pathParameters']['org_id']
        body = json.loads(event.get('body', '{}'))
        
        if not body.get('tenant_id'):
            return response(400, {'error': 'Missing required field: tenant_id'})
        
        tenant_id = body['tenant_id']
        
        # Remove assignment
        reseller_org_tenants_table.delete_item(
            Key={
                'reseller_org_id': org_id,
                'tenant_id': tenant_id
            }
        )
        
        logger.info(f"Removed tenant {tenant_id} from organization {org_id}")
        
        return response(200, {
            'message': 'Tenant removed from organization successfully',
            'org_id': org_id,
            'tenant_id': tenant_id
        })
        
    except Exception as e:
        logger.error(f"Error removing tenant from organization: {str(e)}")
        return response(500, {'error': str(e)})

# ========================================
# SUPERADMIN MANAGEMENT
# ========================================

def create_superadmin(event: Dict, user: Dict) -> Dict:
    """Create new superadmin user (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        required_fields = ['email', 'name', 'password']
        for field in required_fields:
            if not body.get(field):
                return response(400, {'error': f'Missing required field: {field}'})
        
        timestamp = datetime.utcnow().isoformat()
        
        # Create Cognito user for superadmin with temporary password
        # The user will be required to change password on first login
        cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=body['email'],
            UserAttributes=[
                {'Name': 'email', 'Value': body['email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:tenant_id', 'Value': 'SYSTEM'}  # SuperAdmin has SYSTEM tenant_id
            ],
            TemporaryPassword=body['password'],
            MessageAction='SUPPRESS'  # Don't send email, we'll provide password manually
        )
        
        # Create SuperAdmin group if it doesn't exist, then add user to it
        try:
            # Try to get the group first
            cognito.get_group(
                UserPoolId=USER_POOL_ID,
                GroupName='SuperAdmin'
            )
        except cognito.exceptions.ResourceNotFoundException:
            # Group doesn't exist, create it
            logger.info('Creating SuperAdmin group in Cognito')
            cognito.create_group(
                UserPoolId=USER_POOL_ID,
                GroupName='SuperAdmin',
                Description='SuperAdmin users with full system privileges'
            )
        
        # Add to SuperAdmin group
        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID,
            Username=body['email'],
            GroupName='SuperAdmin'
        )
        
        # NOTE: We do NOT set permanent password here
        # The user will be required to change password on first login
        # This is the standard Cognito flow for new users
        
        # Get real UUID from Cognito
        superadmin_response = cognito.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=body['email']
        )
        
        real_user_id = None
        for attr in superadmin_response['UserAttributes']:
            if attr['Name'] == 'sub':
                real_user_id = attr['Value']
                break
        
        if not real_user_id:
            raise Exception('Could not extract user UUID from Cognito')
        
        # Create superadmin user record in DynamoDB
        superadmin_user_item = {
            'user_id': real_user_id,
            'tenant_id': 'SYSTEM',  # SuperAdmin has SYSTEM tenant_id
            'email': body['email'],
            'name': body['name'],
            'role': 'SuperAdmin',
            'created_at': timestamp,
            'xml_endpoint': '',
            'xml_token': '',
            'report_enabled': False,
            'report_schedule': json.dumps({
                'frequency': 'daily',
                'time': '09:00'
            })
        }
        
        users_table.put_item(Item=superadmin_user_item)
        
        logger.info(f"Created superadmin user with UUID {real_user_id}")
        
        return response(201, {
            'message': 'SuperAdmin created successfully',
            'superadmin_id': real_user_id,
            'email': body['email'],
            'temporary_password': body['password'],  # Return password so SuperAdmin can provide it to new superadmin
            'note': 'User must change password on first login'
        })
        
    except cognito.exceptions.UsernameExistsException:
        return response(400, {'error': 'User with this email already exists'})
    except Exception as e:
        logger.error(f"Error creating superadmin: {str(e)}")
        return response(500, {'error': str(e)})

def list_superadmins(user: Dict) -> Dict:
    """List all superadmins (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        # Query all users with role SuperAdmin
        result = users_table.scan(
            FilterExpression='#role = :role',
            ExpressionAttributeNames={'#role': 'role'},
            ExpressionAttributeValues={':role': 'SuperAdmin'}
        )
        
        superadmins = result.get('Items', [])
        
        # For superadmins without created_at, try to get it from Cognito
        for superadmin in superadmins:
            if not superadmin.get('created_at'):
                try:
                    cognito_user = cognito.admin_get_user(
                        UserPoolId=USER_POOL_ID,
                        Username=superadmin['email']
                    )
                    # UserCreateDate is a datetime object from Cognito
                    if 'UserCreateDate' in cognito_user:
                        created_date = cognito_user['UserCreateDate']
                        # Convert to ISO format string
                        if hasattr(created_date, 'isoformat'):
                            created_at_str = created_date.isoformat()
                        else:
                            created_at_str = created_date.strftime('%Y-%m-%dT%H:%M:%S.%f')
                        
                        # Update in DynamoDB for future requests
                        try:
                            users_table.update_item(
                                Key={
                                    'user_id': superadmin['user_id'],
                                    'tenant_id': superadmin['tenant_id']
                                },
                                UpdateExpression='SET created_at = :ca',
                                ExpressionAttributeValues={':ca': created_at_str}
                            )
                        except Exception as e:
                            logger.warning(f"Could not update created_at for superadmin {superadmin['user_id']}: {str(e)}")
                        
                        # Set it in the response
                        superadmin['created_at'] = created_at_str
                except Exception as e:
                    logger.warning(f"Could not get creation date from Cognito for {superadmin['email']}: {str(e)}")
                    # Leave it as None if we can't get it
        
        # Filter out hidden superadmin (emiliano.menichelli@neuralect.it)
        # This superadmin should remain invisible to everyone, including other superadmins
        HIDDEN_SUPERADMIN_EMAIL = 'emiliano.menichelli@neuralect.it'
        superadmins = [sa for sa in superadmins if sa.get('email', '').lower() != HIDDEN_SUPERADMIN_EMAIL.lower()]
        
        return response(200, {'superadmins': superadmins})
        
    except Exception as e:
        logger.error(f"Error listing superadmins: {str(e)}")
        return response(500, {'error': str(e)})

def delete_superadmin(event: Dict, user: Dict) -> Dict:
    """Delete superadmin (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        superadmin_id = event['pathParameters']['superadmin_id']
        
        # Prevent self-deletion
        if user['user_id'] == superadmin_id:
            return response(400, {'error': 'Cannot delete yourself'})
        
        # Verify superadmin exists
        superadmin_result = users_table.query(
            KeyConditionExpression='user_id = :uid AND tenant_id = :tid',
            ExpressionAttributeValues={
                ':uid': superadmin_id,
                ':tid': 'SYSTEM'
            }
        )
        
        if not superadmin_result.get('Items'):
            return response(404, {'error': 'SuperAdmin not found'})
        
        superadmin = superadmin_result['Items'][0]
        
        # Verify it's actually a superadmin
        if superadmin.get('role') != 'SuperAdmin':
            return response(400, {'error': 'User is not a superadmin'})
        
        # Delete from Cognito
        cognito.admin_delete_user(
            UserPoolId=USER_POOL_ID,
            Username=superadmin['email']
        )
        
        # Delete from DynamoDB
        users_table.delete_item(
            Key={
                'user_id': superadmin_id,
                'tenant_id': 'SYSTEM'
            }
        )
        
        logger.info(f"Deleted superadmin {superadmin_id}")
        
        return response(200, {'message': 'SuperAdmin deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting superadmin: {str(e)}")
        return response(500, {'error': str(e)})

# ========================================
# REPORTS MANAGEMENT
# ========================================

def list_all_reports(user: Dict) -> Dict:
    """List all reports across all tenants (SuperAdmin only)"""
    if not is_super_admin(user):
        return response(403, {'error': 'Unauthorized: SuperAdmin only'})
    
    try:
        if not REPORTS_TABLE:
            return response(200, {'reports': []})
        
        # Scan all reports
        result = reports_table.scan()
        reports = result.get('Items', [])
        
        # Sort by timestamp descending
        reports.sort(key=lambda x: x.get('report_timestamp', ''), reverse=True)
        
        return response(200, {'reports': reports})
        
    except Exception as e:
        logger.error(f"Error listing all reports: {str(e)}")
        return response(500, {'error': str(e)})

def list_tenant_reports(event: Dict, user: Dict) -> Dict:
    """List reports for a specific tenant (Admin or Reseller)"""
    if not is_admin(user) and not is_super_admin(user) and not is_reseller(user):
        return response(403, {'error': 'Unauthorized: Admin, Reseller, or SuperAdmin only'})
    
    try:
        tenant_id = event['pathParameters']['tenant_id']
        
        # Authorization check
        if is_admin(user) and user['tenant_id'] != tenant_id:
            return response(403, {'error': 'Unauthorized: Cannot access other tenants'})
        
        if is_reseller(user) and not can_reseller_access_tenant(user, tenant_id):
            return response(403, {'error': 'Unauthorized: Cannot access tenants not assigned to you'})
        
        if not REPORTS_TABLE:
            return response(200, {'reports': []})
        
        # Query reports by tenant_id using GSI (if exists) or scan and filter
        # Note: This assumes reports have a tenant_id field
        # If using GSI, would be: reports_table.query(IndexName='tenant-index', ...)
        result = reports_table.scan(
            FilterExpression='tenant_id = :tid',
            ExpressionAttributeValues={':tid': tenant_id}
        )
        
        reports = result.get('Items', [])
        reports.sort(key=lambda x: x.get('report_timestamp', ''), reverse=True)
        
        return response(200, {'reports': reports})
        
    except Exception as e:
        logger.error(f"Error listing tenant reports: {str(e)}")
        return response(500, {'error': str(e)})

def list_user_reports(event: Dict, user: Dict) -> Dict:
    """List reports for a specific user"""
    try:
        user_id = event['pathParameters']['user_id']
        
        # Authorization check
        if not is_super_admin(user) and not is_reseller(user):
            if is_admin(user):
                # Admin can see reports of users in their tenant
                target_user_result = users_table.query(
                    KeyConditionExpression='user_id = :uid',
                    ExpressionAttributeValues={':uid': user_id}
                )
                if not target_user_result.get('Items'):
                    return response(404, {'error': 'User not found'})
                target_user = target_user_result['Items'][0]
                if user['tenant_id'] != target_user['tenant_id']:
                    return response(403, {'error': 'Unauthorized'})
            else:
                # Regular user can only see their own reports
                if user['user_id'] != user_id:
                    return response(403, {'error': 'Unauthorized'})
        elif is_reseller(user):
            # Reseller can see reports of users in their assigned tenants
            target_user_result = users_table.query(
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
            if not target_user_result.get('Items'):
                return response(404, {'error': 'User not found'})
            target_user = target_user_result['Items'][0]
            if not can_reseller_access_tenant(user, target_user['tenant_id']):
                return response(403, {'error': 'Unauthorized: Cannot access users from tenants not assigned to you'})
        
        if not REPORTS_TABLE:
            return response(200, {'reports': []})
        
        # Query reports by user_id
        result = reports_table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        reports = result.get('Items', [])
        reports.sort(key=lambda x: x.get('report_timestamp', ''), reverse=True)
        
        return response(200, {'reports': reports})
        
    except Exception as e:
        logger.error(f"Error listing user reports: {str(e)}")
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
            # Extract tenant_id from path like /tenants/{tenant_id}/users
            path_parts = path.split('/')
            if len(path_parts) >= 4 and path_parts[1] == 'tenants' and path_parts[3] == 'users':
                tenant_id = path_parts[2]
                # Add tenant_id to pathParameters for the function
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['tenant_id'] = tenant_id
            if method == 'POST':
                return create_user(event, user)
            elif method == 'GET':
                return list_users(event, user)
        
        elif path.startswith('/tenants/') and path.endswith('/admin'):
            if method == 'POST':
                return create_tenant_admin(event, user)
        
        elif path.startswith('/tenants/') and path.endswith('/reports'):
            if method == 'GET':
                return list_tenant_reports(event, user)
        
        elif path.startswith('/tenants/') and '/users' not in path and '/reports' not in path and not path.endswith('/admin'):
            # Extract tenant_id from path like /tenants/{tenant_id}
            path_parts = path.split('/')
            if len(path_parts) >= 3 and path_parts[1] == 'tenants':
                tenant_id = path_parts[2]
                # Add tenant_id to pathParameters for the function
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['tenant_id'] = tenant_id
            if method == 'GET':
                return get_tenant(event, user)
            elif method == 'DELETE':
                return delete_tenant(event, user)
        
        elif path.startswith('/users/') and path.endswith('/reports'):
            if method == 'GET':
                return list_user_reports(event, user)
        
        elif path.startswith('/users/') and '/connectors/' in path and not path.endswith('/connectors'):
            # Extract user_id and connector_id from path like /users/{user_id}/connectors/{connector_id}
            path_parts = path.split('/')
            if len(path_parts) >= 5 and path_parts[1] == 'users' and path_parts[3] == 'connectors':
                user_id = path_parts[2]
                connector_id = path_parts[4]
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['user_id'] = user_id
                event['pathParameters']['connector_id'] = connector_id
                if method == 'PUT':
                    return update_connector(event, user)
                elif method == 'DELETE':
                    return delete_connector(event, user)
        
        elif path.startswith('/users/') and path.endswith('/connectors'):
            # Extract user_id from path like /users/{user_id}/connectors
            path_parts = path.split('/')
            if len(path_parts) >= 4 and path_parts[1] == 'users' and path_parts[3] == 'connectors':
                user_id = path_parts[2]
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['user_id'] = user_id
                if method == 'POST':
                    return create_connector(event, user)
                elif method == 'GET':
                    return list_connectors(event, user)
        
        elif path.startswith('/users/') and not path.endswith('/reports') and '/connectors' not in path:
            if method == 'GET':
                return get_user(event, user)
            elif method == 'PUT':
                return update_user(event, user)
            elif method == 'DELETE':
                return delete_user(event, user)
        
        elif path == '/reports':
            if method == 'GET':
                return list_all_reports(user)
        
        elif path == '/profile':
            if method == 'GET':
                return get_profile(user)
            elif method == 'PUT':
                return update_profile(event, user)
        
        elif path == '/resellers':
            if method == 'POST':
                return create_reseller(event, user)
            elif method == 'GET':
                return list_resellers(user)
        
        elif '/resellers/' in path and '/dissociate' in path:
            # Extract reseller_id from path like /resellers/{reseller_id}/dissociate
            path_parts = path.split('/')
            if len(path_parts) >= 4 and path_parts[1] == 'resellers' and path_parts[3] == 'dissociate':
                reseller_id = path_parts[2]
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['reseller_id'] = reseller_id
                if method == 'POST':
                    return dissociate_reseller(event, user)
        
        elif '/resellers/' in path and not '/tenants' in path and not '/assign-tenant' in path and not '/remove-tenant' in path and not '/dissociate' in path:
            # Extract reseller_id from path like /resellers/{reseller_id}
            path_parts = path.split('/')
            if len(path_parts) >= 3 and path_parts[1] == 'resellers':
                reseller_id = path_parts[2]
                # Add reseller_id to pathParameters for the function
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['reseller_id'] = reseller_id
                if method == 'DELETE':
                    return delete_reseller(event, user)
        
        elif path == '/resellers/assign-tenant':
            if method == 'POST':
                return assign_tenant_to_reseller(event, user)
        
        elif path == '/resellers/remove-tenant':
            if method == 'POST':
                return remove_tenant_from_reseller(event, user)
        
        elif '/resellers/' in path and '/tenants' in path:
            # Extract reseller_id from path like /resellers/{reseller_id}/tenants
            path_parts = path.split('/')
            if len(path_parts) >= 4 and path_parts[1] == 'resellers' and path_parts[3] == 'tenants':
                reseller_id = path_parts[2]
                # Add reseller_id to pathParameters for the function
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['reseller_id'] = reseller_id
                if method == 'GET':
                    return get_reseller_tenants_list(event, user)
        
        # Reseller Organizations endpoints
        elif path == '/reseller-organizations':
            if method == 'POST':
                return create_reseller_organization(event, user)
            elif method == 'GET':
                return list_reseller_organizations(user)
        
        elif path.startswith('/reseller-organizations/') and '/users/' in path and not path.endswith('/users'):
            # Extract org_id and user_id from path like /reseller-organizations/{org_id}/users/{user_id}
            path_parts = path.split('/')
            if len(path_parts) >= 5 and path_parts[1] == 'reseller-organizations' and path_parts[3] == 'users':
                org_id = path_parts[2]
                user_id = path_parts[4]
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['org_id'] = org_id
                event['pathParameters']['user_id'] = user_id
                if method == 'DELETE':
                    return remove_user_from_reseller_organization(event, user)
        
        elif path.startswith('/reseller-organizations/') and path.endswith('/users'):
            # Extract org_id from path like /reseller-organizations/{org_id}/users
            path_parts = path.split('/')
            if len(path_parts) >= 4 and path_parts[1] == 'reseller-organizations' and path_parts[3] == 'users':
                org_id = path_parts[2]
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['org_id'] = org_id
                if method == 'POST':
                    return add_user_to_reseller_organization(event, user)
        
        elif path.startswith('/reseller-organizations/') and '/assign-tenant' in path:
            # Extract org_id from path like /reseller-organizations/{org_id}/assign-tenant
            path_parts = path.split('/')
            if len(path_parts) >= 4 and path_parts[1] == 'reseller-organizations' and path_parts[3] == 'assign-tenant':
                org_id = path_parts[2]
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['org_id'] = org_id
                if method == 'POST':
                    return assign_tenant_to_reseller_organization(event, user)
        
        elif path.startswith('/reseller-organizations/') and '/remove-tenant' in path:
            # Extract org_id from path like /reseller-organizations/{org_id}/remove-tenant
            path_parts = path.split('/')
            if len(path_parts) >= 4 and path_parts[1] == 'reseller-organizations' and path_parts[3] == 'remove-tenant':
                org_id = path_parts[2]
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['org_id'] = org_id
                if method == 'POST':
                    return remove_tenant_from_reseller_organization(event, user)
        
        elif path.startswith('/reseller-organizations/') and not '/users' in path and not '/assign-tenant' in path and not '/remove-tenant' in path:
            # Extract org_id from path like /reseller-organizations/{org_id}
            path_parts = path.split('/')
            if len(path_parts) >= 3 and path_parts[1] == 'reseller-organizations':
                org_id = path_parts[2]
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['org_id'] = org_id
                if method == 'DELETE':
                    return delete_reseller_organization(event, user)
        
        elif path == '/superadmins':
            if method == 'POST':
                return create_superadmin(event, user)
            elif method == 'GET':
                return list_superadmins(user)
        
        elif '/superadmins/' in path:
            # Extract superadmin_id from path like /superadmins/{superadmin_id}
            path_parts = path.split('/')
            if len(path_parts) >= 3 and path_parts[1] == 'superadmins':
                superadmin_id = path_parts[2]
                # Add superadmin_id to pathParameters for the function
                if 'pathParameters' not in event:
                    event['pathParameters'] = {}
                event['pathParameters']['superadmin_id'] = superadmin_id
                if method == 'DELETE':
                    return delete_superadmin(event, user)
        
        return response(404, {'error': 'Not found'})
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return response(500, {'error': str(e)})