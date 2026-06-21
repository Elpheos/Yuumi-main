# members/ai_agent/access.py

DAILY_AI_QUOTA = 10  


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


def can_use_ai_agent(user):
    """
    True si l'utilisateur est premium ET n'a pas encore atteint son
    quota quotidien d'appels IA (DAILY_AI_QUOTA).

    Ne consomme PAS de quota — vérification en lecture seule.
    """
    if not is_premium_user(user):
        return False

    from django.utils import timezone
    from members.models import AIUsageLog

    today = timezone.localdate()
    log = AIUsageLog.objects.filter(user=user, date=today).first()
    current_count = log.request_count if log else 0

    return current_count < DAILY_AI_QUOTA


def register_ai_usage(user):
    """
    Incrémente le compteur de requêtes IA du jour pour cet utilisateur.

    À appeler UNIQUEMENT après un appel IA réellement effectué et réussi.
    """
    from django.utils import timezone
    from django.db.models import F
    from members.models import AIUsageLog

    today = timezone.localdate()

    log, created = AIUsageLog.objects.get_or_create(
        user=user,
        date=today,
        defaults={"request_count": 1},
    )
    if not created:
        AIUsageLog.objects.filter(pk=log.pk).update(request_count=F("request_count") + 1)
