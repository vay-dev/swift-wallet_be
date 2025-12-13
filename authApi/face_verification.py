from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.core.files.storage import default_storage
from .models import FaceVerification
from .serializers import FaceVerificationSerializer
import logging
import cv2
import numpy as np
from PIL import Image
import io

logger = logging.getLogger(__name__)


class FaceVerificationUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        if 'verification_image' not in request.FILES:
            return Response({
                'status': 'error',
                'message': 'No image file provided'
            }, status=status.HTTP_400_BAD_REQUEST)

        image_file = request.FILES['verification_image']

        # Validate file size (max 5MB)
        if image_file.size > 5 * 1024 * 1024:
            return Response({
                'status': 'error',
                'message': 'Image file size cannot exceed 5MB'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if image_file.content_type not in allowed_types:
            return Response({
                'status': 'error',
                'message': 'Invalid file type. Only JPEG and PNG are allowed'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check if verification already exists
            try:
                face_verification = FaceVerification.objects.get(user=user)
                # Update existing verification
                face_verification.verification_image = image_file
                face_verification.verification_status = 'pending'
                face_verification.is_verified = False
            except FaceVerification.DoesNotExist:
                # Create new verification
                face_verification = FaceVerification(
                    user=user,
                    verification_image=image_file
                )

            face_verification.save()

            # Perform AI verification
            verification_result = self.verify_face_image(face_verification.verification_image.path)

            # Update verification model with results
            face_verification.face_detected = verification_result['face_detected']
            face_verification.clarity_score = verification_result['clarity_score']
            face_verification.lighting_score = verification_result['lighting_score']
            face_verification.verification_message = verification_result['message']

            # Determine if verification passed
            if (verification_result['face_detected'] and
                verification_result['clarity_score'] >= 50 and
                verification_result['lighting_score'] >= 40):
                face_verification.verification_status = 'approved'
                face_verification.is_verified = True
                face_verification.verified_at = timezone.now()

                # Update user verification status
                user.is_verified = True
                user.save()
            else:
                face_verification.verification_status = 'rejected'
                face_verification.is_verified = False

            face_verification.save()

            return Response({
                'status': 'success',
                'message': 'Face verification processed',
                'data': FaceVerificationSerializer(face_verification).data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Face verification error: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Face verification failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def verify_face_image(self, image_path):
        try:
            from deepface import DeepFace
            import cv2

            # Read image
            img = cv2.imread(image_path)

            if img is None:
                return {
                    'face_detected': False,
                    'clarity_score': 0,
                    'lighting_score': 0,
                    'message': 'Unable to read image file'
                }

            # Check image clarity (using Laplacian variance)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            clarity_score = min(100, laplacian_var / 10)  # Normalize to 0-100

            # Check lighting (average brightness)
            brightness = np.mean(gray)
            lighting_score = min(100, (brightness / 255) * 100)

            # Detect face using DeepFace
            try:
                faces = DeepFace.extract_faces(
                    img_path=image_path,
                    detector_backend='opencv',
                    enforce_detection=True
                )
                face_detected = len(faces) > 0

                if not face_detected:
                    message = "No face detected in the image"
                elif clarity_score < 50:
                    message = f"Image is too blurry. Clarity score: {clarity_score:.1f}/100"
                elif lighting_score < 40:
                    message = f"Image lighting is poor. Lighting score: {lighting_score:.1f}/100"
                else:
                    message = "Face verification successful! Image quality is good."

            except Exception as e:
                logger.warning(f"DeepFace detection failed: {str(e)}")
                face_detected = False
                message = f"Face detection failed: {str(e)}"

            return {
                'face_detected': face_detected,
                'clarity_score': round(clarity_score, 2),
                'lighting_score': round(lighting_score, 2),
                'message': message
            }

        except ImportError:
            logger.error("DeepFace library not installed")
            return {
                'face_detected': False,
                'clarity_score': 0,
                'lighting_score': 0,
                'message': 'DeepFace library not installed. Please install with: pip install deepface'
            }
        except Exception as e:
            logger.error(f"Face verification error: {str(e)}")
            return {
                'face_detected': False,
                'clarity_score': 0,
                'lighting_score': 0,
                'message': f'Verification error: {str(e)}'
            }


class FaceVerificationStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            face_verification = FaceVerification.objects.get(user=user)
            return Response({
                'status': 'success',
                'message': 'Verification status retrieved',
                'data': FaceVerificationSerializer(face_verification).data
            }, status=status.HTTP_200_OK)

        except FaceVerification.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'No face verification found for this user'
            }, status=status.HTTP_404_NOT_FOUND)
