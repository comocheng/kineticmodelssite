# MATLAB examples

Using `webread` / `weboptions`. MATLAB decodes JSON into structs automatically.

```matlab
base = "https://dev.omethe.us";   % replace with your deployment

% Reads are public; for writes add an Authorization header:
% opts = weboptions("HeaderFields", ["Authorization" "Token <your-token>"]);
opts = weboptions("Timeout", 30);

url = base + "/api/ignition-delay/?datapoint__temperature__gte=1000";
data = webread(url, opts);

fprintf("%d datapoints\n", data.count);
results = data.results;
for k = 1:min(5, numel(results))
    q = results(k).ignition_delay_quantity;
    fprintf("%s: %g %s\n", results(k).ignition_target, q.value, q.units);
end
```

## Page through all results

```matlab
function rows = get_all(path, query)
    base = "https://dev.omethe.us";
    url = base + path + query;
    rows = [];
    opts = weboptions("Timeout", 30);
    while ~isempty(url)
        data = webread(url, opts);
        rows = [rows; data.results]; %#ok<AGROW>
        if isempty(data.next), break; end
        url = string(data.next);
    end
end

rows = get_all("/api/datapoint-result/", "?success=true");
T = [rows.temperature];
tau = [rows.experimental_ignition_delay];
semilogy(1000 ./ T, tau, "o");
xlabel("1000/T [1/K]"); ylabel("ignition delay [s]");
```
