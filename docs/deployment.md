# Deployment, offline transfer, and recovery

## Local single-host deployment

Copy `.env.example` to `.env`, review the loopback host and origin values, then run `docker compose up --build -d` from the repository root. `docker compose ps` should show a healthy `app`; `/ready` returns `{"status":"ready"}` only when the expected migration is applied. The browser URL is `http://127.0.0.1:8000` unless `HOST_PORT` is changed. Change `ALLOWED_ORIGINS` to include the exact new browser origin when changing that port. The database is `/data/sat-sa.db` inside the named volume. The container runs as UID/GID 10001 with one Uvicorn worker.

For normal updates, take a backup first, build the new image, and run `docker compose up --no-build --pull never -d`. Compose replaces the container and keeps the data volume. Do not remove volumes during updates. A rollback uses a compatible earlier image *and a backup from before its migrations*; schema downgrades are not the recovery strategy. The MVP has no authentication, so keep it on loopback or behind an existing private authenticated gateway. Do not expose the service directly to the Internet.

## Build once and start without a registry

On a connected build machine, build the image and save it outside Git:

```powershell
docker compose build
docker save -o sat-sa-mvp.tar sat-sa:mvp
Get-FileHash sat-sa-mvp.tar -Algorithm SHA256
```

On POSIX, `sha256sum sat-sa-mvp.tar` gives the checksum. Transfer the archive, its recorded checksum, `compose.yaml`, and a prepared `.env` with `APP_IMAGE=sat-sa:mvp` to the target. Verify the checksum there, then:

```powershell
docker load -i sat-sa-mvp.tar
docker compose up --no-build --pull never -d
docker compose ps
```

The target needs a compatible Docker engine, Compose, and enough disk space. Source builds and package installation are not claimed to work offline. The tested packaged browser flow made no external requests; actual network isolation remains an environment setting.

## Consistent backups

Never copy only the live `.db` file while writes and SQLite WAL are active. The included helper uses SQLite's backup API, checks integrity and foreign keys, and refuses to overwrite a destination:

```powershell
docker compose exec -T app python scripts/sqlite_copy.py backup /data/sat-sa.db /data/backups/review-20261001.db
New-Item -ItemType Directory -Force backups
docker compose cp app:/data/backups/review-20261001.db ./backups/review-20261001.db
```

On POSIX, replace `New-Item -ItemType Directory -Force backups` with `mkdir -p backups`. Store the downloaded backup separately from the host and protect it as sensitive data: it includes submitted CSV bytes and review notes. The local `backups/` directory is ignored by Git.

To verify or use a restore, start with an **empty** destination volume. Copy the backup into a running instance's `/data/backups` if it is not already there:

```powershell
docker compose exec -T app mkdir -p /data/backups
docker compose cp ./backups/review-20261001.db app:/data/backups/review-20261001.db
$sourceVolume = ((docker inspect (docker compose ps -q app) | ConvertFrom-Json).Mounts | Where-Object Destination -eq '/data').Name
docker volume create sat_sa_restored
docker run --rm --mount type=volume,source=sat_sa_restored,target=/data --mount "type=volume,source=$sourceVolume,target=/source,readonly" sat-sa:mvp python scripts/sqlite_copy.py restore /source/backups/review-20261001.db /data/sat-sa.db
```

On POSIX, use `source_volume=$(docker inspect "$(docker compose ps -q app)" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')` and substitute `$source_volume` in the second mount. Mount `sat_sa_restored` at `/data` in a separate deployment, or run a temporary container with that volume and a different loopback host port to verify `/ready`, submission counts, and saved reviews. The helper refuses to overwrite an existing database, protecting a live deployment from an accidental restore. This procedure was tested with a fresh Docker volume and matched the original three submissions, three assessments, review-state counts, and review-event count.
