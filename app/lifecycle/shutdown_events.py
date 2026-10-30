from scheduler.registry import shutdown_scheduler

def on_shutdown():
    shutdown_scheduler()
