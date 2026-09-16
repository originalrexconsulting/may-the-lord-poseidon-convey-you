# Audio stack for the ThinkPad: Ansible instructions

For the Claude Code agent maintaining the laptop playbook. Read SYSTEM.md first.

Target end state: PipeWire owns the Rotel A14 MKII, sample rate follows the source, Strawberry plays through PipeWire. This replaces PulseAudio, which is what the laptop was running as of 2026-09-11.

Host: the listening laptop (Debian 13 trixie). Rotel appears as ALSA card `R20`.

Debian 13 ships PipeWire as the default audio server. The laptop running PulseAudio means it was carried over from an upgrade or installed explicitly. The playbook brings it in line with the trixie default; nothing here is exotic.

## Why this design

- PipeWire with `allowed-rates` switches the DAC to the file's rate instead of resampling. Bit-perfect in practice without exclusive `hw:` access.
  The switch only happens when the device is idle and PipeWire re-opens it: a sink that is already `RUNNING` keeps its current rate and resamples the new stream into it. Going straight from a 44.1 kHz show to a 48 kHz stream therefore stays at 44.1, with no second stream involved. Stop, let the sink suspend (a few seconds), then start the new source.
- All apps (Strawberry, browser for KDFC, archive.org) share the Rotel. No "device busy" errors.
- Debian is moving to PipeWire; PulseAudio config would be throwaway work.

Do not use exclusive ALSA `hw:` output or WirePlumber device-disable rules. Those were considered and rejected for this laptop.

## What the playbook must do

Add a role (suggest `audio`) or tasks block that is idempotent and safe to rerun.

### 1. Packages

Install:

```
pipewire
pipewire-audio
pipewire-pulse
pipewire-alsa
wireplumber
strawberry
alsa-utils
```

On trixie, `pipewire-pulse` conflicts with `pulseaudio`, so apt will remove `pulseaudio` when installing the list above. Let it; use `state: absent` for `pulseaudio` explicitly so the play is honest about it. Keep `pulseaudio-utils` (provides `pactl`, works against pipewire-pulse). Add `gstreamer1.0-pipewire` to the list.

### 2. User services (run as `cp`, `scope: user`)

Disable and mask:

```
pulseaudio.service
pulseaudio.socket
```

Enable and start:

```
pipewire.service
pipewire.socket
pipewire-pulse.service
pipewire-pulse.socket
wireplumber.service
```

Ansible `systemd` module with `scope: user` needs `XDG_RUNTIME_DIR=/run/user/<uid>` and `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus` in `environment:`. Get uid with `getent passwd cp`. Do not run these tasks with `become: true` targeting root.

A logout/login (or reboot) is required once after the PulseAudio to PipeWire switch. The playbook should print a debug message when the pulse services were actually changed, not fail or reboot on its own.

### 3. PipeWire rate config

File: `~cp/.config/pipewire/pipewire.conf.d/10-rates.conf`
Owner `cp:cp`, mode `0644`. Create parent dirs.

```
context.properties = {
  default.clock.rate = 44100
  default.clock.allowed-rates = [ 44100 48000 88200 96000 176400 192000 ]
}
```

Rationale: Dead shows are 44.1 kHz, DAT captures are 48 or 32 kHz, TV/optical is 48. The list covers everything the A14 accepts. `default.clock.rate` is the rate the DAC idles at and the one it falls back to, so a 44.1 kHz source is indistinguishable from a resampled one by rate alone -- test rate switching with a 48 kHz source.

Notify a handler that restarts `pipewire` and `wireplumber` in user scope when this file changes.

### 3b. WirePlumber default-sink rule

File: `~cp/.config/wireplumber/wireplumber.conf.d/51-rotel-default.conf`
Owner `cp:cp`, mode `0644`. Create parent dirs.

```
monitor.alsa.rules = [
  {
    matches = [ { node.name = "~alsa_output.usb-ROTEL.*" } ]
    actions = { update-props = { priority.session = 3000, priority.driver = 3000 } }
  }
]
```

Rationale: the internal card's Pro Audio profile has `priority.session` 1500 and the Rotel 1009, so WirePlumber never chose the Rotel on plug-in (found 2026-09-12; fixed by hand that day with `wpctl set-default`, which WirePlumber also remembers in `~/.local/state/wireplumber/default-nodes`). The rule makes it deterministic. Same restart handler as the rates file.

### 4. Strawberry config

Strawberry stores settings in `~cp/.config/strawberry/strawberry.conf` (INI). Set only these keys; do not template the whole file, it contains UI state.

```
[Backend]
engine=gstreamer
output=pipewiresink
device=@Invalid()
```

If `pipewiresink` is unavailable in the installed GStreamer (`gst-inspect-1.0 pipewiresink` returns nonzero), fall back to:

```
output=pulsesink
```

which reaches PipeWire through pipewire-pulse. Either is fine; `pipewiresink` is preferred. Install `gstreamer1.0-pipewire` to get it.

Use `community.general.ini_file` for these keys. Strawberry must not be running when the file is edited; check with `pgrep -u cp strawberry` and skip with a warning rather than clobbering.

### 5. Verification tasks (tagged `verify`, `changed_when: false`)

- `pactl info` reports `Server Name: PulseAudio (on PipeWire ...)`
- `wpctl status` lists the Rotel under Audio Sinks
- `fuser -v /dev/snd/*` shows `pipewire`, not `pulseaudio`
- Optional, and order-dependent: stop playback first, wait for the sink to reach `SUSPENDED` (`pactl list sinks short`, a few seconds; `hw_params` then reads `closed`), and only then start a 48 kHz source. `cat /proc/asound/R20/pcm0p/sub0/hw_params` shows `rate: 48000`. Run against a still-`RUNNING` sink it reports `44100` and looks like a broken config when nothing is wrong. `scripts/radio.py`'s `ddur` station is 16/48 and exists for this test.

Fail the play if the first three don't hold after a login cycle.

## Rollback

Reinstall `pulseaudio` (apt will remove `pipewire-pulse`) and reverse the service enable/disable in step 2. Keep a `pulseaudio_rollback: false` variable so this is one flag flip. Unlikely to be needed on trixie; PipeWire is the tested default there.

## Conventions

- Idempotent. Rerunning must produce zero changes.
- No `shell:` where a module exists. `shell:` only for `wpctl`/`pactl` checks.
- Tag everything `audio`. Verification tasks also tagged `verify`.
- Don't touch `/etc/pipewire`. All config is per-user under `~cp/.config`.
- Report what changed in one short summary, verdict first.
