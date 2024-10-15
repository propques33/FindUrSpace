import os
import requests
from base64 import b64encode
import OTPLessAuthSDK

class OtpLessAuth:

    @staticmethod
    def send_otp(mobile):
        """Send OTP via SMS using OTPLess API"""
        url = "https://auth.otpless.app/auth/v1/initiate/otp"

        # Ensure mobile number is in correct format
        if mobile.startswith('0'):
            mobile = mobile.lstrip('0')
        if not mobile.startswith('+91'):
            mobile = f"+91{mobile}"

        # Payload for OTP request
        payload = {
            "phoneNumber": mobile,
            "expiry": 30,  # OTP expires in 30 minutes
            "otpLength": 4,  # OTP length
            "channels": ["SMS"],  # Sending only via SMS
            "metaData": {
                "purpose": "Operator Login"  # Optional metadata
            }
        }

        headers = {
            "clientId": os.getenv('CLIENT_ID'),
            "clientSecret": os.getenv('CLIENT_SECRET'),
            "Content-Type": "application/json"
        }

        try:
            # Make request to send OTP
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return {'success': True, 'requestId': result['requestId']}
                else:
                    return {'success': False, 'message': result.get('message', 'Failed to send OTP.')}
            else:
                return {'success': False, 'message': f'Error: {response.status_code} - {response.text}'}
        except Exception as e:
            print(f"Error sending OTP: {str(e)}")
            return {'success': False, 'message': 'An error occurred while sending OTP.'}

    @staticmethod
    def verify_otp(request_id, otp):
        """Verify OTP using OTPLess API"""
        url = "https://auth.otpless.app/auth/v1/verify/otp"

        payload = {
            "requestId": request_id,
            "otp": otp
        }

        headers = {
            "clientId": os.getenv('CLIENT_ID'),
            "clientSecret": os.getenv('CLIENT_SECRET'),
            "Content-Type": "application/json"
        }

        try:
            # Make request to verify OTP
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return {'success': True, 'message': 'OTP verified successfully!'}
                else:
                    return {'success': False, 'message': result.get('message', 'OTP verification failed.')}
            else:
                return {'success': False, 'message': f'Error: {response.status_code} - {response.text}'}
        except Exception as e:
            print(f"Error verifying OTP: {str(e)}")
            return {'success': False, 'message': 'An error occurred during OTP verification.'}
