#!/usr/bin/env python
"""
Test script to verify AWS SNS configuration
Run this to diagnose SNS issues
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def test_sns_configuration():
    print("=" * 60)
    print("AWS SNS Configuration Test")
    print("=" * 60)

    # Check environment variables
    print("\n1. Checking environment variables...")
    print(f"   AWS_ACCESS_KEY_ID: {'✓ Set' if settings.AWS_ACCESS_KEY_ID else '✗ NOT SET'}")
    print(f"   AWS_SECRET_ACCESS_KEY: {'✓ Set' if settings.AWS_SECRET_ACCESS_KEY else '✗ NOT SET'}")
    print(f"   AWS_REGION_NAME: {settings.AWS_REGION_NAME or '✗ NOT SET'}")

    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        print("\n❌ ERROR: AWS credentials are not configured!")
        print("   Please check your .env file and ensure AWS credentials are set.")
        return False

    # Test SNS client initialization
    print("\n2. Testing SNS client initialization...")
    try:
        sns_client = boto3.client(
            'sns',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION_NAME
        )
        print("   ✓ SNS client initialized successfully")
    except Exception as e:
        print(f"   ✗ Failed to initialize SNS client: {e}")
        return False

    # Test SNS credentials
    print("\n3. Testing SNS credentials and permissions...")
    try:
        # Try to get SMS attributes (this doesn't send SMS, just checks permissions)
        response = sns_client.get_sms_attributes()
        print("   ✓ SNS credentials are valid")
        print(f"   Current SMS attributes: {response.get('attributes', {})}")
    except NoCredentialsError:
        print("   ✗ No credentials found")
        return False
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'InvalidClientTokenId':
            print("   ✗ Invalid AWS Access Key ID")
        elif error_code == 'SignatureDoesNotMatch':
            print("   ✗ Invalid AWS Secret Access Key")
        elif error_code == 'AccessDenied':
            print("   ✗ Access denied - check IAM permissions for SNS")
        else:
            print(f"   ✗ AWS Error: {error_code} - {e.response['Error']['Message']}")
        return False
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        return False

    # Check if we can set SMS type
    print("\n4. Checking SMS spend limit...")
    try:
        attributes = sns_client.get_sms_attributes()
        spend_limit = attributes.get('attributes', {}).get('MonthlySpendLimit', 'Not set')
        print(f"   Monthly spend limit: ${spend_limit}")

        if spend_limit == '1.00' or spend_limit == '1':
            print("   ⚠ WARNING: Spend limit is very low ($1). You may not be able to send many SMS.")
            print("   To increase: Go to AWS SNS Console → Text messaging (SMS) → Sandbox or spending limits")
    except Exception as e:
        print(f"   ⚠ Could not check spend limit: {e}")

    print("\n" + "=" * 60)
    print("✓ SNS Configuration Test PASSED")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Make sure your phone number is in E.164 format (e.g., +1234567890)")
    print("2. Check AWS SNS console for any sandbox restrictions")
    print("3. Verify your account has SMS sending enabled in your region")
    print("4. Check CloudWatch logs for detailed error messages")
    return True

if __name__ == "__main__":
    success = test_sns_configuration()
    sys.exit(0 if success else 1)
