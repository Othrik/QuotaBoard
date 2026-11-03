"""Taskbar dwell time, independent of API refresh frequency."""
def rotation_seconds(value=5):
    try:
        if isinstance(value,bool):return 5
        return max(1,min(300,int(value)))
    except (TypeError,ValueError,OverflowError):
        return 5
