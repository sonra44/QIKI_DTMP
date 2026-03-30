# tmux Mouse Wheel Passthrough (ORION Radar Zoom)

ORION radar uses the mouse wheel for zoom. In `tmux` with `set -g mouse on`, wheel events are often captured by tmux
scrollback instead of being forwarded to full-screen apps (alternate screen).

## Goal

- In ORION (full-screen), wheel events go to the app (zoom works).
- Outside full-screen apps, wheel scrolls tmux history (copy-mode).

## Recommended tmux config

Add to `~/.tmux.conf`:

```tmux
# Enable mouse support (required for wheel events).
set -g mouse on

# Forward wheel events to full-screen apps (alternate screen),
# otherwise use tmux scrollback (copy-mode).
bind -n WheelUpPane if-shell -F "#{alternate_on}" "send-keys -M" "copy-mode -e; send-keys -M"
bind -n WheelDownPane if-shell -F "#{alternate_on}" "send-keys -M" "copy-mode -e; send-keys -M"
```

Reload config:

```tmux
tmux source-file ~/.tmux.conf
```

## Notes

- If you do not want tmux mouse at all, disable it with `set -g mouse off` and rely on terminal scrollback.
- Some SSH clients/terminals do not forward mouse events through to tmux reliably; ORION still has keyboard controls
  and Docker-first headless proofs.

