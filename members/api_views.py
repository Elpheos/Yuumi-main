# members/api_views.py
from django.contrib.auth import authenticate, login
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError


# -------------------------------------------------------------------
# 1. LOGIN CLASSIQUE → retourne un refresh token JWT
#    Appelé une seule fois quand l'utilisateur tape son mot de passe.
#    L'app stocke le refresh token dans le Keychain natif Android/iOS.
# -------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def biometric_token_obtain(request):
    """
    POST /api/token/
    Body : { "username": "...", "password": "..." }
    Retourne : { "refresh": "...", "username": "..." }

    Le refresh token est stocké dans le Keychain de l'app.
    Il sera utilisé à chaque reconnexion biométrique.
    """
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()

    if not username or not password:
        return Response(
            {'error': 'Username et password requis.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response(
            {'error': 'Identifiants incorrects.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {'error': 'Compte désactivé.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Génère un refresh token JWT longue durée (90 jours, cf settings.py)
    refresh = RefreshToken.for_user(user)

    return Response({
        'refresh': str(refresh),
        'username': user.username,
    }, status=status.HTTP_200_OK)


# -------------------------------------------------------------------
# 2. LOGIN BIOMÉTRIQUE → échange le refresh token contre une session
#    Appelé à chaque ouverture de l'app après validation biométrique.
#    Crée une vraie session Django → l'utilisateur est connecté.
# -------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def biometric_login(request):
    """
    POST /api/biometric-login/
    Body : { "refresh": "..." }
    Retourne : { "success": true, "username": "..." }

    Django crée une session → l'utilisateur est connecté côté web.
    """
    refresh_token = request.data.get('refresh', '').strip()

    if not refresh_token:
        return Response(
            {'error': 'Refresh token requis.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Valide le refresh token et récupère l'utilisateur
        token = RefreshToken(refresh_token)
        user_id = token['user_id']

        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)

        if not user.is_active:
            return Response(
                {'error': 'Compte désactivé.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Crée une vraie session Django (équivalent à un login classique)
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)

        return Response({
            'success': True,
            'username': user.username,
        }, status=status.HTTP_200_OK)

    except TokenError:
        # Token expiré ou invalide → l'app devra demander le mot de passe
        return Response(
            {'error': 'Token expiré ou invalide. Reconnexion requise.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    except Exception:
        return Response(
            {'error': 'Erreur serveur.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
