import json
import boto3
import os
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
ses_client = boto3.client('ses', region_name=os.environ['REGION'])
dynamodb = boto3.resource('dynamodb')

# Environment variables
REGION = os.environ['REGION']
SES_FROM_EMAIL = os.environ['SES_FROM_EMAIL']
REPORTS_TABLE = os.environ['REPORTS_TABLE']

# DynamoDB table
reports_table = dynamodb.Table(REPORTS_TABLE)

def send_html_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send HTML email via Amazon SES with proper UTF-8 encoding"""
    try:
        logger.info(f"Sending email to: {to_email}")
        
        # CRITICAL FIX: Ensure all content is properly encoded as UTF-8
        # Clean and normalize content
        subject_clean = subject.encode('utf-8', errors='ignore').decode('utf-8')
        html_content_clean = html_content.encode('utf-8', errors='ignore').decode('utf-8')
        
        # Create message with explicit UTF-8 encoding
        response = ses_client.send_email(
            Source=SES_FROM_EMAIL,
            Destination={
                'ToAddresses': [to_email]
            },
            Message={
                'Subject': {
                    'Data': subject_clean,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': html_content_clean,
                        'Charset': 'UTF-8'
                    },
                    'Text': {
                        'Data': strip_html_tags(html_content_clean),
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        
        message_id = response['MessageId']
        logger.info(f"Email sent successfully. MessageId: {message_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise

def strip_html_tags(html_text: str) -> str:
    """Strip HTML tags to create plain text version with proper UTF-8 handling"""
    import re
    
    # Ensure input is UTF-8
    if isinstance(html_text, bytes):
        html_text = html_text.decode('utf-8', errors='ignore')
    
    # Clean HTML tags
    clean = re.compile('<.*?>')
    text_content = re.sub(clean, '', html_text)
    
    # Replace common HTML entities with proper UTF-8 characters
    entity_map = {
        '&nbsp;': ' ',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&apos;': "'",
        '&euro;': '€',
        '&copy;': '©',
        '&reg;': '®',
        '&trade;': '™',
        # Italian specific
        '&agrave;': 'à',
        '&egrave;': 'è',
        '&igrave;': 'ì',
        '&ograve;': 'ò',
        '&ugrave;': 'ù',
        '&Agrave;': 'À',
        '&Egrave;': 'È',
        '&Igrave;': 'Ì',
        '&Ograve;': 'Ò',
        '&Ugrave;': 'Ù',
        '&#8364;': '€',
        '&#8482;': '™',
        '&#169;': '©'
    }
    
    for entity, char in entity_map.items():
        text_content = text_content.replace(entity, char)
    
    # Clean up extra whitespace while preserving UTF-8
    text_content = ' '.join(text_content.split())
    
    # Ensure final output is proper UTF-8
    return text_content.encode('utf-8', errors='ignore').decode('utf-8')

def update_report_status(user_id: str, status: str, error_msg: str = None):
    """Update report status in history"""
    try:
        timestamp = datetime.utcnow().isoformat()
        
        item = {
            'user_id': user_id,
            'report_timestamp': timestamp,
            'sent_at': timestamp,
            'status': status
        }
        
        if error_msg:
            # Ensure error message is UTF-8 safe
            item['error_message'] = str(error_msg).encode('utf-8', errors='ignore').decode('utf-8')
        
        reports_table.put_item(Item=item)
        logger.info(f"Report status updated for user {user_id}: {status}")
        
    except Exception as e:
        logger.error(f"Error updating report status: {str(e)}")

def validate_email_data(data: dict) -> tuple:
    """Validate required email fields with UTF-8 safety"""
    to_email = data.get('to_email')
    subject = data.get('subject')
    html_content = data.get('html_content')
    
    if not to_email:
        raise ValueError("Missing required field: to_email")
    if not subject:
        raise ValueError("Missing required field: subject")
    if not html_content:
        raise ValueError("Missing required field: html_content")
    
    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, to_email):
        raise ValueError(f"Invalid email format: {to_email}")
    
    # Ensure all data is UTF-8 safe
    subject_safe = str(subject).encode('utf-8', errors='ignore').decode('utf-8')
    html_content_safe = str(html_content).encode('utf-8', errors='ignore').decode('utf-8')
    
    return to_email, subject_safe, html_content_safe

def lambda_handler(event, context):
    """Main Lambda handler - send email with proper UTF-8 handling"""
    logger.info(f"Email sender triggered: {json.dumps(event, ensure_ascii=False)}")
    
    try:
        # Parse event (can be direct invocation or from SNS)
        if 'Records' in event:
            # From SNS
            body = json.loads(event['Records'][0]['Sns']['Message'])
        else:
            # Direct invocation
            body = event
        
        # Validate input data
        to_email, subject, html_content = validate_email_data(body)
        user_id = body.get('user_id')
        
        logger.info(f"Processing email request for: {to_email}")
        
        # Send email
        success = send_html_email(to_email, subject, html_content)
        
        # Update status in DynamoDB if user_id provided
        if user_id:
            update_report_status(user_id, 'sent' if success else 'failed')
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json; charset=utf-8',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Email sent successfully',
                'to': to_email,
                'timestamp': datetime.utcnow().isoformat()
            }, ensure_ascii=False)
        }
        
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        
        # Update status as failed if user_id available
        if 'user_id' in event:
            update_report_status(event['user_id'], 'failed', str(ve))
        
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json; charset=utf-8',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Validation error',
                'message': str(ve)
            }, ensure_ascii=False)
        }
        
    except ses_client.exceptions.MessageRejected as mr:
        logger.error(f"SES message rejected: {str(mr)}")
        
        if 'user_id' in event:
            update_report_status(event['user_id'], 'failed', f"Message rejected: {str(mr)}")
        
        return {
            'statusCode': 422,
            'headers': {
                'Content-Type': 'application/json; charset=utf-8',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Message rejected',
                'message': str(mr)
            }, ensure_ascii=False)
        }
        
    except ses_client.exceptions.MailFromDomainNotVerifiedException as mfd:
        logger.error(f"SES domain not verified: {str(mfd)}")
        
        if 'user_id' in event:
            update_report_status(event['user_id'], 'failed', f"Domain not verified: {str(mfd)}")
        
        return {
            'statusCode': 403,
            'headers': {
                'Content-Type': 'application/json; charset=utf-8',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Domain not verified',
                'message': 'The sending domain is not verified with Amazon SES'
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in email sender: {str(e)}")
        
        # Update status as failed if user_id available
        if 'user_id' in event:
            update_report_status(event['user_id'], 'failed', str(e))
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json; charset=utf-8',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            }, ensure_ascii=False)
        }

def test_email_configuration():
    """Test function to verify SES configuration"""
    try:
        # Get SES sending quota
        quota = ses_client.get_send_quota()
        logger.info(f"SES sending quota: {quota}")
        
        # Get verified identities
        identities = ses_client.list_verified_email_addresses()
        logger.info(f"Verified email addresses: {identities}")
        
        return True
        
    except Exception as e:
        logger.error(f"SES configuration test failed: {str(e)}")
        return False

# Test handler for manual testing with proper UTF-8
def test_handler(event, context):
    """Test handler for manual email testing with corrected UTF-8"""
    test_event = {
        "to_email": "test@example.com",
        "subject": "🤖 Maya Analytics - Test Email",
        "html_content": """
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <title>Test Email</title>
        </head>
        <body>
            <h1>🤖 Maya Analytics - Test Email</h1>
            <p>Questo è un email di test dal sistema Maya Analytics.</p>
            <p>Se ricevi questo messaggio, l'integrazione SES funziona correttamente.</p>
            <p><strong>Timestamp:</strong> """ + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC') + """</p>
            <div style="margin-top: 20px;">
                <h3>Test caratteri speciali:</h3>
                <ul>
                    <li>Emoji: 🤖 📊 ✅ 📈 📧</li>
                    <li>Caratteri italiani: àèìòù ÀÈÌÒÙ</li>
                    <li>Simboli: €™©®</li>
                </ul>
            </div>
        </body>
        </html>
        """,
        "user_id": "test-user-123"
    }
    
    return lambda_handler(test_event, context)