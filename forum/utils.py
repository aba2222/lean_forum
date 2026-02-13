from webpush import send_group_notification as sgn
from django.core.exceptions import ObjectDoesNotExist
from requests import RequestException
import threading

def send_group_notification(group_name, body, url):
    payload = {"head": "Lean Forum", "body": body, "url": url}
    try:
        thread = threading.Thread(target=sgn, kwargs={"group_name" : group_name, 
                                                      "payload" : payload, 
                                                      "ttl" : 1000})
        thread.daemon = True
        thread.start()
    except (ObjectDoesNotExist, RequestException) as e:
        pass
