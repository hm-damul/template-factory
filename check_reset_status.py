import time
import datetime

reset_timestamp = 1771266937.452
current_timestamp = time.time()

print(f"Current timestamp: {current_timestamp}")
print(f"Reset timestamp:   {reset_timestamp}")

if current_timestamp > reset_timestamp:
    print("Rate limit reset time HAS PASSED.")
else:
    diff = reset_timestamp - current_timestamp
    print(f"Rate limit reset time is in the future. Wait {diff:.2f} seconds ({diff/60:.2f} minutes).")
