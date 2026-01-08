"""Canonical NATS/JetStream names (subjects/streams/durables) for QIKI_DTMP.

Keep these as the single source of truth to avoid drift between services.
"""

from __future__ import annotations

# Streams
RADAR_STREAM_NAME = "QIKI_RADAR_V1"
EVENTS_STREAM_NAME = "QIKI_EVENTS_V1"

# JetStream durable consumer names
RADAR_FRAMES_DURABLE = "radar_frames_pull"
RADAR_TRACKS_DURABLE = "radar_tracks_pull"
OPERATOR_CONSOLE_RADAR_SR_DURABLE = "operator-console-sr"
OPERATOR_CONSOLE_RADAR_LR_DURABLE = "operator-console-lr"
OPERATOR_CONSOLE_TRACKS_DURABLE = "operator-console-tracks"

# Radar subjects
RADAR_FRAMES = "qiki.radar.v1.frames"
RADAR_FRAMES_LR = "qiki.radar.v1.frames.lr"
RADAR_TRACKS = "qiki.radar.v1.tracks"
RADAR_TRACKS_SR = "qiki.radar.v1.tracks.sr"

# Telemetry subjects
SYSTEM_TELEMETRY = "qiki.telemetry"

# Control subjects
COMMANDS_CONTROL = "qiki.commands.control"
RESPONSES_CONTROL = "qiki.responses.control"

# QIKI interaction subjects (operator intents, agent replies)
QIKI_INTENT_V1 = "qiki.intent.v1"
QIKI_PROPOSALS_V1 = "qiki.proposals.v1"

# QIKI environment mode (QCore is the source of truth)
QIKI_ENVIRONMENT_V1 = "qiki.environment.v1"
QIKI_ENVIRONMENT_SET_V1 = "qiki.environment.v1.set"

# Backward-compat alias: prefer QIKI_INTENT_V1.
QIKI_INTENTS = QIKI_INTENT_V1

# Events subjects
EVENTS_V1_WILDCARD = "qiki.events.v1.>"
EVENTS_AUDIT = "qiki.events.v1.audit"
