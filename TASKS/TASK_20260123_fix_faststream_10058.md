# TASK: Fix JetStream warning 10058 (faststream-bridge)

Status: done
Date: 2026-01-23

## Goal

Eliminate `BadRequestError: err_code=10058 description='stream name already in use with a different configuration'` on faststream-bridge startup.

## Root cause

`faststream-bridge` subscribed with `stream="QIKI_RADAR_V1"` and FastStream attempted to declare the stream using a different subjects config than the canonical stream created by `nats-js-init` (which uses `RADAR_SUBJECTS=qiki.radar.v1.*`).

## Fix

Bind to the existing stream without declaring it:

- `src/qiki/services/faststream_bridge/app.py`: use `stream=JStream(name=RADAR_STREAM, declare=False)`.

## Evidence

After (rebuild/restart faststream-bridge and scan logs):

Command:

`docker compose -f docker-compose.phase1.yml restart faststream-bridge && docker compose -f docker-compose.phase1.yml logs --since 2m faststream-bridge | rg -n "10058|different configuration|stream name already"`

Output:

```text
(no output)
```

Startup looks clean (excerpt):

```text
FastStream app starting...
FastStream bridge service has started.
JetStream lag monitor started for stream QIKI_RADAR_V1 consumers=['radar_frames_pull', 'radar_tracks_pull']
`HandleRadarFrame` waiting for messages
FastStream app started successfully!
```

Radar still flows (example):

```text
Radar frame received: frame_id=36d5a5d3-a24c-4c67-b9e6-498cb41c42c9 detections=2
```
