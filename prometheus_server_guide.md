# Prometheus Server Setup Guide
## Nginx vs Apache Comparison + Complete Installation from Scratch

**Prosper Lekia — Northeastern University, West Lab**
**February 2026**

---

## Nginx vs Apache: Head-to-Head Comparison

| Aspect | Nginx | Apache | Winner for Prometheus |
|--------|-------|--------|---------------------|
| **Architecture** | Event-driven, asynchronous (one process handles thousands of connections) | Process/thread-per-connection (one thread per active request) | **Nginx** — importer status polling creates many long-lived connections |
| **Concurrency** | Handles 10,000+ simultaneous connections with ~2MB RAM | ~256 default workers; each uses 2-10MB RAM | **Nginx** — multiple users browsing while importer runs |
| **Static file serving** | Serves directly from disk at near-kernel speed | Routes through mod_wsgi unless you add separate alias config | **Nginx** — species images, CSS, JS served without touching Python |
| **Reverse proxy** | Built-in, first-class feature (proxy_pass) | Requires mod_proxy + mod_proxy_http modules | **Nginx** — Gunicorn reverse proxy is the standard Django deployment |
| **Memory usage** | ~2-5 MB per worker process | ~10-50 MB per worker thread/process | **Nginx** — office server has limited RAM |
| **Configuration** | Declarative blocks, simple for reverse proxy setups | .htaccess files, XML-like directives, more verbose | **Nginx** — cleaner config for your use case |
| **SSL/TLS** | Native, fast, easy Let's Encrypt integration | Native, slightly more config steps | **Tie** |
| **Long polling / WebSocket** | Native support, excellent for importer status updates | Requires mod_proxy_wstunnel, less stable | **Nginx** — dashboard polling importer job status |
| **File uploads** | Simple client_max_body_size directive | LimitRequestBody + mod configuration | **Nginx** — mechanism file uploads (5-50 MB) |
| **URL rewriting** | Built-in, regex-based | mod_rewrite (powerful but complex syntax) | **Tie** |
| **Dynamic content** | Cannot run Python directly — always proxies to app server (this is correct design) | Can embed Python via mod_wsgi (tighter coupling, harder to debug) | **Nginx** — separation of concerns is cleaner |
| **.htaccess support** | No (all config in main files) | Yes (per-directory overrides) | **Apache** — but you don't need this |
| **Module ecosystem** | Smaller, covers common needs | Massive, covers edge cases | **Apache** — but you don't need exotic modules |
| **PHP support** | Via FastCGI (external process) | mod_php (embedded, fast) | **Apache** — but you're not using PHP |
| **Documentation** | Excellent, concise | Excellent, verbose | **Tie** |
| **Market share (2025)** | ~34% of all websites | ~29% of all websites | **Nginx** leads |
| **Used by** | Netflix, Dropbox, GitHub, WordPress.com | Many legacy enterprise apps, shared hosting | Nginx is standard for modern Python web apps |
| **Django community recommendation** | ✅ Recommended (Nginx + Gunicorn is the standard) | Possible but less common (Apache + mod_wsgi) | **Nginx** |
| **Debugging** | Access/error logs, simple to parse | Access/error logs, more verbose | **Tie** |
| **Reload without downtime** | `nginx -s reload` — zero-downtime config reload | `apachectl graceful` — brief interruption possible | **Nginx** |
| **CPU usage under load** | Lower (event loop, no thread context switching) | Higher (thread scheduling overhead) | **Nginx** |
| **When Apache wins** | Never for your use case | Shared hosting, PHP apps, .htaccess needed, mod_rewrite-heavy legacy apps | Not applicable |

**Bottom line:** For a Django + Gunicorn + Celery + PostgreSQL stack serving a scientific database with long-running background jobs, Nginx is the standard choice. Apache would work but adds complexity for no benefit.

---

## Complete Setup: Ubuntu Server from Scratch

The following setup script installs and configures everything needed to run the full Prometheus stack on a fresh Ubuntu 22.04 or 24.04 server.
