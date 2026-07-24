# Review gates

Automatic gates run before human review:

- exact canvas and full-body framing;
- alpha corners, foreground coverage, chroma spill, and edge retention;
- stable center, scale, feet, and baseline;
- no detached, duplicated, or missing anatomy;
- bounded adjacent silhouette and identity-region change;
- exact S0 bytes and hash at both boundaries;
- bounded `S0 → second` and `penultimate → S0` motion.

A clean result is `needs_review`. The reviewer must confirm identity, anatomy,
clothing, intended pose, style, and temporal continuity. Approval binds all
current hashes and unlocks exactly one stage. Rejection keeps the same stage
unlocked and cannot seed a later candidate.

Candidate generation, review, and publication are separate authorities. The
candidate runner cannot write `AI_Avatar/public/`.

