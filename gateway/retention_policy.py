"""One fixed retention policy shared by persistence and maintenance."""
RETENTION_DAYS = 90
RETENTION_SECONDS = RETENTION_DAYS * 86400
CLEANUP_INTERVAL_SECONDS = 3600
EXPIRY_WARNING_DAYS = 7


def expiry_fields(created):
    return {'expires_at': created + RETENTION_SECONDS, 'retention_days': RETENTION_DAYS}
