# Dockerfile
### Builder stage: install packages into /install ###
FROM python:3.13-alpine AS builder

# build deps only
RUN apk add --no-cache \
      gcc musl-dev libffi-dev openssl-dev

WORKDIR /app
COPY src/requirements.txt .

# install into a staging dir, without cache
RUN pip install \
      --prefix=/install \
      --no-cache-dir \
      -r requirements.txt

### Final stage: minimal runtime ###
FROM python:3.13-alpine

# runtime dependencies
RUN apk add --no-cache \
      bash       \
      ffmpeg     \
      grep       \
      sed        \
      curl       \
      mpv        \
      aria2      \
      fzf        \
      patch


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# copy only the installed libraries
COPY --from=builder /install /usr/local

WORKDIR /app
COPY src/ .

# -OO strips docstrings; use ENTRYPOINT so you can still override
ENTRYPOINT ["python", "-OO", "main.py"]
