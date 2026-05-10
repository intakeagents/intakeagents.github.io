import urllib.request, json, os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
key = os.environ.get("VAPI_API_Key") or os.environ.get("VAPI_API_KEY") or os.environ.get("VAPI_API_key")
print(f"Key loaded: {key[:8]}..." if key else "ERROR: Key not found")

def get(endpoint):
    req = urllib.request.Request(f"https://api.vapi.ai/{endpoint}",
                                  headers={"Authorization": f"Bearer {key}"})
    res = urllib.request.urlopen(req)
    return json.loads(res.read())

print("ASSISTANTS:")
for a in get("assistant"):
    print(f"  {a['id']} | {a.get('name','unnamed')}")

print("\nPHONE NUMBERS:")
for p in get("phone-number"):
    print(f"  {p['id']} | {p.get('number','?')} | {p.get('name','unnamed')}")
