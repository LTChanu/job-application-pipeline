import boto3
import json
import os
import smtplib
from email.mime.text import MIMEText

def send_mail(recipient_email, name):
    sender_email = "interceptormcamp@gmail.com"  # Your Gmail address
    sender_password = os.environ['GMAIL_APP_PASSWORD']  # App Password from env var

    # Email content
    subject = "Your CV Under Review"
    msg = MIMEText(f"Hi {name},\n\nYour CV is under review. Only those candidates moving on to the next stage of the hiring process will be contacted.\n\nWe wish you a nice day and the best of luck with your job search.\n\nThank you,\nTeam at Interceptor mCamp")
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    # Gmail SMTP settings
    smtp_server = "smtp.gmail.com"
    smtp_port = 465  # SSL port (matches your Java code)

    try:
        # Connect to Gmail SMTP server with SSL
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)  # Authenticate with App Password
            server.send_message(msg)  # Send email
        print(f"Email sent to {recipient_email}")
        return {'statusCode': 200, 'body': json.dumps({'message': 'Email sent successfully'})}
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Failed to send email'})}


def lambda_handler(event, context):
    # Check if event['body'] is a string, then parse it
    if isinstance(event.get('body'), str):
        meta_data = json.loads(event['body'])
    else:
        # If it's already a dictionary, use it directly
        meta_data = event.get('body', {})

    # Get applicant_name and email from meta_data
    try:
        applicant_name = meta_data['metadata']['applicant_name']
        email = meta_data['metadata']['email']

        send_mail(email, applicant_name)
        
    except KeyError as e:
        print(f"KeyError: {e} not found in the payload")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": f"Missing key: {e}"
            })
        }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "applicant_name": applicant_name,
            "email": email
        })
    }