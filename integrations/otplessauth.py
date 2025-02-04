# import os
# import requests
# import logging

# # Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# class OtpLessAuth:
#     @staticmethod
#     def send_otp(mobile):
#         client_id = os.getenv('CLIENT_ID')
#         client_secret = os.getenv('CLIENT_SECRET')
        
#         # Validate environment variables
#         if not client_id or not client_secret:
#             logging.error("CLIENT_ID or CLIENT_SECRET is not set in environment variables.")
#             return {'success': False, 'message': 'Missing CLIENT_ID or CLIENT_SECRET.'}
        
#         url = "https://auth.otpless.app/auth/v1/initiate/otp"
#         payload = {
#             "phoneNumber": mobile,
#             "expiry": 30,
#             "otpLength": 4,
#             "channels": ["SMS"],
#             "metaData": {"purpose": "Operator Login"}
#         }
#         headers = {
#             "clientId": os.getenv('CLIENT_ID'),
#             "clientSecret": os.getenv('CLIENT_SECRET'),
#             "Content-Type": "application/json"
#         }

#         try:
#             response = requests.post(url, json=payload, headers=headers, timeout=10)
#             logging.info(f"Send OTP Response: {response.status_code}, {response.text}")
#             if response.status_code == 200:
#                 result = response.json()
#                 if result.get('requestId'):
#                     return {'success': True, 'requestId': result['requestId']}
#                 else:
#                     return {'success': False, 'message': 'Unexpected response from OTP service.'}
#             else:
#                 return {'success': False, 'message': f'Error: {response.status_code} - {response.text}'}
#         except requests.exceptions.Timeout:
#             logging.error("Request timed out while sending OTP.")
#             return {'success': False, 'message': 'Request timed out while sending OTP.'}
#         except Exception as e:
#             logging.error(f"Error sending OTP: {str(e)}")
#             return {'success': False, 'message': 'An error occurred while sending OTP.'}

#     @staticmethod
#     def verify_otp(request_id, otp):
#         client_id = os.getenv('CLIENT_ID')
#         client_secret = os.getenv('CLIENT_SECRET')
        
#         # Validate environment variables
#         if not client_id or not client_secret:
#             logging.error("CLIENT_ID or CLIENT_SECRET is not set in environment variables.")
#             return {'success': False, 'message': 'Missing CLIENT_ID or CLIENT_SECRET.'}
        
#         url = "https://auth.otpless.app/auth/v1/verify/otp"
#         payload = {"requestId": request_id, "otp": otp}
#         headers = {
#             "clientId": os.getenv('CLIENT_ID'),
#             "clientSecret": os.getenv('CLIENT_SECRET'),
#             "Content-Type": "application/json"
#         }

#         try:
#             response = requests.post(url, json=payload, headers=headers, timeout=10)
#             logging.info(f"Verify OTP Response: {response.status_code}, {response.text}")
#             print(f"Verify OTP Response: {response.status_code}, {response.text}")

#             if response.status_code == 200:
#                 result = response.json()
#                 if result.get('isOTPVerified'):
#                     return {
#                         'success': True,
#                         'message': 'OTP verified successfully!',
#                         'mobile': result.get('mobile')
#                     }
#                 else:
#                     return {'success': False, 'message': result.get('message', 'OTP verification failed.')}
#             else:
#                 return {'success': False, 'message': f"Error: {response.status_code} - {response.text}"}
#         except requests.exceptions.Timeout:
#             logging.error("Request timed out while verifying OTP.")
#             return {'success': False, 'message': 'Request timed out while verifying OTP.'}
#         except Exception as e:
#             logging.error(f"Error verifying OTP: {str(e)}")
#             return {'success': False, 'message': 'An error occurred during OTP verification.'}

import os
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OtpLessAuth:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')

    def send_otp(self, mobile):
        if not self.client_id or not self.client_secret:
            return {'success': False, 'message': 'Missing OTPLESS credentials'}

        url = "https://auth.otpless.app/auth/v1/initiate/otp"
        payload = {
            "phoneNumber": mobile,
            "expiry": 30,
            "otpLength": 6,
            "channels": ["SMS"]
        }
        headers = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"OTP sending failed: {e}")
            return {'success': False, 'message': 'Error sending OTP'}

    def verify_otp(self, mobile, otp):
        if not self.client_id or not self.client_secret:
            return {'success': False, 'message': 'Missing OTPLESS credentials'}

        url = "https://auth.otpless.app/auth/v1/verify/otp"
        payload = {"phoneNumber": mobile, "otp": otp}
        headers = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"OTP verification failed: {e}")
            return {'success': False, 'message': 'Error verifying OTP'}
