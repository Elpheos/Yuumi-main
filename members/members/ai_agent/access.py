# members/ai_agent/access.py

def is_premium_user(user):
    """
    True si l'utilisateur est connecté ET a un statut premium valide
    (actif et non expiré).
    """
    if not user.is_authenticated:
        return False

    try:
        return user.premium.is_valid
    except Exception:
        return False
