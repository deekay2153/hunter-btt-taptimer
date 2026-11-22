from datetime import timedelta

DOMAIN = "hunter_btt"
CONF_OUTLETS = "outlets"  # 1 or 2

IDLE_INTERVAL = timedelta(minutes=30)  # battery device: keep idle connections rare
RUNNING_INTERVAL = timedelta(seconds=60)
DEFAULT_RUN_MINUTES = 10
