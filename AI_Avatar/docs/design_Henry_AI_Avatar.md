# Henry AI Avatar — Dynamic Character Design Specification

> File: `design_Henry_AI Avatar.md`<br>
> Version: 0.1<br>
> Purpose: Define the visual design, animation actions, runtime interfaces, state machine, and asset requirements for the Henry AI Avatar used in a WebUI with ASR, LLM, and TTS.

---

## 1. Product Goal

Henry is a cute, chibi-style AI assistant displayed inside a WebUI.<br>
The character should communicate system status through facial expressions, ear movement, body motion, gestures, and speech animation.

Henry is not just a static icon. It is a **state-driven animated avatar**.

The avatar must make it easy for users to understand whether Henry is:

- waiting
- listening
- recognizing speech
- thinking
- speaking
- happy
- confused
- interrupted
- sleeping
- disconnected
- experiencing an error

The core design principle is:

> Every important system state should have a clearly recognizable visual behavior.

---

## 2. Character Identity

### 2.1 Core appearance

Henry is a soft brown lop-eared rabbit with:

- large round eyes
- round black glasses
- soft fluffy cheeks
- short muzzle
- small rounded paws
- oversized head and compact body
- long flexible ears
- white assistant shirt
- dark tie
- lavender lanyard
- readable name badge marked `Henry`

### 2.2 Personality

Henry should feel:

- friendly
- curious
- reliable
- slightly playful
- intelligent but not overly serious
- emotionally expressive
- safe and approachable

### 2.3 Visual proportions

Recommended chibi proportions:

- head: approximately 55–65% of total body height
- eyes: large enough to remain readable at 160–300 px display size
- body: compact and rounded
- hands/paws: simplified and readable
- ears: long enough to create secondary motion
- silhouette: recognizable even without facial details

### 2.4 Main visual language

Use:

- rounded forms
- soft contours
- large emotional eyes
- small mouth
- soft fabric and fur appearance
- limited accessory complexity
- clean silhouette
- lavender accent color for AI/helper identity

Avoid:

- overly realistic anatomy
- too many small details
- stiff ears
- overly dark or intimidating shadows
- expressions that depend only on small mouth changes
- clothing that blocks body deformation

---

## 3. Display Modes

Henry should support three display sizes.

### 3.1 Icon mode

Use for:

- sidebar icon
- account avatar
- notification badge
- minimized assistant

Recommended output:

- 64 × 64
- 128 × 128
- 256 × 256

Animation:

- blink
- tiny bounce
- small ear sway
- status ring

### 3.2 Bust mode

Use for:

- chat window
- voice assistant panel
- floating assistant bubble

Visible area:

- head
- upper body
- hands
- name badge

This should be the primary MVP mode.

### 3.3 Full-body mode

Use for:

- onboarding
- dashboard home screen
- tutorial scenes
- celebration animation
- larger desktop companion mode

Full-body mode can include:

- stepping
- jumping
- bowing
- pointing
- turning
- sitting
- sleeping

---

## 4. Recommended Rendering Architecture

The preferred implementation is:

> Layered 2D avatar + runtime animation controller + event-driven state machine

Possible rendering technologies:

1. Live2D Cubism
2. Rive
3. Spine 2D
4. PixiJS with layered sprites
5. SVG + CSS animation
6. Canvas/WebGL custom renderer

For the first implementation, use one of these approaches:

### MVP

- layered PNG/WebP assets
- CSS or Framer Motion
- WebSocket events
- audio-volume-driven mouth animation

### Production

- Live2D or Rive rig
- viseme-based lip sync
- expression blending
- physics-based ear movement
- gaze tracking
- gesture sequencing

---

## 5. Asset Layer Specification

The source artwork should be prepared in layers so the character can be rigged.

### 5.1 Head layers

```text
Head_Base
Face_Fur
Cheek_L
Cheek_R
Muzzle
Nose
Hair_Tuft
Ear_L_Base
Ear_L_Mid
Ear_L_Tip
Ear_R_Base
Ear_R_Mid
Ear_R_Tip
Ear_L_Inner
Ear_R_Inner
```

Each ear should be divided into at least three deformable sections:

- base
- middle
- tip

This allows:

- delayed sway
- soft head-shake follow-through
- bouncing
- gravity response
- asymmetric ear reactions

### 5.2 Eye layers

```text
Eye_L_White
Eye_L_Iris
Eye_L_Pupil
Eye_L_Highlight
Eye_L_UpperLid
Eye_L_LowerLid

Eye_R_White
Eye_R_Iris
Eye_R_Pupil
Eye_R_Highlight
Eye_R_UpperLid
Eye_R_LowerLid
```

Additional expression layers:

```text
Eye_Happy
Eye_Squint
Eye_Surprised
Eye_Sleepy
Eye_Confused
```

### 5.3 Eyebrow layers

```text
Brow_L
Brow_R
```

Eyebrows must support:

- vertical movement
- rotation
- inward tilt
- outward tilt
- asymmetric expression

### 5.4 Mouth layers

Recommended mouth shapes:

```text
Mouth_Closed
Mouth_SmallOpen
Mouth_WideOpen
Mouth_RoundO
Mouth_Smile
Mouth_Frown
Mouth_Teeth
Mouth_Tongue
```

Production lip sync can map phonemes to visemes.

Recommended viseme set:

```text
sil
PP
FF
TH
DD
kk
CH
SS
nn
RR
aa
E
ih
oh
ou
```

### 5.5 Glasses layers

```text
Glasses_Frame
Glasses_Lens_L
Glasses_Lens_R
Glasses_Highlight
```

The glasses should move slightly after fast head movements to create soft secondary motion.

### 5.6 Body layers

```text
Body_Base
Shirt
Collar_L
Collar_R
Tie
Lanyard_L
Lanyard_R
NameBadge
Arm_L_Upper
Arm_L_Lower
Paw_L
Arm_R_Upper
Arm_R_Lower
Paw_R
Leg_L
Leg_R
Foot_L
Foot_R
Tail
Body_Shadow
```

The lanyard and badge should also have small delayed movement.

---

## 6. Core Runtime Parameters

The avatar runtime should expose normalized parameters where possible.

Recommended range:

- `-1.0` to `1.0` for directional parameters
- `0.0` to `1.0` for intensity parameters

### 6.1 Head and body parameters

```text
head_x
head_y
head_roll
body_x
body_y
body_roll
body_breath
body_bounce
```

### 6.2 Eye parameters

```text
eye_open_l
eye_open_r
eye_gaze_x
eye_gaze_y
blink
pupil_scale
```

### 6.3 Eyebrow parameters

```text
brow_l_y
brow_r_y
brow_l_angle
brow_r_angle
```

### 6.4 Mouth parameters

```text
mouth_open
mouth_form
mouth_smile
mouth_round
jaw_y
```

### 6.5 Ear parameters

```text
ear_l_base_angle
ear_l_mid_bend
ear_l_tip_bend
ear_r_base_angle
ear_r_mid_bend
ear_r_tip_bend
ear_l_gravity
ear_r_gravity
ear_sway
ear_alert
```

### 6.6 Hand and gesture parameters

```text
arm_l_raise
arm_r_raise
paw_l_open
paw_r_open
paw_wave
paw_point
hands_together
```

### 6.7 Accessory parameters

```text
glasses_x
glasses_y
glasses_roll
lanyard_sway
badge_sway
tie_sway
```

---

## 7. Avatar State Machine

Recommended top-level states:

```text
OFFLINE
BOOTING
IDLE
LISTENING
RECOGNIZING
THINKING
SPEAKING
INTERRUPTED
SUCCESS
CONFUSED
ERROR
SLEEPING
```

### 7.1 State transition flow

```text
OFFLINE
  -> BOOTING
  -> IDLE

IDLE
  -> LISTENING
  -> SLEEPING

LISTENING
  -> RECOGNIZING
  -> IDLE
  -> ERROR

RECOGNIZING
  -> THINKING
  -> LISTENING
  -> ERROR

THINKING
  -> SPEAKING
  -> CONFUSED
  -> ERROR

SPEAKING
  -> IDLE
  -> INTERRUPTED
  -> ERROR

INTERRUPTED
  -> LISTENING
  -> IDLE
```

---

## 8. State-to-Animation Mapping

## 8.1 IDLE

Visual behavior:

- slow breathing
- natural blink every 3–6 seconds
- very small body sway
- occasional ear tip movement
- occasional eye movement
- light smile

Loop duration:

- 4–8 seconds

Do not make idle movement too frequent, or Henry will feel nervous.

---

## 8.2 LISTENING

Visual behavior:

- body leans slightly forward
- eyes become attentive
- ears lift slightly
- one ear may rotate toward the sound
- one paw can move near the ear
- subtle audio-reactive ear pulse
- listening indicator around the character

Trigger:

```text
VAD speech_start
```

Exit:

```text
VAD speech_end
```

---

## 8.3 RECOGNIZING

Visual behavior:

- focused eyes
- minimal body movement
- small status pulse
- ears remain attentive
- avoid large thinking gestures because speech recognition should feel fast

Trigger:

```text
ASR processing
```

---

## 8.4 THINKING

Visual behavior:

- eyes glance upward or to one side
- head tilts slightly
- one paw touches chin
- one ear bends slightly
- slow body sway
- optional small question bubble

Long-thinking fallback:

After approximately 4 seconds:

- change to a second thinking loop
- blink
- switch gaze direction
- add tiny ear twitch

This prevents the animation from looking frozen.

---

## 8.5 SPEAKING

Visual behavior:

- lip sync
- soft head movement
- controlled hand gestures
- occasional blink
- slight body bounce on emphasized words
- ears follow head motion
- expression follows response emotion

Do not gesture continuously.
Use gesture events at phrase boundaries.

---

## 8.6 HAPPY / SUCCESS

Visual behavior:

- eyes curve into happy shape
- cheeks rise
- hands come together
- small jump or bounce
- both ears lift and settle
- short sparkle effect

Duration:

- 0.8–1.8 seconds

Then return to:

```text
IDLE
```

---

## 8.7 CONFUSED

Visual behavior:

- one eyebrow raised
- head tilted
- one ear lowered
- mouth slightly open
- gaze moves left and right
- optional question mark

Use when:

- ASR confidence is low
- user input is ambiguous
- LLM requests clarification

---

## 8.8 ERROR

Visual behavior:

- ears droop
- eyes soften
- small apologetic expression
- body lowers slightly
- optional warning icon

Avoid aggressive red flashing.
The error state should feel apologetic, not alarming.

---

## 8.9 INTERRUPTED

Visual behavior:

- mouth closes quickly
- eyes widen briefly
- ears react upward
- body shifts back
- then transition into listening mode

Trigger:

```text
barge_in
```

---

## 8.10 SLEEPING

Visual behavior:

- eyes closed
- slow breathing
- ears relaxed
- body slightly lowered
- optional small sleep bubble
- very low animation frequency

Wake triggers:

```text
wake_word
pointer_enter
microphone_activity
user_click
```

---

## 9. Action Library

Actions are short, reusable animation clips.

Recommended naming convention:

```text
action.<category>.<name>
```

### 9.1 Face actions

```text
action.face.blink
action.face.slow_blink
action.face.wink_left
action.face.wink_right
action.face.smile
action.face.big_smile
action.face.surprised
action.face.confused
action.face.shy
action.face.sleepy
```

### 9.2 Head actions

```text
action.head.nod
action.head.double_nod
action.head.shake
action.head.tilt_left
action.head.tilt_right
action.head.look_up
action.head.look_down
action.head.look_left
action.head.look_right
```

### 9.3 Ear actions

```text
action.ear.sway
action.ear.alert
action.ear.droop
action.ear.twitch_left
action.ear.twitch_right
action.ear.bounce
action.ear.follow_head
```

### 9.4 Paw actions

```text
action.paw.wave_left
action.paw.wave_right
action.paw.raise
action.paw.point_left
action.paw.point_right
action.paw.point_center
action.paw.hands_together
action.paw.touch_chin
action.paw.touch_glasses
```

### 9.5 Body actions

```text
action.body.bounce
action.body.cheer
action.body.bow
action.body.lean_forward
action.body.lean_back
action.body.shrug
action.body.jump
action.body.settle
```

### 9.6 System actions

```text
action.system.boot
action.system.connect
action.system.disconnect
action.system.success
action.system.warning
action.system.error
action.system.sleep
action.system.wake
```

---

## 10. Ear Physics Design

Henry's long ears are one of the most important personality features.

The ears should not simply rotate with the head. They should have delayed secondary movement.

### 10.1 Head shake sequence

Example:

```text
0 ms:
head begins moving left

60 ms:
ear bases begin following

120 ms:
ear middle sections bend

180 ms:
ear tips follow

240 ms:
head reverses direction

300–500 ms:
ears overshoot and settle
```

### 10.2 Recommended ear behavior

When the head turns:

- ear base follows quickly
- ear middle follows with delay
- ear tip follows with more delay
- opposite ear may react differently
- both ears settle with damping

Suggested physics values:

```text
stiffness: medium-low
damping: medium
gravity: low-medium
overshoot: subtle
asymmetry: 5–12%
```

The slight asymmetry keeps the motion organic.

---

## 11. Speech Animation

There are three implementation levels.

### Level 1 — Audio amplitude

Input:

```text
audio_level: 0.0–1.0
```

Mapping:

```text
0.00–0.10 -> closed
0.10–0.35 -> small open
0.35–0.70 -> medium open
0.70–1.00 -> wide open
```

Advantages:

- simple
- low latency
- works with any TTS

Limitations:

- not phoneme accurate

### Level 2 — Viseme timeline

The TTS service returns a timeline:

```json
[
  { "time_ms": 0, "viseme": "sil" },
  { "time_ms": 80, "viseme": "PP" },
  { "time_ms": 140, "viseme": "aa" },
  { "time_ms": 260, "viseme": "E" }
]
```

Advantages:

- better lip sync
- predictable animation

### Level 3 — Viseme + emotion + gesture markers

Example:

```json
{
  "audio_url": "/audio/reply_123.wav",
  "emotion": "happy",
  "visemes": [],
  "markers": [
    { "time_ms": 400, "action": "action.paw.raise" },
    { "time_ms": 1200, "action": "action.head.nod" },
    { "time_ms": 2100, "action": "action.body.bounce" }
  ]
}
```

This is the recommended production format.

---

## 12. Runtime Event Interface

Use WebSocket for real-time avatar events.

Suggested endpoint:

```text
ws://host/avatar/events
```

### 12.1 Generic event envelope

```json
{
  "version": "1.0",
  "event_id": "evt_123",
  "timestamp": 1760000000000,
  "source": "asr",
  "type": "avatar.state",
  "payload": {}
}
```

### 12.2 Change avatar state

```json
{
  "type": "avatar.state",
  "payload": {
    "state": "LISTENING",
    "transition_ms": 180,
    "priority": 50
  }
}
```

### 12.3 Trigger action

```json
{
  "type": "avatar.action",
  "payload": {
    "action": "action.head.nod",
    "intensity": 0.7,
    "duration_ms": 700,
    "priority": 40,
    "interruptible": true
  }
}
```

### 12.4 Set expression

```json
{
  "type": "avatar.expression",
  "payload": {
    "expression": "happy",
    "intensity": 0.8,
    "blend_ms": 200,
    "hold_ms": 1200
  }
}
```

### 12.5 Update gaze target

```json
{
  "type": "avatar.gaze",
  "payload": {
    "x": 0.35,
    "y": -0.15,
    "duration_ms": 250
  }
}
```

### 12.6 Audio level

```json
{
  "type": "avatar.audio_level",
  "payload": {
    "level": 0.62,
    "timestamp_ms": 1840
  }
}
```

### 12.7 Viseme update

```json
{
  "type": "avatar.viseme",
  "payload": {
    "viseme": "aa",
    "weight": 0.9,
    "duration_ms": 110
  }
}
```

### 12.8 Ear reaction

```json
{
  "type": "avatar.ear",
  "payload": {
    "action": "sway",
    "side": "both",
    "intensity": 0.65,
    "duration_ms": 900
  }
}
```

---

## 13. REST Control Interface

Suggested API base:

```text
/api/avatar/v1
```

### 13.1 Get avatar status

```http
GET /api/avatar/v1/status
```

Response:

```json
{
  "state": "IDLE",
  "expression": "neutral",
  "speaking": false,
  "connected": true,
  "model": "henry_v1"
}
```

### 13.2 Set avatar state

```http
POST /api/avatar/v1/state
```

Body:

```json
{
  "state": "THINKING"
}
```

### 13.3 Trigger action

```http
POST /api/avatar/v1/action
```

Body:

```json
{
  "action": "action.head.shake",
  "intensity": 0.8
}
```

### 13.4 Set expression

```http
POST /api/avatar/v1/expression
```

Body:

```json
{
  "expression": "happy",
  "intensity": 1.0,
  "hold_ms": 1200
}
```

### 13.5 Load model

```http
POST /api/avatar/v1/model
```

Body:

```json
{
  "model_id": "henry_v1"
}
```

---

## 14. Action Scheduling and Priority

Multiple events may arrive at the same time.

Recommended priority levels:

```text
100  critical system event
90   interruption / barge-in
80   error
70   state transition
60   speech synchronization
50   user-triggered action
40   gesture
20   idle motion
10   ambient motion
```

Rules:

1. Higher-priority actions may interrupt lower-priority actions.
2. Idle actions must always be interruptible.
3. Speech lip sync should continue even when a hand gesture plays.
4. Error and interrupted states should stop nonessential actions.
5. Ear physics should remain active during most animations.
6. Avoid playing more than one major body action simultaneously.

---

## 15. Animation Layers

The runtime should separate animation channels.

```text
Channel 1: Base state
Channel 2: Facial expression
Channel 3: Lip sync
Channel 4: Eye gaze and blink
Channel 5: Head movement
Channel 6: Ear physics
Channel 7: Hand gesture
Channel 8: Body motion
Channel 9: Accessory physics
Channel 10: UI effects
```

This allows Henry to:

- speak
- blink
- move ears
- perform a hand gesture

at the same time without replacing the entire animation.

---

## 16. ASR / LLM / TTS Integration

Recommended pipeline:

```text
Microphone
  -> VAD
  -> ASR
  -> Dialogue Manager
  -> LLM
  -> Response Planner
  -> TTS
  -> Avatar Controller
  -> WebUI Renderer
```

### 16.1 VAD events

```text
vad.speech_start
vad.speech_end
vad.silence
```

Mapping:

```text
speech_start -> LISTENING
speech_end -> RECOGNIZING
```

### 16.2 ASR events

```text
asr.partial
asr.final
asr.low_confidence
asr.error
```

Mapping:

```text
partial -> continue LISTENING
final -> THINKING
low_confidence -> CONFUSED
error -> ERROR
```

### 16.3 LLM events

```text
llm.started
llm.token
llm.completed
llm.error
```

Mapping:

```text
started -> THINKING
completed -> prepare SPEAKING
error -> ERROR
```

### 16.4 TTS events

```text
tts.started
tts.audio_level
tts.viseme
tts.marker
tts.completed
tts.interrupted
tts.error
```

Mapping:

```text
started -> SPEAKING
completed -> IDLE
interrupted -> INTERRUPTED
error -> ERROR
```

---

## 17. Response Planner

The LLM should not directly output raw animation commands without validation.

Instead, use a response planner.

Example response plan:

```json
{
  "text": "當然可以，我幫你整理好了。",
  "emotion": "happy",
  "energy": 0.65,
  "gesture_plan": [
    {
      "at": "sentence_start",
      "action": "action.paw.raise"
    },
    {
      "at": "sentence_end",
      "action": "action.head.nod"
    }
  ]
}
```

The avatar controller converts this plan into safe runtime actions.

---

## 18. Emotion Model

Recommended basic emotion set:

```text
neutral
happy
excited
curious
thinking
confused
surprised
shy
sorry
sleepy
concerned
```

Each emotion should map to:

- eye shape
- eyebrow position
- mouth form
- cheek deformation
- head pose
- ear pose
- body energy
- gesture frequency

Example:

```json
{
  "emotion": "curious",
  "parameters": {
    "brow_l_y": 0.25,
    "brow_r_y": 0.10,
    "head_roll": -0.12,
    "ear_l_base_angle": 0.18,
    "ear_r_base_angle": -0.08,
    "mouth_smile": 0.15
  }
}
```

---

## 19. Idle Behavior Controller

Idle behavior should be procedural rather than one repeated GIF.

Example scheduler:

```text
Every 3–6 seconds:
- blink

Every 8–15 seconds:
- eye glance
- ear twitch
- small head tilt

Every 20–40 seconds:
- slow blink
- adjust glasses
- small paw movement
- soft bounce

After 60–120 seconds of inactivity:
- sleepy behavior

After configured timeout:
- SLEEPING
```

Use randomness within controlled limits so Henry feels alive but not distracting.

---

## 20. User Interaction Actions

### Pointer interaction

```text
pointer_enter -> look toward pointer
pointer_move -> subtle eye tracking
pointer_click_head -> surprised blink
pointer_click_ear -> ear twitch
pointer_click_badge -> point to badge
pointer_leave -> return gaze to center
```

### Voice interaction

```text
wake_word -> wake animation
barge_in -> stop speech and listen
user_laugh -> happy reaction
loud_noise -> surprised reaction
```

### UI interaction

```text
task_complete -> success animation
new_message -> attentive reaction
notification -> ear alert
connection_lost -> disconnected expression
```

---

## 21. WebUI Component Interface

Suggested React component:

```tsx
<HenryAvatar
  state="IDLE"
  emotion="neutral"
  audioLevel={0}
  gaze={{ x: 0, y: 0 }}
  size="bust"
  interactive={true}
  onActionComplete={handleActionComplete}
/>
```

Suggested controller interface:

```ts
interface AvatarController {
  setState(state: AvatarState): void;
  setExpression(expression: ExpressionOptions): void;
  triggerAction(action: AvatarAction): Promise<void>;
  setAudioLevel(level: number): void;
  setViseme(viseme: VisemeEvent): void;
  setGaze(target: GazeTarget): void;
  stop(priorityBelow?: number): void;
  reset(): void;
}
```

---

## 22. TypeScript Data Types

```ts
type AvatarState =
  | "OFFLINE"
  | "BOOTING"
  | "IDLE"
  | "LISTENING"
  | "RECOGNIZING"
  | "THINKING"
  | "SPEAKING"
  | "INTERRUPTED"
  | "SUCCESS"
  | "CONFUSED"
  | "ERROR"
  | "SLEEPING";

type AvatarEmotion =
  | "neutral"
  | "happy"
  | "excited"
  | "curious"
  | "thinking"
  | "confused"
  | "surprised"
  | "shy"
  | "sorry"
  | "sleepy"
  | "concerned";

interface AvatarAction {
  action: string;
  intensity?: number;
  durationMs?: number;
  priority?: number;
  interruptible?: boolean;
}

interface ExpressionOptions {
  expression: AvatarEmotion;
  intensity?: number;
  blendMs?: number;
  holdMs?: number;
}

interface GazeTarget {
  x: number;
  y: number;
  durationMs?: number;
}

interface VisemeEvent {
  viseme: string;
  weight: number;
  durationMs: number;
}
```

---

## 23. Configuration File

Suggested configuration file:

```text
henry.avatar.json
```

Example:

```json
{
  "id": "henry_v1",
  "display_name": "Henry",
  "default_state": "IDLE",
  "default_expression": "neutral",
  "renderer": "live2d",
  "model_path": "/avatars/henry/model3.json",
  "physics_enabled": true,
  "gaze_tracking": true,
  "lip_sync": {
    "mode": "viseme",
    "fallback": "audio_level"
  },
  "idle": {
    "blink_min_ms": 3000,
    "blink_max_ms": 6000,
    "gesture_min_ms": 12000,
    "gesture_max_ms": 30000
  },
  "ears": {
    "physics_enabled": true,
    "stiffness": 0.35,
    "damping": 0.55,
    "gravity": 0.22
  }
}
```

---

## 24. MVP Scope

The first production prototype should support:

### Required

- idle breathing
- blink
- eye tracking
- listening pose
- thinking pose
- speaking mouth movement
- happy expression
- confused expression
- head nod
- head shake
- ear sway
- paw wave
- WebSocket state events
- audio-level lip sync
- interruption handling

### Optional for phase 2

- viseme lip sync
- emotion blending
- pointer interaction
- accessory physics
- multiple outfit variants
- full-body movement
- emotion inferred from LLM output
- face-camera gaze
- user emotion reaction

---

## 25. Testing Checklist

### Visual

- Is Henry recognizable at 128 px?
- Are state changes clear without text labels?
- Do the glasses remain aligned during head turns?
- Do the ears feel soft rather than rigid?
- Is the badge readable at bust size?
- Does the silhouette remain clean?

### Animation

- Does head shake produce delayed ear motion?
- Are blink intervals natural?
- Does lip sync stop immediately when interrupted?
- Do hand gestures interfere with speech?
- Are state transitions smooth?
- Does idle movement remain subtle?

### System

- Can ASR events change states reliably?
- Can TTS send audio level or viseme events?
- Are high-priority actions able to interrupt idle actions?
- Does the avatar return to IDLE after actions?
- Can the renderer reconnect after WebSocket failure?
- Is there a fallback static image if the model fails?

---

## 26. Suggested Project Structure

```text
avatar/
├── assets/
│   └── henry/
│       ├── source/
│       ├── textures/
│       ├── expressions/
│       ├── motions/
│       ├── icons/
│       └── model/
├── config/
│   └── henry.avatar.json
├── controller/
│   ├── AvatarController.ts
│   ├── AvatarStateMachine.ts
│   ├── ActionScheduler.ts
│   ├── EmotionMapper.ts
│   └── LipSyncController.ts
├── renderer/
│   ├── Live2DRenderer.ts
│   ├── SpriteRenderer.ts
│   └── FallbackRenderer.ts
├── transport/
│   ├── AvatarWebSocket.ts
│   └── AvatarApi.ts
├── components/
│   ├── HenryAvatar.tsx
│   └── AvatarStatus.tsx
└── types/
    └── avatar.ts
```

---

## 27. Final Design Direction

Henry should be designed as:

> A soft, expressive, chibi rabbit assistant whose long ears, large eyes, small paws, and rounded body provide clear emotional communication.

The most important animation features are:

1. ear secondary motion
2. eye and eyebrow expression
3. clear listening/thinking/speaking states
4. natural blink and breathing
5. controlled paw gestures
6. interruption-aware speech animation
7. smooth state transitions

The recommended implementation sequence is:

```text
Character finalization
-> layered artwork
-> MVP sprite animation
-> ASR / TTS state integration
-> Live2D or Rive rig
-> viseme lip sync
-> emotion and gesture planner
-> production optimization
```
