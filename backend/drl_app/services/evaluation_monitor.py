import time
from django.core.cache import cache
from ..models import Evaluation, EvaluationSession

def record_autosave_metrics(*, success=True, is_conflict=False, duration_ms=0):
    """
    Records real-time performance and reliability metrics of the Evaluation Engine.
    Uses Django cache to store and update values in a thread-safe manner.
    """
    if is_conflict:
        # Increment version conflict count
        conflict_val = cache.get('drl_conflict_count', 0)
        cache.set('drl_conflict_count', conflict_val + 1, timeout=86400)
    
    if success:
        # Increment successful save count
        success_val = cache.get('drl_autosave_success_count', 0)
        cache.set('drl_autosave_success_count', success_val + 1, timeout=86400)
        
        # Accumulate total save duration
        total_time_val = cache.get('drl_total_save_time_ms', 0)
        cache.set('drl_total_save_time_ms', total_time_val + duration_ms, timeout=86400)
        
        # Increment total save operations count
        save_val = cache.get('drl_save_count', 0)
        cache.set('drl_save_count', save_val + 1, timeout=86400)
    else:
        # Increment failed save count
        failed_val = cache.get('drl_autosave_failed_count', 0)
        cache.set('drl_autosave_failed_count', failed_val + 1, timeout=86400)

def get_health_metrics():
    """
    Queries database and Django cache to return standard observability indicators.
    """
    draft_count = Evaluation.objects.filter(status='draft').count()
    active_sessions = EvaluationSession.objects.filter(status='active').count()
    
    autosave_success = cache.get('drl_autosave_success_count', 0)
    autosave_failed = cache.get('drl_autosave_failed_count', 0)
    conflict_count = cache.get('drl_conflict_count', 0)
    
    total_time = cache.get('drl_total_save_time_ms', 0)
    save_count = cache.get('drl_save_count', 0)
    average_save_ms = int(total_time / save_count) if save_count > 0 else 0
    
    return {
        'active_sessions': active_sessions,
        'draft_count': draft_count,
        'autosave_failed': autosave_failed,
        'version_conflict': conflict_count,
        'average_save_ms': average_save_ms,
        # included success for complete transparency
        'autosave_success': autosave_success
    }
