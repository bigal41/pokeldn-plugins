"""Den Seed Finder: register the Sword/Shield tools. docs/plugins.md, Making a plugin."""
from pokeldn.plugins import Field, Tool

FLAWLESS = (("1", "1 (1-star den)"), ("2", "2 (2-star den)"), ("3", "3 (3-star den)"),
            ("4", "4 (4-star, most 5-star dens)"), ("5", "5 (some 5-star dens)"))
CHANNELS = (("1", "1"), ("6", "6"), ("11", "11"))

FINDER = Tool(
    "swsh-den-seed", "Den seed", "den_seed.py",
    "Finds a Max Raid den's seed from the Pokemon you caught in it, read off the trade screen with no "
    "trade made, then lists the den's next shiny days.",
    ("Start the host and wait for the network to come up.",
     "Y-Comm, Link Trade, local communication; press A on both messages, then wait in the overworld.",
     "When POKELDN appears, offer the Pokemon you caught in the den. Do not confirm.",
     "pokeldn reads the offer and leaves: the console reports a communication error and keeps the "
     "Pokemon. The den seed and its next shiny days appear below."),
    fields=(
        Field("--flawless", "Guaranteed perfect IVs", "choice", default="auto",
              choices=(("auto", "Work it out (try 1 to 5)"),) + FLAWLESS,
              help="How many IVs the den guarantees at 31: the raid's star count up to 4, and 4 or 5 "
                   "for a 5-star den. Work it out tries every count and keeps the ones that fit."),
        Field("--shiny-count", "Shiny days to list", "number", default="5",
              help="How many upcoming shiny frames to show."),
        Field("--offer-file", "Pokemon to show", "pokemon", random=True,
              help="What POKELDN puts on the trade screen. Empty: a random legal Pokemon. It is never traded."),
        Field("--code", "Link Code", "code", help="Eight digits. Empty for a plain trade."),
        Field("--file", "Pokemon file instead", "file", exts=("pk8", "ek8"),
              help="A Pokemon file pokeldn already received: read it instead of hosting a trade."),
        Field("--frames", "Days to search", "number", default="10000", hidden=True,
              help="How far ahead to look for shiny frames."),
        Field("--channel", "Channel", "choice", default="6", choices=CHANNELS, hidden=True,
              help="The wireless channel of the network pokeldn hosts."),
        Field("--seconds", "Time limit (seconds)", "number", default="600", hidden=True,
              help="How long the host waits for the offer, then it closes on its own."),
        Field("--ec", "Encryption constant (hex)", hidden=True,
              help="Typed instead of hosting: the Pokemon's encryption constant, 8 hex digits."),
        Field("--pid", "PID (hex)", hidden=True, help="Typed instead of hosting: the PID, 8 hex digits."),
        Field("--ivs", "IVs HP/Atk/Def/SpA/SpD/Spe", hidden=True,
              help="Typed instead of hosting, the six IVs in that order: 31/31/31/0/31/12."),
        Field("--tid", "Catcher's TID (16-bit)", "number", hidden=True,
              help="Typed instead of hosting: the original trainer's 16-bit TID, as PKHeX shows it."),
        Field("--sid", "Catcher's SID (16-bit)", "number", hidden=True,
              help="Typed instead of hosting: the original trainer's 16-bit SID."),
        Field("--shiny", "The Pokemon is shiny", "switch", hidden=True,
              help="Typed instead of hosting: whether the Pokemon came out shiny."),
    ),
    fixed=("--player-name", "{ot}", "--trainer-name", "{ot}", "--trainer-tid", "{tid}", "--trainer-sid", "{sid}",
           "--received", "{received}"),
)


def register(api):
    api.add_tool("swsh", FINDER)
