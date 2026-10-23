# R examples

Using `httr2` and `jsonlite`.

```r
library(httr2)
library(jsonlite)

base <- "https://dev.omethe.us"   # replace with your deployment

# Ignition-delay datapoints at/above 1000 K
resp <- request(base) |>
  req_url_path("/api/ignition-delay/") |>
  req_url_query(datapoint__temperature__gte = 1000, ordering = "datapoint__temperature") |>
  # req_headers(Authorization = "Token <your-token>") |>   # only for writes
  req_perform()

data <- resp_body_json(resp, simplifyVector = TRUE)
cat(data$count, "datapoints\n")
head(data$results)
```

## Page through all results

```r
library(httr2)

get_all <- function(path, ...) {
  base <- "https://dev.omethe.us"
  url <- paste0(base, path)
  out <- list()
  query <- list(...)
  repeat {
    resp <- request(url) |> req_url_query(!!!query) |> req_perform()
    body <- resp_body_json(resp, simplifyVector = TRUE)
    out <- c(out, list(body$results))
    if (is.null(body$`next`)) break
    url <- body$`next`; query <- list()
  }
  do.call(rbind, out)
}

df <- get_all("/api/datapoint-result/", success = "true")
plot(1000 / df$temperature, df$experimental_ignition_delay, log = "y",
     xlab = "1000/T [1/K]", ylab = "ignition delay [s]")
```
