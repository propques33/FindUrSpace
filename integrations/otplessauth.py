import os
import requests

class OtpLessAuth:
    @staticmethod
    def send_otp(mobile):
        url = "https://auth.otpless.app/auth/v1/initiate/otp"
        payload = {
            "phoneNumber": mobile,
            "expiry": 30,
            "otpLength": 4,
            "channels": ["SMS"],
            "metaData": {"purpose": "Operator Login"}
        }
        headers = {
            "clientId": os.getenv('CLIENT_ID'),
            "clientSecret": os.getenv('CLIENT_SECRET'),
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result.get('requestId'):
                    return {'success': True, 'requestId': result['requestId']}
                else:
                    return {'success': False, 'message': 'Unexpected response from OTP service.'}
            else:
                return {'success': False, 'message': f'Error: {response.status_code} - {response.text}'}
        except Exception as e:
            print(f"Error sending OTP: {str(e)}")
            return {'success': False, 'message': 'An error occurred while sending OTP.'}

    @staticmethod
    def verify_otp(request_id, otp):
        url = "https://auth.otpless.app/auth/v1/verify/otp"
        payload = {"requestId": request_id, "otp": otp}
        headers = {
            "clientId": os.getenv('CLIENT_ID'),
            "clientSecret": os.getenv('CLIENT_SECRET'),
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            print(f"Verify OTP Response: {response.status_code}, {response.text}")

            if response.status_code == 200:
                result = response.json()
                if result.get('isOTPVerified'):
                    return {
                        'success': True,
                        'message': 'OTP verified successfully!',
                        'mobile': result.get('mobile')
                    }
                else:
                    return {'success': False, 'message': result.get('message', 'OTP verification failed.')}
            else:
                return {'success': False, 'message': f"Error: {response.status_code} - {response.text}"}
        except Exception as e:
            print(f"Error verifying OTP: {str(e)}")
            return {'success': False, 'message': 'An error occurred during OTP verification.'}
