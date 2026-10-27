#!/usr/bin/env python3
"""Find a Sword/Shield Max Raid den's seed from a Pokemon caught in it, then list its next shiny days.

With nothing else given, pokeldn hosts a Link Trade and reads the Pokemon the console puts on the trade
screen: the record arrives with the offer, before anyone confirms (docs/swsh_trade.md, The sequence,
step 7), so the host leaves as soon as it has it and nothing is traded. A file pokeldn received, or
typed values, skip the hosting. The maths is swshdenseed_core; nothing leaves this computer.
"""
import _thread
import argparse
import json
import os
import runpy
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swshdenseed_core as core

PLUGIN_ID = "swsh-den-seed"


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=None, help="the caught Pokemon's .pk8 / .ek8; empty: read it from the trade screen")
    ap.add_argument("--ec", default=None, help="encryption constant, hex, instead of a file")
    ap.add_argument("--pid", default=None, help="PID, hex, instead of a file")
    ap.add_argument("--ivs", default=None, help="HP/Atk/Def/SpA/SpD/Spe, instead of a file")
    ap.add_argument("--tid", type=int, default=None, help="the catcher's 16-bit TID, with --ec")
    ap.add_argument("--sid", type=int, default=None, help="the catcher's 16-bit SID, with --ec")
    ap.add_argument("--shiny", action="store_true", help="the Pokemon is shiny, with --ec")
    ap.add_argument("--flawless", default="auto", help="guaranteed perfect IVs, 1 to 5, or auto")
    ap.add_argument("--frames", type=int, default=10000, help="days to search for shiny frames")
    ap.add_argument("--shiny-count", type=int, default=5, help="shiny frames to list")
    ap.add_argument("--received", default=None, help="the Received folder the offered record is saved into")
    # The trade host, bin/swsh_host.py, when the Pokemon is read from the trade screen.
    ap.add_argument("--offer-file", action="append", default=[], help="what POKELDN shows on the trade screen")
    ap.add_argument("--code", default=None, help="Link Code, eight digits; empty for a plain trade")
    ap.add_argument("--keys", default=None, help="prod.keys; the app passes Settings' file")
    ap.add_argument("--channel", default=None)
    ap.add_argument("--seconds", default=None)
    ap.add_argument("--player-name", default="POKELDN")
    ap.add_argument("--trainer-name", default="POKELDN")
    ap.add_argument("--trainer-tid", default=None)
    ap.add_argument("--trainer-sid", default=None)
    return ap


def parse_hex(text, what):
    try:
        value = int(text.strip().removeprefix("0x").removeprefix("0X"), 16)
    except ValueError:
        raise SystemExit(f"{what} is not hex: {text!r}")
    if not 0 <= value <= 0xFFFFFFFF:
        raise SystemExit(f"{what} is 8 hex digits at most: {text!r}")
    return value


def parse_ivs(text):
    parts = [p for p in text.replace(",", "/").replace(" ", "/").split("/") if p]
    try:
        ivs = tuple(int(p) for p in parts)
    except ValueError:
        raise SystemExit(f"IVs are six numbers 0-31 as HP/Atk/Def/SpA/SpD/Spe: {text!r}")
    if len(ivs) != 6 or not all(0 <= v <= 31 for v in ivs):
        raise SystemExit(f"IVs are six numbers 0-31 as HP/Atk/Def/SpA/SpD/Spe: {text!r}")
    return ivs


# --- reading the Pokemon from the trade screen ----------------------------------------------------
def pokeldn_root():
    import pokeldn
    return os.path.dirname(os.path.dirname(os.path.abspath(pokeldn.__file__)))


def peek(host_trade, out, taken, log=print, stop=_thread.interrupt_main):
    """Wraps HostTrade so no trade confirms and the first offer is saved to `out`, then `stop` runs.
    -> a function restoring the class."""
    original_init, original_on_data = host_trade.HostTrade.__init__, host_trade.HostTrade.on_data

    def __init__(self, *a, **kw):
        kw["auto_accept"] = False                  # never send box command 4: the console keeps its Pokemon
        original_init(self, *a, **kw)

    def on_data(self, protocol, port, payload, now=None):
        original_on_data(self, protocol, port, payload, now)
        pk8 = self.box.get("peer_pk8")
        if pk8 is not None and not taken:
            taken["pk8"] = bytes(pk8)
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "wb") as f:
                f.write(taken["pk8"])
            log(f"[den] the console offers its Pokemon: saved {os.path.basename(out)}. Leaving the trade; "
                "nothing is traded.", flush=True)
            stop()

    host_trade.HostTrade.__init__, host_trade.HostTrade.on_data = __init__, on_data

    def restore():
        host_trade.HostTrade.__init__, host_trade.HostTrade.on_data = original_init, original_on_data
    return restore


def from_trade_screen(args):
    """Hosts a Link Trade until the console offers a Pokemon; -> the saved record's path."""
    try:
        from pokeldn.swsh import host_trade
    except Exception as error:
        raise SystemExit(f"pokeldn's trade host cannot be loaded here: {error}")
    folder = args.received or os.getcwd()
    out = os.path.join(folder, f"swsh-{time.strftime('%Y%m%d-%H%M%S')}-den.pk8")
    taken = {}
    restore = peek(host_trade, out, taken)
    argv = [os.path.join(pokeldn_root(), "bin", "swsh_host.py")]
    for offer in args.offer_file:
        argv += ["--offer-file", offer]
    for flag, value in (("--code", args.code), ("--keys", args.keys), ("--channel", args.channel),
                        ("--seconds", args.seconds), ("--player-name", args.player_name),
                        ("--trainer-name", args.trainer_name), ("--trainer-tid", args.trainer_tid),
                        ("--trainer-sid", args.trainer_sid)):
        if value not in (None, ""):
            argv += [flag, str(value)]
    print("Hosting a Link Trade. On the console: Y-Comm, Link Trade, local communication, then offer the "
          "Pokemon you caught in the den when POKELDN appears. Do not confirm: pokeldn leaves as soon as "
          "it has read the offer.", flush=True)
    saved_argv, saved_path = sys.argv, list(sys.path)
    sys.argv = argv
    sys.path.insert(0, os.path.dirname(argv[0]))
    try:
        runpy.run_path(argv[0], run_name="__main__")
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        restore()
        sys.argv, sys.path[:] = saved_argv, saved_path
    if not taken:
        raise SystemExit("The host ended before the console offered a Pokemon.")
    print(flush=True)
    return out


# --- the seed ------------------------------------------------------------------------------------
def pokemon_from(args):
    """-> (facts, source line) from the file, the typed values, or the trade screen."""
    if args.ec or args.pid or args.ivs:
        if not (args.ec and args.pid and args.ivs):
            raise SystemExit("Typed values need all three: the encryption constant, the PID and the IVs.")
        facts = {"ec": parse_hex(args.ec, "The encryption constant"), "pid": parse_hex(args.pid, "The PID"),
                 "ivs": parse_ivs(args.ivs), "species": 0, "tsv": None, "shiny": 1 if args.shiny else 0}
        if args.tid is not None and args.sid is not None:
            facts["tsv"] = (args.tid ^ args.sid) & 0xFFFF
            facts["shiny"] = core.shiny_kind(facts["pid"], facts["tsv"])
        return facts, "typed values"
    path = args.file or from_trade_screen(args)
    with open(path, "rb") as f:
        facts = core.read_record(f.read())
    facts["path"] = os.path.abspath(path)
    return facts, os.path.basename(path)


def species_name(number):
    """The Sword/Shield dex name from pokeldn's own table; the number when the app is not around."""
    if not number:
        return "Pokemon"
    try:
        import pokeldn
        table = os.path.join(os.path.dirname(pokeldn.__file__), "swsh", "data", "species.json")
        with open(table, encoding="utf-8") as f:
            return json.load(f)["species_names"].get(str(number), f"#{number:03d}")
    except Exception:
        return f"#{number:03d}"


def card(**kw):
    try:
        from pokeldn import panel
        panel.show(**kw)
    except Exception:
        pass


def kind_text(kind):
    return "square" if kind == 2 else "star"


def main(args):
    facts, source = pokemon_from(args)
    name = species_name(facts["species"])
    kinds = {0: "no", 1: "yes, star", 2: "yes, square"}
    print(f"{name} from {source}: EC {facts['ec']:08X}, PID {facts['pid']:08X}, "
          f"IVs {core.ivs_text(facts['ivs'])}, shiny: {kinds[facts['shiny']]}", flush=True)
    counts = (1, 2, 3, 4, 5) if args.flawless == "auto" else (int(args.flawless),)
    if any(c not in (1, 2, 3, 4, 5) for c in counts):
        raise SystemExit("Guaranteed perfect IVs is 1 to 5, or auto.")
    if facts["shiny"]:
        print("A shiny's PID was rewritten by the game, so this takes longer: up to a minute.", flush=True)
    print("Working out the seed...", flush=True)
    started = time.monotonic()
    try:
        found = core.find(facts["ec"], facts["pid"], facts["ivs"], bool(facts["shiny"]), facts["tsv"], counts)
    except RuntimeError as e:
        raise SystemExit(str(e))
    took = time.monotonic() - started
    if not found:
        card(id="den-seed", title=f"No den seed fits {name}", tone="error", lines=[
            f"EC {facts['ec']:08X}, PID {facts['pid']:08X}, IVs {core.ivs_text(facts['ivs'])}",
            "A Pokemon straight from a Max Raid den fits. A hatched, promoted or Dynamax Adventure "
            "Pokemon does not, nor do hyper-trained values typed by hand."])
        raise SystemExit(f"No den seed gives this Pokemon ({took:.1f} s). Is it straight from a Max Raid den?")
    print(f"Found {len(found)} fit{'s' if len(found) != 1 else ''} in {took:.1f} s.", flush=True)
    lines = []
    for seed, flawless, mon in found:
        print(f"\nDen seed {seed:016X} with {flawless} guaranteed perfect IV{'s' if flawless != 1 else ''}",
              flush=True)
        frames = core.shiny_frames(seed, flawless, args.frames, args.shiny_count, facts["tsv"])
        if not frames:
            print(f"  No shiny frame within {args.frames} days.", flush=True)
        for days, kind, hit in frames:
            print(f"  day +{days}: {kind_text(kind)} shiny, EC {hit['ec']:08X}, "
                  f"IVs {core.ivs_text(hit['ivs'])}", flush=True)
        lines.append(f"Seed ({flawless} IVs)\t{seed:016X}")
        if frames:
            days, kind, _ = frames[0]
            later = ", ".join("+" + str(d) for d, _, _ in frames[1:])
            lines.append(f"Next shiny\tday +{days}, {kind_text(kind)}" + (f"; then {later}" if later else ""))
        else:
            lines.append(f"Next shiny\tnone within {args.frames} days")
    seed, flawless, _ = found[0]
    card(id="den-seed", title=f"Den seed for {name}: {seed:016X}", tone="ok", lines=lines[:12],
         chips=[("Perfect IVs", str(flawless)), ("From", source[:40])])
    print("\nA day skip on the console moves the den one frame; day +N is N skips from the Pokemon you "
          "caught. Do not beat or clear the den before you get there.", flush=True)
    remember(seed, flawless, facts)
    return seed, flawless, facts


def remember(seed, flawless, facts):
    """Keeps the result for Host the shiny frame: the seed, the IV count and the file it came from."""
    try:
        from pokeldn.plugins import data_folder
        folder = str(data_folder(PLUGIN_ID))
    except Exception:
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "last.json"), "w", encoding="utf-8") as f:
            json.dump({"seed": f"{seed:016X}", "flawless": flawless, "file": facts.get("path", ""),
                       "species": facts["species"], "tid": facts.get("tid"), "sid": facts.get("sid"),
                       "ivs": list(facts["ivs"]), "shiny": facts["shiny"], "when": time.time()}, f, indent=1)
    except OSError as error:
        print(f"Could not keep the result for Host the shiny frame: {error}", flush=True)


if __name__ == "__main__":
    try:
        main(build_parser().parse_args())
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
        sys.exit(1)
