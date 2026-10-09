from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from .serializers import AdminRegistrationSerializer


class AdminRegistrationAPIView(APIView):
    """
    POST /api/admin/register/
    Registers a new Admin user (is_staff=True, is_superuser=False).
    Only accessible by superusers.
    """
    authentication_classes = [SessionAuthentication, BasicAuthentication]

    def post(self, request, *args, **kwargs):
        # 1. Unauthenticated request -> HTTP 401 Unauthorized
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2. Authenticated user without superuser permission -> HTTP 403 Forbidden
        if not request.user.is_superuser:
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 3. Superuser -> Validate & Create Admin User
        serializer = AdminRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            admin_user = serializer.save()
            return Response(
                {
                    "message": "Admin user registered successfully.",
                    "admin": {
                        "id": admin_user.id,
                        "username": admin_user.username,
                        "email": admin_user.email,
                        "first_name": admin_user.first_name,
                        "last_name": admin_user.last_name,
                    }
                },
                status=status.HTTP_201_CREATED
            )

        # 4. Validation errors -> HTTP 400 Bad Request
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
