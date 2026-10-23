# Python examples

Using the `requests` library. For a typed client instead, see [Client SDKs](../clients.md).

```python
import requests

BASE = "https://dev.omethe.us"   # replace with your deployment
# TOKEN only needed for contribution/admin endpoints:
# HEADERS = {"Authorization": "Token <your-token>"}


def get_all(path, **params):
    """Yield every result across all pages."""
    url = f"{BASE}{path}"
    while url:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        yield from data["results"]
        url, params = data["next"], {}   # 'next' already carries the query


# Ignition-delay datapoints measured at/above 1000 K
points = list(get_all("/api/ignition-delay/", datapoint__temperature__gte=1000))
print(f"{len(points)} datapoints")

for p in points[:5]:
    q = p.get("ignition_delay_quantity") or {}
    print(p["ignition_target"], q.get("value"), q.get("units"))
```

## Plotting ignition delay vs. 1000/T

```python
import requests
import matplotlib.pyplot as plt

BASE = "https://dev.omethe.us"
resp = requests.get(f"{BASE}/api/datapoint-result/", params={"success": "true"})
rows = resp.json()["results"]

T = [r["temperature"] for r in rows if r["temperature"]]
tau_exp = [r["experimental_ignition_delay"] for r in rows]
plt.semilogy([1000.0 / t for t in T], tau_exp, "o")
plt.xlabel("1000 / T  [1/K]"); plt.ylabel("ignition delay [s]")
plt.show()
```
