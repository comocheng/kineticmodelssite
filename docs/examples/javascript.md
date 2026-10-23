# JavaScript examples

Using the built-in `fetch` (browser or Node.js 18+).

```javascript
const BASE = "https://dev.omethe.us"; // replace with your deployment

async function getAll(path, params = {}) {
  let url = new URL(BASE + path);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const out = [];
  while (url) {
    const res = await fetch(url, {
      // headers: { Authorization: "Token <your-token>" }, // only for writes
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    out.push(...data.results);
    url = data.next ? new URL(data.next) : null;
  }
  return out;
}

// Ignition-delay datapoints at/above 1000 K
const points = await getAll("/api/ignition-delay/", {
  datapoint__temperature__gte: 1000,
  ordering: "datapoint__temperature",
});
console.log(`${points.length} datapoints`);
points.slice(0, 5).forEach((p) =>
  console.log(p.ignition_target, p.ignition_delay_quantity?.value, p.ignition_delay_quantity?.units),
);
```

!!! note "CORS"
    For browser apps on another origin, the server must allow your origin via CORS.
    Server-side (Node) calls are unaffected.
