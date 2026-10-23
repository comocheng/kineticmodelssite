# Java examples

Using the JDK 11+ `java.net.http.HttpClient`. (For a fully typed client, generate the
Java SDK — see [Client SDKs](../clients.md).)

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class PrometheusExample {
    static final String BASE = "https://dev.omethe.us"; // replace

    public static void main(String[] args) throws Exception {
        HttpClient client = HttpClient.newHttpClient();

        String url = BASE + "/api/ignition-delay/"
                + "?datapoint__temperature__gte=1000&ordering=datapoint__temperature";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                // .header("Authorization", "Token <your-token>")  // only for writes
                .GET()
                .build();

        HttpResponse<String> response =
                client.send(request, HttpResponse.BodyHandlers.ofString());

        System.out.println("HTTP " + response.statusCode());
        System.out.println(response.body()); // parse with Jackson/Gson as needed
    }
}
```

For JSON parsing and paging across `next`, use a library such as Jackson and follow the
`next` URL until it is `null` — the same pattern shown in the
[Python](python.md) and [JavaScript](javascript.md) examples.
