import json
import requests

def lambda_handler(event, context):
    try:
        print(f"Received event: {json.dumps(event)}")
        cv_data = json.loads(event['body'])
        payload = {
            'cv_data': cv_data['cv_data'],
            'metadata': cv_data['metadata']
        }
        headers = {'X-Candidate-Email': 'tchanu210@gmail.com'}
        print(f"Sending webhook with payload: {json.dumps(payload)}")

        response = requests.post(
            'https://rnd-assignment.automations-3d6.workers.dev/',
            json=payload,
            headers=headers
        )
        print(f"Webhook response: {response.status_code} - {response.text}")

        return {
            'statusCode': response.status_code,
            'body': response.text
        }
    except Exception as e:
        print(f"Error sending webhook: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to send webhook'})
        }