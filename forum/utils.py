from webpush import send_group_notification as sgn
from webpush.models import Group
import threading

def send_group_notification(group_name, body, url):
    if not Group.objects.filter(name=group_name).exists():
        print(f"Group '{group_name}' does not exist, skip notification.")
        return

    payload = {"head": "Lean Forum", "body": body, "url": url}
    try:
        thread = threading.Thread(target=sgn, kwargs={"group_name" : group_name, 
                                                      "payload" : payload, 
                                                      "ttl" : 1000})
        thread.daemon = True
        thread.start()
    except Exception as e:
        pass
