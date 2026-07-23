# React Integration

## Component contract

```tsx
<HenryAvatar
  state="IDLE"
  emotion="neutral"
  onClipComplete={handleClipComplete}
/>
```

## Event flow

```text
vad.speech_start  -> LISTENING
vad.speech_end    -> RECOGNIZING
asr.final         -> THINKING
tts.started       -> SPEAKING
tts.completed     -> IDLE
tts.interrupted   -> LISTENING
system.success    -> happy_once -> previous persistent state
```

## CSS requirements

The avatar viewport must have fixed width and height to prevent layout shift.
Use `object-fit: contain` and absolute centering.
