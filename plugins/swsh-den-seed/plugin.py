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

HOST = Tool(
    "swsh-den-seed-host", "Host the shiny frame", "host_frame.py",
    "Hosts the den's shiny day as a Max Raid your console joins, so you catch it now instead of "
    "skipping days. Built from the Pokemon you caught there, rolled as that day's seed.",
    ("Run Den seed first and note a shiny day from its list.",
     "Enter that day, choose the Pokemon our player brings, and start the host.",
     "Y-Comm in local wireless mode: join POKELDN's raid from the list.",
     "Press Ready: the console runs the battle and our Pokemon fights at your side.",
     "Win and catch: the Pokemon is that day's roll of the den, shiny for your trainer.",
     "A black screen with the raid music is a start the console lost; the host recovers it once. If it "
     "stays black, press Stop, close the game fully, reopen it and start again."),
    fields=(
        Field("--day", "Shiny day", "number", required=True,
              help="The +N day from the finder's list. Day 0 is the Pokemon you caught."),
        Field("--offer-file", "Our Pokemon", "pokemon", required=True,
              help="The Pokemon our player brings to the raid. PKHeX checks it is legal."),
        Field("--seed", "Den seed (hex)",
              help="16 hex digits. Empty: the seed Den seed found last."),
        Field("--file", "Pokemon caught in the den", "file", exts=("pk8", "ek8"),
              help="The frame's Pokemon is rebuilt from it: same species, trainer and met data. "
                   "Empty: the file Den seed read last."),
        Field("--flawless", "Guaranteed perfect IVs", "choice", default="auto",
              choices=(("auto", "As Den seed found"),) + FLAWLESS,
              help="The den's guaranteed 31s, as Den seed reported for this den."),
        Field("--ability-rule", "Den ability rule", "choice", default="auto", hidden=True,
              choices=(("auto", "Work it out"), ("12", "Ability 1 or 2"), ("12H", "Ability 1, 2 or hidden")),
              help="Which abilities the den can give. Work it out builds both and keeps the one PKHeX accepts."),
        Field("--prepare-only", "Build the file only, do not host", "switch", hidden=True,
              help="Writes the frame's .pk8 into the plugin's data folder and stops."),
        Field("--channel", "Channel", "choice", default="6", choices=CHANNELS, hidden=True,
              help="The wireless channel of the network pokeldn hosts."),
        Field("--seconds", "Time limit (seconds)", "number", default="900", hidden=True,
              help="How long the host stays up after Start, then it closes on its own."),
    ),
    fixed=("--raid-console-serves", "--player-name", "{ot}", "--trainer-name", "{ot}",
           "--trainer-tid", "{tid}", "--trainer-sid", "{sid}"),
)


def register(api):
    api.add_tool("swsh", FINDER)
    api.add_tool("swsh", HOST)
