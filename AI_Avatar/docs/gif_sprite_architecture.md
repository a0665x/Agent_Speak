# Henry GIF / Sprite Architecture

## 1. Why use clips instead of arbitrary GIF switching

Every animation is treated as a clip with metadata:

- clip ID
- source sheet
- frame count
- FPS
- loop flag
- duration
- return state
- transition policy

## 2. Clip categories

### Persistent loops

- idle_loop
- listening_loop
- thinking_loop
- speaking_neutral_loop
- speaking_happy_loop
- sleepy_doze_loop
- ear_sway_loop

### One-shot reactions

- happy_once
- laugh_once
- pout_once
- surprised_once
- sorry_once
- head_nod_once
- head_shake_once
- ear_twitch_once
- paw_wave_once
- point_left_once
- point_right_once
- hands_together_once
- thumbs_up_once

## 3. Anchor pose

All clips should render into a fixed viewport and align to one anchor:

```text
viewport: 512 × 512
anchor_x: 0.5
anchor_y: 0.92
fit: contain
```

## 4. Transition algorithm

```text
current persistent clip
    ↓
optional transition clip
    ↓
new persistent clip
```

For one-shot reactions:

```text
persistent clip
    ↓
one-shot reaction
    ↓
return to persistent clip
```

## 5. React recommendation

For exact control, use PNG sequences rather than raw GIF completion events.
A requestAnimationFrame or timer loop advances frames according to FPS.

## 6. Preloading

Preload all persistent clips at startup and preload one-shot clips on first use.
