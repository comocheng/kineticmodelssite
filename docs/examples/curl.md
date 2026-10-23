# cURL examples

Reads are public; add `-H "Authorization: Token <your-token>"` only for
contribution/admin endpoints. Replace the host with your deployment.

## List with a filter

```bash
curl "https://dev.omethe.us/api/ignition-delay/?datapoint__temperature__gte=1000&ordering=datapoint__temperature"
```

## Page through results

```bash
curl "https://dev.omethe.us/api/experiment-datapoint/?page=2&pressure__gte=100000"
```

## Pretty-print and extract with jq

```bash
curl -s "https://dev.omethe.us/api/ignition-delay/?datapoint__temperature__gte=1200" \
  | jq '.results[] | {t: .ignition_delay_quantity.value, target: .ignition_target}'
```

## Find datasets containing a species (by CAS)

```bash
curl -s "https://dev.omethe.us/api/composition-species/?cas=74-82-8" | jq '.count'
```

## Authenticated: contribution status

```bash
curl -H "Authorization: Token <your-token>" \
  "https://dev.omethe.us/api/contribute/status/123/"
```
