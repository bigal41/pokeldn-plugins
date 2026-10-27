# pokeldn plugins

Plugins for [pokeldn](https://decryptu.github.io/pokeldn/), the local Pokémon link tool. Everything here
runs on your own computer: no bots, no Discord, nothing phones home.

## Install

In pokeldn open **Plugins**, **Sources**, and add

    bigal41/pokeldn-plugins

The plugins below then appear under **Browse** with an Install button. Or download a `.pokeplugin`
from the [releases](https://github.com/bigal41/pokeldn-plugins/releases) and drop it on
**Installed**. Every package is signed; the app shows the author's key fingerprint on install, which should read
`ZZ6W-YYM6-4DAX-GZLZ`.

## Plugins

| plugin | game | what it does |
|---|---|---|
| [Den Seed Finder](plugins/swsh-den-seed) | Sword & Shield | Finds a Max Raid den's seed from a Pokémon caught in it and traded to pokeldn, then lists the den's next shiny days. |

### Den Seed Finder

1. Catch the den's Pokémon. Do not throw a Wishing Piece at that den afterwards.
2. **Sword & Shield**, **Den seed**, Start. On the console: Y-Comm, Link Trade, local communication,
   and offer the Pokémon when POKELDN appears. Do not confirm.
3. pokeldn reads the offer and leaves the trade. The console shows a communication error and keeps
   the Pokémon, ball and all. The card shows the den seed and the next shiny days. Day +N means N
   date changes from the Pokémon you caught.

Choose a Pokémon file pokeldn already received, or type the values on the Advanced tab, and no trade
is hosted.

The maths is pure Python (`swshdenseed_core.py`): the encryption constant fixes half the seed, a
GF(2) guess-and-determine over the PID recovers the rest, and the IVs pick the den's guaranteed-IV
count. A shiny takes a few seconds, anything else is instant. Event dens with forced shiny or IV
rules, Dynamax Adventure Pokémon and hatched Pokémon are not den rolls and are reported as no fit.

#### Host the shiny frame

Instead of skipping N days, host that day's raid yourself. **Sword & Shield**, **Host the shiny
frame**: enter the day from Den seed's list, choose the Pokémon our player brings, Start, then join
POKELDN's raid from Y-Comm in local wireless mode and catch it.

The frame's Pokémon is rebuilt from the one you caught in that den, so it keeps the species, trainer
and met data, and takes everything the den rolls on that day from the seed: encryption constant,
PID, IVs, ability, gender, nature, height, weight, level and Dynamax level. PKHeX checks the file
before pokeldn's own Max Raid host serves it. The console shows the boss shiny and, at the catch,
writes a PID for your trainer that keeps it shiny, as a real den does: verified on a retail Shield,
square shiny in the box. Gigantamax dens are not handled yet.

Two things seen on a retail console: a black screen with the raid music is a start the console
lost, which the host recovers once by republishing its server table, and a game that keeps stalling
is fixed by closing it fully and reopening. Do not change the console's date to test anything: every
date change moves your real den by one frame.

## Releasing (maintainer notes)

    pip install pycryptodome
    python scripts/release.py swsh-den-seed

This packs `plugins/<id>` into `dist/<id>-<version>.pokeplugin`, signs it with the key at
`~/.pokeldn-signing.pem` (created on first run: back it up, never commit it), and updates
`pokeldn-source.json`. Then commit the listing, tag the release `<id>-<version>` and attach the
package. `python scripts/release.py <id> --check` verifies a built package against the sources.
Bump `version` in `plugin.toml` for every release; pokeldn compares versions to offer updates.
