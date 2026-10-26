"""Den seed finder: register the Sword/Shield tool. docs/plugins.md, Making a plugin."""
from pokeldn.plugins import Field, Tool

FLAWLESS = (("auto", "Work it out (try 1 to 5)"), ("1", "1 (1-star den)"), ("2", "2 (2-star den)"),
            ("3", "3 (3-star den)"), ("4", "4 (4-star, most 5-star dens)"), ("5", "5 (some 5-star dens)"))


def register(api):
    api.add_tool("swsh", Tool(
        "swsh-den-seed", "Den seed from a traded Pokemon", "den_seed.py",
        "Finds a Max Raid den's seed from a Pokemon caught in it, then lists the next shiny days.",
        ("Catch the den's Pokemon, then trade it to pokeldn with Trade (your console joins).",
         "Leave the file empty to use the newest Sword/Shield file in Received, or choose it.",
         "Press Start: the den seed and its next shiny days appear below."),
        fields=(
            Field("--file", "Raid Pokemon file", "file", exts=("pk8", "ek8"),
                  help="The Pokemon you caught in the den, as pokeldn received it. Empty: the newest "
                       ".pk8 in Received."),
            Field("--flawless", "Guaranteed perfect IVs", "choice", default="auto", choices=FLAWLESS,
                  help="How many IVs the den guarantees at 31: the raid's star count up to 4, and 4 or 5 "
                       "for a 5-star den. Work it out tries every count and keeps the ones that fit."),
            Field("--shiny-count", "Shiny days to list", "number", default="5",
                  help="How many upcoming shiny frames to show."),
            Field("--frames", "Days to search", "number", default="10000", hidden=True,
                  help="How far ahead to look for shiny frames."),
            Field("--ec", "Encryption constant (hex)", hidden=True,
                  help="Typed instead of a file: the Pokemon's encryption constant, 8 hex digits."),
            Field("--pid", "PID (hex)", hidden=True, help="Typed instead of a file: the PID, 8 hex digits."),
            Field("--ivs", "IVs HP/Atk/Def/SpA/SpD/Spe", hidden=True,
                  help="Typed instead of a file, the six IVs in that order: 31/31/31/0/31/12."),
            Field("--tid", "Catcher's TID (16-bit)", "number", hidden=True,
                  help="Typed instead of a file: the original trainer's 16-bit TID, as PKHeX shows it."),
            Field("--sid", "Catcher's SID (16-bit)", "number", hidden=True,
                  help="Typed instead of a file: the original trainer's 16-bit SID."),
            Field("--shiny", "The Pokemon is shiny", "switch", hidden=True,
                  help="Typed instead of a file: whether the Pokemon came out shiny."),
        ),
        fixed=("--received", "{received}"),
        radio=False,
    ))
