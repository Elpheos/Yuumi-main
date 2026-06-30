# members/ai_agent/access.py
from django.db.models import Sum

DAILY_AI_QUOTA = 10
MONTHLY_WEB_SEARCH_QUOTA = 50


def is_premium_user(user):
    if not user.is_authenticated:
        return False
    try:
        return user.premium.is_valid
    except Exception:
        return False


def can_use_ai_agent(user):
    if not is_premium_user(user):
        return False
    from django.utils import timezone
    from members.models import AIUsageLog
    today = timezone.localdate()
    log = AIUsageLog.objects.filter(user=user, date=today).first()
    current_count = log.request_count if log else 0
    return current_count < DAILY_AI_QUOTA


def monthly_web_search_count(user):
    from django.utils import timezone
    from members.models import AIUsageLog
    today = timezone.localdate()
    total = AIUsageLog.objects.filter(
        user=user,
        date__year=today.year,
        date__month=today.month,
    ).aggregate(total=Sum("web_search_count"))["total"]
    return total or 0


def can_use_web_search(user):
    return monthly_web_search_count(user) < MONTHLY_WEB_SEARCH_QUOTA


def register_ai_usage(user, web_search_used=False):
    from django.utils import timezone
    from django.db.models import F
    from members.models import AIUsageLog
    today = timezone.localdate()
    log, created = AIUsageLog.objects.get_or_create(
        user=user,
        date=today,
        defaults={"request_count": 1, "web_search_count": 1 if web_search_used else 0},
    )
    if not created:
        if web_search_used:
            AIUsageLog.objects.filter(pk=log.pk).update(
                request_count=F("request_count") + 1,
                web_search_count=F("web_search_count") + 1,
            )
        else:
            AIUsageLog.objects.filter(pk=log.pk).update(
                request_count=F("request_count") + 1,
            )
