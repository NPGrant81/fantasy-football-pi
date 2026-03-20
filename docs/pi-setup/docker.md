# Raspberry Pi Docker Engine + Portainer Setup

Issue reference: `#299`

This runbook installs Docker Engine (Docker CE) on Raspberry Pi OS (Debian Bookworm, ARM64), enables Docker Compose v2, and optionally installs Portainer CE.

## 1. Prerequisites

- Raspberry Pi OS based on Debian Bookworm
- `pi` user with `sudo` access
- Internet access from the Pi

Optional validation:

```bash
uname -m
cat /etc/os-release
```

Expected architecture for this guide: `aarch64` / `arm64`.

## 2. Install Docker Engine (Docker CE)

Install prerequisite packages:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
```

Add Docker's official GPG key:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

Add Docker APT repository:

```bash
echo \
  "deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Install Docker Engine and plugins:

```bash
sudo apt-get update
sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

Enable and start Docker:

```bash
sudo systemctl enable --now docker
sudo systemctl status docker --no-pager
```

Add `pi` user to Docker group:

```bash
sudo usermod -aG docker pi
```

Apply group membership in current shell:

```bash
newgrp docker
```

Validate Docker install:

```bash
docker run --rm hello-world
```

## 3. Validate Docker Compose v2

```bash
docker compose version
docker compose ls
```

## 4. Optional: Install Portainer CE

Create Portainer data volume:

```bash
docker volume create portainer_data
```

Run Portainer:

```bash
docker run -d \
  -p 9000:9000 \
  -p 8000:8000 \
  --name portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

Validate container status:

```bash
docker ps --filter name=portainer
```

UI access:

- `http://<pi-ip>:9000`
- Create admin user on first launch and attach the local Docker environment.

## 5. Update and Maintenance

Update Docker Engine and plugins:

```bash
sudo apt-get update
sudo apt-get install --only-upgrade -y \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl restart docker
```

Confirm versions after update:

```bash
docker version
docker compose version
```

## 6. Troubleshooting

### Permission denied on Docker socket

Symptom:

```text
Got permission denied while trying to connect to the Docker daemon socket
```

Fix:

```bash
sudo usermod -aG docker pi
newgrp docker
docker ps
```

### Docker service not running

```bash
sudo systemctl status docker --no-pager
sudo journalctl -u docker -n 100 --no-pager
sudo systemctl restart docker
```

### Compose command not found

Use `docker compose` (space), not `docker-compose` (hyphen), and confirm plugin install:

```bash
sudo apt-get install -y docker-compose-plugin
docker compose version
```

### Portainer not reachable

```bash
docker logs --tail 100 portainer
sudo ss -tulpn | grep 9000
```

If Nginx reverse proxy is used for Portainer, also validate Nginx site config and port bindings.

## 7. Acceptance Checklist

- [ ] Docker Engine installed and `docker` service active
- [ ] Docker Compose plugin installed and `docker compose version` succeeds
- [ ] `pi` user can run Docker commands without `sudo`
- [ ] Portainer reachable (if installed)
- [ ] Commands and troubleshooting documented in this runbook