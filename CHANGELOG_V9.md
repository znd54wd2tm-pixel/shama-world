# SHAMA WORLD V9

## Mobile, enterprise economy, and deployment package
- Moved the primary navigation to the top and made the layout mobile-first with safe-area padding and larger touch targets.
- Replaced the city artwork on World with four direct section buttons.
- Added persistent server-side Farm, Business, customer-bank, stock, and crypto systems using SQLite; added a Torpedo Stadium foundation screen.
- Added saved crypto-price fallback, globally limited company shares, hourly price limits, bank-liability protection, and profit-only withdrawals.
- Added enterprise loading and error feedback, duplicate-action guards, and versioned static URLs.
- Hardened profile rendering so optional legacy profile fields cannot stop the app from loading.
- The Mega Hangar price is set to 75,000 SH because its price was not specified in the feature brief.

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
