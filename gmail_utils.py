import base64
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os.path
import os
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load credentials from environment variables or GitHub Secrets
def load_credentials():
    try:
        # Get credentials from environment variables
        client_secret = os.environ.get('GMAIL_CLIENT_SECRET')
        token_data = os.environ.get('GMAIL_TOKEN_DATA')
        
        if not client_secret or not token_data:
            # Try to load from local files if environment variables are not set
            try:
                with open('clientsecret.json', 'r') as f:
                    client_secret = f.read()
                with open('token.json', 'r') as f:
                    token_data = f.read()
            except FileNotFoundError:
                raise ValueError("Credentials not found. Please either:\n"
                               "1. Set GMAIL_CLIENT_SECRET and GMAIL_TOKEN_DATA environment variables\n"
                               "2. Place clientsecret.json and token.json in the project directory")
        
        # Parse the JSON strings
        credentials = json.loads(client_secret)
        tokens = json.loads(token_data)
        logging.info(f"Loaded credentials:success")
        return credentials, tokens
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON from credentials: {e}")
        raise
    except Exception as e:
        logging.error(f"Error loading credentials: {e}")
        raise

def get_gmail_service():
    credentials, tokens = load_credentials()
    creds = Credentials(
        token=tokens['token'],
        refresh_token=tokens['refresh_token'],
        token_uri=tokens['token_uri'],
        client_id=tokens['client_id'],
        client_secret=tokens['client_secret'],
        scopes=tokens['scopes']
    )
    
    service = build('gmail', 'v1', credentials=creds)
    return service

def create_message(sender, to, subject, message_text, attachments=None):
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    msg = MIMEText(message_text)
    message.attach(msg)

    if attachments:
        # Define a safe root directory (using a temporary directory for example)
        # In a production environment, this should be a more permanent and secure location.
        SAFE_ROOT_DIR = tempfile.gettempdir()
        logging.info(f"Using safe root directory: {SAFE_ROOT_DIR}")

        for file_path in attachments:
            # Normalize the file path
            normalized_file_path = os.path.normpath(file_path)

            # Ensure the normalized path is within the safe root directory
            if not normalized_file_path.startswith(SAFE_ROOT_DIR):
                logging.error(f"Attempted to access file outside safe directory: {file_path}")
                raise ValueError(f"File path is outside the allowed directory: {file_path}")

            with open(normalized_file_path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(normalized_file_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(normalized_file_path)}"'
            message.attach(part)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    return {'raw': raw_message}

def send_mail(options):
    service = get_gmail_service()
    message = create_message(
        sender=options.get('from', 'me'),
        to=options['to'],
        subject=options['subject'],
        message_text=options['text'],
        attachments=options.get('attachments', [])
    )
    
    try:
        message = service.users().messages().send(userId='me', body=message).execute()
        return message['id']
    except Exception as e:
        logging.error(f'An error occurred while sending email: {e}')
        raise

def send_completion_email(emails_list, output_file, doc_id):
    """
    Send completion email with the processed document attached.
    
    Args:
        emails_list (list): List of email addresses to send to
        output_file (str): Path to the output file to attach
        doc_id (str): Document ID for reference
    """
    if not emails_list:
        logging.warning("No email addresses provided for notification")
        return None

    # Join multiple email addresses with commas
    to_emails = ', '.join(emails_list)
    
    subject = f"Document Processing Complete - Document ID: {doc_id}"
    message_text = f"""
    Hello,

    Your document processing has been completed successfully.
    Document ID: {doc_id}
    
    Please find the processed document attached to this email.
    
    Best regards,
    Automated Testing System
    """

    options = {
        'to': to_emails,
        'subject': subject,
        'text': message_text,
        'attachments': [output_file] if output_file else []
    }

    try:
        message_id = send_mail(options)
        logging.info(f"Completion email sent successfully. Message ID: {message_id}")
        return message_id
    except Exception as e:
        logging.error(f"Failed to send completion email: {str(e)}")
        raise


load_credentials()