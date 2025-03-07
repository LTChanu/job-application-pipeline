import json
import os
import boto3
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import requests

# AWS clients
s3 = boto3.client('s3', region_name='eu-north-1')
lambda_client = boto3.client('lambda', region_name='eu-north-1')
events_client = boto3.client('events', region_name='eu-north-1')

# Google Sheets scope
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def extract_cv_data(resume_data):
    # Initialize the categories
    Education = []
    Qualifications = []
    Projects = []
    Contact_Details = []
    Personal_Info = {'Name': 'Not Found', 'phoneNumber': 'Not Found', 'email': 'Not Found'}

    # Extract Education
    for edu in resume_data['data']['education']:
        education_entry = {
            'organization': edu['organization'],
            'degree': edu['accreditation']['education'],
            'completion_date': edu['dates']['completionDate'],
            'raw_text': edu['dates']['rawText']
        }
        if edu.get('grade'):  # Add grade if it exists
            education_entry['grade'] = edu['grade']
        Education.append(education_entry)

    # Extract Qualifications (using grades from education where available)
    for edu in resume_data['data']['education']:
        if edu.get('grade'):
            Qualifications.append({
                'qualification': edu['accreditation']['education'],
                'grade': edu['grade'],
                'year': edu['dates']['completionDate']
            })

    # Extract Projects
    for section in resume_data['data']['sections']:
        if section['sectionType'] == 'Projects':
            # Split the text into lines and extract project details
            project_lines = section['text'].split('\n')
            project_entry = {'title': project_lines[0], 'details': []}
            for line in project_lines[1:]:
                if line.strip():  # Ignore empty lines
                    project_entry['details'].append(line.strip())
            Projects.append(project_entry)

    # Extract Contact Details
    Contact_Details.extend(resume_data['data']['emails'])  # Add emails
    Contact_Details.extend(resume_data['data']['websites'])  # Add websites

    # Extract Personal Info
    Personal_Info['Name'] = resume_data['data']['name']['raw']
    if resume_data['data']['phoneNumbers']:
        Personal_Info['phoneNumber'] = resume_data['data']['phoneNumbers'][0]
    else:
        Personal_Info['phoneNumber'] = 'Not Found'
    Personal_Info['email'] = resume_data['data']['emails'][0] if resume_data['data']['emails'] else 'Not Found'


    return {
        'personal_info': Personal_Info,
        'education': Education,
        'qualifications': Qualifications,
        'projects': Projects,
        'otherContact' : Contact_Details
    }

# Function to parse the resume, API call
def parse_resume(bucket, key):
    # Define the URL for the Affinda API endpoint
    url = 'https://api.affinda.com/v1/resumes'

    # Download the file from S3 to a temporary location
    temp_file_path = f"/tmp/{os.path.basename(key)}"
    s3.download_file(bucket, key, temp_file_path)

    # Open the file in binary mode
    with open(temp_file_path, 'rb') as file:
        files = {'file': file}
        
        # Set the headers to include the API Key
        headers = {
            'Authorization': f'Bearer {os.environ['API_KEY']}'
        }

        # Send a POST request to the API
        response = requests.post(url, files=files, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the response JSON
            os.remove(temp_file_path)
            resume_data = response.json()
            return resume_data
        else:
            os.remove(temp_file_path)
            print(f"Error: {response.status_code}, {response.text}")

def lambda_handler(event, context):
    print(f"GOOGLE_SHEETS_CREDENTIALS exists: {'GOOGLE_SHEETS_CREDENTIALS' in os.environ}")
    print(f"Raw event: {json.dumps(event)}")
    try:
        # Handle non-S3 events gracefully
        if 'Records' not in event:
            raise ValueError("Event is not an S3 trigger event")

        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key'].replace('+', ' ').replace('%20', ' ')
        print(f"New file uploaded: {bucket}/{key}")

        # Get CV content from S3 and read into memory
        obj = s3.get_object(Bucket=bucket, Key=key)
        metadata = obj.get('Metadata', {})  # Access name, email, phone
        # print(f"Name: {metadata.get('name', 'Not found')}")
        # print(f"Email: {metadata.get('email', 'Not found')}")
        # print(f"Phone: {metadata.get('phone', 'Not found')}")

        # Extract CV data
        public_url = f"https://{bucket}.s3.amazonaws.com/{key}"
        resume_data = parse_resume(bucket, key)
        if not resume_data:
            raise Exception("Failed to parse resume from Affinda API")
        cv_data = extract_cv_data(resume_data)
        print(f"Extracted CV data: {json.dumps(cv_data)}")

        # Google Sheets setup with gspread
        credentials_json = json.loads(os.environ['GOOGLE_SHEETS_CREDENTIALS'])
        print(f"Parsed credentials: {credentials_json.get('client_email', 'No email found')}")
        credentials_file = '/tmp/credentials.json'
        with open(credentials_file, 'w') as f:
            json.dump(credentials_json, f)
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        client = gspread.authorize(creds)
        spreadsheet_name = "Candidate-cv-info"
        sheet = client.open(spreadsheet_name).sheet1

        # Prepare and append data
        values = [[
            datetime.now().isoformat(),
            public_url,
            metadata.get('name'),
            metadata.get('email'),
            metadata.get('phone'),
            json.dumps(cv_data['education']),
            json.dumps(cv_data['qualifications']),
            json.dumps(cv_data['projects']),
            cv_data['personal_info']['Name'],
            cv_data['personal_info']['email'],
            cv_data['personal_info']['phoneNumber'],
            json.dumps(cv_data['otherContact']),
        ]]
        print(f"Appending data to sheet: {values}")
        sheet.append_rows(values)
        print("Data written to Google Sheet successfully!")

        # Invoke send-webhook Lambda
        payload = {
            'body': json.dumps({
                'cv_data': {
                    'personal_info': cv_data['personal_info'],
                    'education': cv_data['education'],
                    'qualifications': cv_data['qualifications'],
                    'projects': cv_data['projects'],
                    'cv_public_link': public_url
                },
                'metadata': {
                    'applicant_name': metadata.get('name', 'Not found'),
                    'email': metadata.get('email', 'Not found'),
                    'status': 'prod',
                    'cv_processed': True,
                    'processed_timestamp': datetime.utcnow().isoformat() + 'Z'
                }
            })
        }

        mail_payload = {
            'body': json.dumps({
                'metadata': {
                    'applicant_name': metadata.get('name', 'Not found'),
                    'email': metadata.get('email', 'Not found'),                    
                }
            })
        }

        print(f"payload: {json.dumps(payload)}")

        response = lambda_client.invoke(
            FunctionName='send-webhook',
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        print(f"Invoked send-webhook: {response['ResponseMetadata']['RequestId']}")

        # mail_response = lambda_client.invoke(
        #     FunctionName='send-email',
        #     InvocationType='Event',
        #     Payload=json.dumps(mail_payload)
        # )
        # print(f"Invoked send-webhook: {mail_response['ResponseMetadata']['RequestId']}")

        # Schedule send-email after 22 hours
        now_utc = datetime.utcnow()
        schedule_time = now_utc + timedelta(hours=22) #hours=22
        rule_name = f"send-email-{key.replace('/', '-')}-{int(now_utc.timestamp())}"
        cron_expression = f"cron({schedule_time.minute} {schedule_time.hour} {schedule_time.day} {schedule_time.month} ? {schedule_time.year})"

        events_client.put_rule(
            Name=rule_name,
            ScheduleExpression=cron_expression,
            State='ENABLED'
        )
        events_client.put_targets(
            Rule=rule_name,
            Targets=[{
                'Id': '1',
                'Arn': 'arn:aws:lambda:eu-north-1:676206939350:function:send-email',
                'Input': json.dumps(mail_payload)
            }]
        )
        print(f"Scheduled send-email for {schedule_time.isoformat()}Z")



        return {
            'statusCode': 200,
            'body': json.dumps({'message': f"Processed {key} and invoked webhook"})
        }
    except Exception as e:
        import traceback
        print("Exception occurred:", traceback.format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to process S3 event'})
        }