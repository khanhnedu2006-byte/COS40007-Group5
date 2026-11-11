# Optional public testing

The app runs locally by default. `start.bat`, `demo.bat`, the Python launcher and ordinary `docker compose up` do not start a public tunnel. Public testing is an explicit Docker Compose profile; it uses the same frontend, API, dataset and 1.5 km area estimates as the official local run.

This first hosting option uses a [Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/). It gives the running application a temporary HTTPS address without a Cloudflare account or domain. It is for testing, not permanent hosting: the address changes between tunnel sessions, and availability depends on the host computer, its internet connection and the tunnel service. Anyone with the URL can access the application while the tunnel runs.

## Prerequisites

- Windows: install and start Docker Desktop with Linux containers enabled.
- Linux: install Docker Engine and the Docker Compose plugin using the [official Docker installation guide](https://docs.docker.com/engine/install/).
- Have the official data/model files described in the README, or explicitly choose demo mode.
- Run all commands below from the repository root. Verify `docker compose version` works.

The tunnel connects outbound; no router port forwarding is needed. Requests reach the frontend's Nginx server, which forwards `/api/` to FastAPI inside Docker. Browser requests use the same public origin, so no public backend URL or CORS changes are required. Host ports remain bound to `127.0.0.1`.

## 1. Check the application locally

Stop an existing Python launcher or manually started API on port 8000 before starting the container stack.

```sh
docker compose up -d --build --wait
```

Open **http://127.0.0.1:8080** and select a location. Check the prediction and 1.5 km circle before enabling public access. The default mode is `actual`, selecting recorded data or the registered trained model.

For a simulated test without local data, set the mode first:

```powershell
# Windows PowerShell
$env:SPEEDMAP_MODE = 'demo'
docker compose up -d --build --wait
```

```bash
# Linux Bash
SPEEDMAP_MODE=demo docker compose up -d --build --wait
```

Keep that mode when running later Compose commands. In Bash, prefix them with `SPEEDMAP_MODE=demo` too; in PowerShell the environment setting stays active in the current terminal. To return to official mode, set `SPEEDMAP_MODE` to `actual` and recreate the stack.

## 2. Enable public testing explicitly

Once the local stack is healthy:

```sh
docker compose --profile online up -d --no-deps public-tunnel
docker compose logs -f public-tunnel
```

`--no-deps` leaves the already running local services as they are and skips dependency health checks; only use this command after step 1 succeeds. Find the **`https://…trycloudflare.com`** address in the output. Press **Ctrl+C** to leave the log view; this does not stop the tunnel.

Open the printed address on a phone using mobile data or on another computer outside your network. Confirm that the page loads, the API connects, and a location selection produces the point estimate, radius circle and area summary. The local address continues working at the same time.

Alternatively, to start everything with public testing enabled in a single command:

```sh
docker compose --profile online up -d --build
docker compose logs -f public-tunnel
```

The tunnel service starts only after the frontend health check succeeds in this full-stack command.

## 3. End public access and continue locally

```sh
docker compose --profile online stop public-tunnel
```

The public address stops serving the app; the local site remains at **http://127.0.0.1:8080**. Stopping the tunnel does not stop the backend or frontend. To stop and remove the entire container stack:

```sh
docker compose --profile online down
```

To return to the normal desktop launcher after shutting down Docker services, run `start.bat` on Windows or `python3 scripts/launch.py actual` on Linux.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `docker` not found / daemon unavailable | Install Docker and start its engine; verify `docker compose version`. |
| Local stack is unhealthy | Run `docker compose ps` and `docker compose logs backend frontend`. Fix missing data/model files before enabling the tunnel. |
| No HTTPS URL appears | Inspect `docker compose logs public-tunnel`; check outbound internet/firewall access. If using the staged command, ensure the local stack is running first. |
| Public page reports a gateway error | Confirm the local site at port 8080 works, inspect frontend/backend logs, then restart the tunnel with `docker compose --profile online restart public-tunnel`. |
| URL has stopped working | Keep the host awake and containers running. Obtain the current URL from the logs after restarting the tunnel. |
| A later Compose run unexpectedly starts online | Remove `online` from `COMPOSE_PROFILES` in the shell or `.env`. This project does not enable that environment variable by default. |

There is no automatic public fallback when local connectivity fails, and the application does not require this tunnel for local use. For a stable domain and an always-on deployment, the next step is a server deployment with a named tunnel or HTTPS reverse proxy; the current Quick Tunnel intentionally remains a temporary testing option.
