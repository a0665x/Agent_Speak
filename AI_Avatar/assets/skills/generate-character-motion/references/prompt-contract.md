# Provider prompt contract

For GPT Image, provide these images in order:

1. canonical full-body character reference;
2. deterministic pose map for the current stage;
3. nearest approved flesh frame.

The text must lock identity regions, canvas, scale, center, baseline, feet, and
one flat chroma background. Describe the pose map as a strong visual
instruction, not a latent constraint or ControlNet.

Read the API key only from the environment. Safe metadata is limited to
provider, model, request ID, elapsed time, input hashes, and bounded error
codes. Do not store raw response bodies.

For ComfyUI FLF2V, provide the exact approved S0 as both first and last frame,
the reviewed workflow hash, motion prompt, dimensions, FPS, duration, and seed.
The original media is a review preview; normalized PNG frames are the precise
runtime candidate.

