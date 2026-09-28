# SHAMA WORLD V9

## Core fixes
- Rebuilt the case-result modal so it stays inside the Telegram viewport.
- Fixed result image sizing with contain/object-position center.
- Added deterministic modal cleanup on close, navigation and backdrop taps.
- Rebuilt upgrade roulette as two explicit animation phases.
- Phase 1 is exactly five full pointer rotations.
- Phase 2 slows down and stops at a randomized point in the server-authoritative result sector.
- Removed the artificial GitHub file-count target; the package contains the complete project structure and all required assets.
- Fixed local `routes.py --dev` startup and corrected stale `api.routes` references.
- Bumped asset cache version to V9.
