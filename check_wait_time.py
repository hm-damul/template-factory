
import datetime
import time

reset_ts = 1770949102024 / 1000
now_ts = time.time()
diff_min = (reset_ts - now_ts) / 60

print(f"Current Time: {datetime.datetime.now()}")
print(f"Vercel Reset Time: {datetime.datetime.fromtimestamp(reset_ts)}")
print(f"Remaining Wait: {diff_min:.1f} minutes")
