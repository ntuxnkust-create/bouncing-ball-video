# Replace sound effects

The default sounds are synthesized in Python. No downloads are required. Drop any of these files in this directory to replace that sound family:

| Filename | Trigger | Default |
|---|---|---|
| `wall.wav` | Actual ball/container contact | Soft glass / marble tap |
| `ball.wav` | Actual ball/ball contact | Short pop / boing |
| `merge.wav` | Successful equal-level merge | Layered pop + ding, richer at higher levels |
| `final.wav` | Actual final-level merge | Short ascending success sparkle |

Use **16-bit PCM WAV**, mono or stereo, between 1 sample and **3 seconds**. Audio is downmixed to mono for spatial placement and resampled to the output rate. A short fade removes edge clicks and peak normalization protects the gain staging. Stereo position then follows the real contact position. Missing files use the procedural bank; malformed files produce an error rather than silently substituting a sound.

Configure gains, cooldowns, maximum voices, ducking and limiter headroom in `config.py` → `SoundConfig`. The `SoundBank` is separate from scheduling; replacing timbre never changes physics or event timing. Only effects should be supplied here; the engine generates no background music or speech. Legacy `hit` events can still be read as ball contacts, but only new `wall`/`ball` logs preserve the distinction.

Custom merge WAVs replace the complete sound family; procedural level-dependent layers apply to the built-in bank. Use a custom `SoundBank.get(kind, level)` implementation if separate WAVs per upgrade level are needed.
