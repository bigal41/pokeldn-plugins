#!/usr/bin/env python3
"""Host a den's shiny frame as a Max Raid, so the console catches it tonight instead of after N day skips.

The frame's Pokemon is rebuilt from the Pokemon you caught in that den: the same species, level, moves,
trainer and met data, with the encryption constant, PID, IVs, ability, gender, nature, height and weight
the den would roll on that day. PKHeX checks it, then pokeldn's own Max Raid host (bin/swsh_host.py)
serves it to the console. The maths is swshdenseed_core; nothing leaves this computer.
"""
import argparse
import json
import os
import runpy
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swshdenseed_core as core

PLUGIN_ID = "swsh-den-seed"
LAST = "last.json"


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", type=int, required=True, help="the shiny day from the finder: +N")
    ap.add_argument("--seed", default=None, help="den seed, hex; empty: the seed the finder found last")
    ap.add_argument("--file", default=None, help="the Pokemon you caught in the den; empty: the finder's last file")
    ap.add_argument("--flawless", default="auto", help="guaranteed perfect IVs, 1 to 5; auto: as the finder found")
    ap.add_argument("--ability-rule", default="auto", choices=("auto", "12", "12H"),
                    help="which abilities the den draws from; auto tries both and keeps what PKHeX accepts")
    ap.add_argument("--prepare-only", action="store_true", help="build and check the file; do not host")
    ap.add_argument("--out", default=None, help="where to write the frame's file; default: the plugin's data folder")
    # Passed on to bin/swsh_host.py.
    ap.add_argument("--offer-file", action="append", default=[], help="the Pokemon our player brings")
    ap.add_argument("--raid-console-serves", action="store_true")
    ap.add_argument("--keys", default=None, help="prod.keys; the app passes Settings' file")
    ap.add_argument("--player-name", default="POKELDN")
    ap.add_argument("--trainer-name", default="POKELDN")
    ap.add_argument("--trainer-tid", default=None)
    ap.add_argument("--trainer-sid", default=None)
    ap.add_argument("--channel", default=None)
    ap.add_argument("--seconds", default=None)
    ap.add_argument("--received", default=None)
    return ap


def data_folder():
    try:
        from pokeldn.plugins import data_folder as folder
        return str(folder(PLUGIN_ID))
    except Exception:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def last_result():
    try:
        with open(os.path.join(data_folder(), LAST), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def pokeldn_root():
    import pokeldn
    return os.path.dirname(os.path.dirname(os.path.abspath(pokeldn.__file__)))


def species_table():
    """pokeldn's Sword/Shield species table: names and PersonalInfo rows."""
    path = os.path.join(pokeldn_root(), "pokeldn", "swsh", "data", "species.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def card(**kw):
    try:
        from pokeldn import panel
        panel.show(**kw)
    except Exception:
        pass


def template_ids():
    """The trainer ids of pokeldn's den boss template: the ids every hosted boss carries, since the
    host copies only the Pokemon's own fields onto that template, and the ids a retail console accepts."""
    from pokeldn.swsh import raid
    plain = core.decrypt_record(raid.WILD_BOSS.read_bytes())
    return plain[0x0C] | plain[0x0D] << 8, plain[0x0E] | plain[0x0F] << 8


def boss_copy(path, mode, kind):
    """-> the file the host serves. `template`: the den template's ids with the PID rewritten so the
    boss is shiny for them, the way pokeldn builds its always-shiny event raids; the console shows a
    shiny and, as the den generator does, rewrites the PID for the catcher to keep that state.
    `none`: the file as PKHeX passed it, plain on screen. `kind` is 1 star, 2 square."""
    if mode == "none":
        return path
    with open(path, "rb") as f:
        plain = bytearray(core.decrypt_record(f.read()))
    tid, sid = template_ids()
    pid = plain[0x1C] | plain[0x1D] << 8 | plain[0x1E] << 16 | plain[0x1F] << 24
    low = pid & 0xFFFF
    pid = ((low ^ tid ^ sid ^ (0 if kind == 2 else 1)) << 16) | low
    plain[0x1C:0x20] = pid.to_bytes(4, "little")
    plain[0x0C:0x0E] = tid.to_bytes(2, "little")
    plain[0x0E:0x10] = sid.to_bytes(2, "little")
    out = path[:-4] + "-boss.pk8"
    with open(out, "wb") as f:
        f.write(core.encrypt_record(bytes(plain)))
    return out


def main(args):
    last = last_result()
    seed_text = args.seed or last.get("seed")
    if not seed_text:
        raise SystemExit("No den seed: run Den seed first, or type the seed.")
    try:
        seed = int(str(seed_text).strip().removeprefix("0x").removeprefix("0X"), 16)
    except ValueError:
        raise SystemExit(f"The den seed is 16 hex digits: {seed_text!r}")
    path = args.file or last.get("file")
    if not path or not os.path.isfile(path):
        raise SystemExit("Choose the Pokemon you caught in the den: the frame's Pokemon is built from it.")
    if args.day < 1:
        raise SystemExit("The shiny day is the +N from the finder's list, 1 or more.")
    flawless = last.get("flawless") if args.flawless == "auto" else args.flawless
    try:
        flawless = int(flawless)
        assert 1 <= flawless <= 5
    except (TypeError, ValueError, AssertionError):
        raise SystemExit("Guaranteed perfect IVs is 1 to 5; auto needs a finder result.")

    with open(path, "rb") as f:
        raw = f.read()
    facts = core.read_record(raw)
    plain = core.decrypt_record(raw)
    species, form = facts["species"], facts["form"]
    tables = species_table()
    name = tables["species_names"].get(str(species), f"#{species:03d}")
    personal = tables["personal"].get(f"{species}/{form}")
    if personal is None:
        raise SystemExit(f"{name} form {form} is not in the Sword/Shield species table.")
    base, ratio, growth, abilities = tuple(personal[:6]), personal[6], personal[7], tuple(personal[8:11])
    rank = core.rank_of(facts["met_level"])
    if rank is None:
        raise SystemExit(f"{name} was met at level {facts['met_level']}, which no Max Raid den gives: "
                         "is it straight from a den?")
    frame_seed = (seed + args.day * core.XOROSHIRO_CONST) & core.MASK64
    level, dynamax = core.frame_level(frame_seed, rank)
    print(f"{name} from {os.path.basename(path)}, den seed {seed:016X}, day +{args.day}: "
          f"frame seed {frame_seed:016X}, a {rank + 1}-star raid at level {level}", flush=True)

    try:
        from pokeldn.pokemon import SERVICE
    except Exception:
        SERVICE = None
        print("PKHeX is not reachable here: the file is built but not checked.", flush=True)
    moves, move_pp = None, None
    if level != facts["met_level"] and SERVICE is not None:
        # The level changed: take the level-up moves PKHeX gives a legal catch at that level.
        try:
            trainer = {"ot": "POKELDN", "tid": facts["tid"], "sid": facts["sid"], "language": 2, "gender": 0}
            made = SERVICE.make("swsh", species, trainer, level=level, options={"form": form})
            with open(made["file"], "rb") as f:
                moves = core.read_record(f.read())["moves"]
            move_pp = [tables["move_pp"].get(str(m), 0) if m else 0 for m in moves]
        except Exception as error:
            print(f"Keeping the reference's moves: PKHeX gave none at level {level} ({error}).", flush=True)
    rules = ("12H", "12") if args.ability_rule == "auto" else (args.ability_rule,)
    folder = args.out or data_folder()
    os.makedirs(folder, exist_ok=True)
    built = None
    reports = []
    for rule in rules:
        values = core.frame_values(frame_seed, flawless, facts["tsv"], ratio, rule, species, form)
        for dmax in (max(dynamax, facts["dynamax"]), 10):
            record = core.encrypt_record(core.apply_frame(
                plain, values, abilities, base, level=level, growth=growth, moves=moves, move_pp=move_pp,
                dynamax=dmax))
            out = os.path.join(folder, f"frame-{args.day}-{name}-{frame_seed:016X}.pk8")
            with open(out, "wb") as f:
                f.write(record)
            if SERVICE is None:
                built = (rule, values, out, None, level, dmax)
                break
            reply = SERVICE.check("swsh", out)
            if reply.get("legal"):
                built = (rule, values, out, reply, level, dmax)
                break
            reports.append((rule, dmax, reply.get("report", "")))
        if built:
            break
    if built is None:
        for rule, dmax, report in reports:
            print(f"PKHeX refuses the file built with ability rule {rule}, Dynamax level {dmax}:\n{report}",
                  flush=True)
        card(id="den-frame", title=f"PKHeX refuses the day +{args.day} {name}", tone="error",
             lines=[f"Frame seed {frame_seed:016X}", "See the output for PKHeX's report. Is the reference "
                    "Pokemon straight from that den, with the guaranteed IVs the finder reported?"])
        raise SystemExit(1)

    rule, values, out, reply, level, dmax = built
    kinds = {0: "not shiny", 1: "star shiny", 2: "square shiny"}
    ability = (reply or {}).get("ability") or f"slot {values['ability_slot'] + 1}"
    lines = [f"Shiny\t{kinds[values['shiny']]}", f"Level\t{level}, {rank + 1} stars, Dynamax level {dmax}",
             f"IVs\t{core.ivs_text(values['ivs'])}", f"Nature\t{core.NATURES[values['nature']]}",
             f"Ability\t{ability}", f"EC / PID\t{values['ec']:08X} / {values['pid']:08X}",
             f"File\t{os.path.basename(out)}", f"PKHeX\t{'legal' if reply else 'not checked'}"]
    for line in lines:
        print("  " + line.replace("\t", ": "), flush=True)
    if not values["shiny"]:
        print("This day is not a shiny frame for this den. Hosting it anyway.", flush=True)
    card(id="den-frame", title=f"Day +{args.day} {name}: {kinds[values['shiny']]}", tone="ok",
         lines=lines, chips=[("Perfect IVs", str(flawless)), ("Ability rule", rule)])
    if args.prepare_only:
        print(f"Built {out}; not hosting.", flush=True)
        return
    if not args.offer_file:
        raise SystemExit("Choose the Pokemon our player brings to the raid.")

    # The console judges the boss by PID against the trainer ids in the record, then at the catch
    # writes a PID for the player that keeps that state: a shiny roll goes out shiny for the record's
    # trainer, a plain roll as rolled (verified on a retail Shield, square shiny in the box).
    mode = "template" if values["shiny"] else "none"
    boss = boss_copy(out, mode, values["shiny"] or 1)
    print(f"Boss record for the console: {'shiny for its trainer' if mode == 'template' else 'as rolled'}.",
          flush=True)
    argv = ["--raid-boss", boss]
    for offer in args.offer_file:
        argv += ["--offer-file", offer]
    if args.raid_console_serves:
        argv.append("--raid-console-serves")
    for flag, value in (("--keys", args.keys), ("--player-name", args.player_name),
                        ("--trainer-name", args.trainer_name), ("--trainer-tid", args.trainer_tid),
                        ("--trainer-sid", args.trainer_sid), ("--channel", args.channel),
                        ("--seconds", args.seconds), ("--received", args.received)):
        if value not in (None, ""):
            argv += [flag, str(value)]
    print(f"\nHosting the raid: {name}, {kinds[values['shiny']]}. Y-Comm, local wireless, join POKELDN's raid.",
          flush=True)
    sys.exit(run_host(argv))


def consistent_boss(raid):
    """Wraps pokeldn's boss builder so the boss record agrees with itself. The builder copies the
    ability id onto its den template but leaves the template's ability-slot byte, so a hidden ability
    arrives marked as slot 2; the Dynamax level and the height and weight stay the template's too.
    -> a function restoring the builder."""
    from pokeldn import gen8
    original = raid.boss_record

    def boss_record(pk8, template=None):
        out = bytearray(gen8.decrypt(original(pk8, template)))
        src = gen8.decrypt(bytes(pk8))
        out[0x16] = (out[0x16] & ~0x07) | (src[0x16] & 0x07)
        out[0x50:0x52] = src[0x50:0x52]
        out[0x90] = src[0x90]
        return gen8.encrypt(bytes(out))

    raid.boss_record = boss_record
    return lambda: setattr(raid, "boss_record", original)


def reassert_server(raid_battle):
    """Wraps the host's battle client for a race the console sometimes loses. Which station serves
    the battle comes from a table of server records; pokeldn publishes it with the console in slot 0
    so the console serves. Sometimes the console publishes a table of its own instead, framework
    object 0 from no station, with pokeldn's record in slot 0: it then waits for pokeldn to serve and
    the battle never starts. Republishing pokeldn's table puts the console back in slot 0.
    -> a function restoring the client."""
    original = raid_battle.Master.receive

    def receive(self, port, payload, src=None):
        out = original(self, port, payload, src)
        fw = raid_battle.parse_framework(payload)
        if fw is not None and fw["base"] == 0 and fw["station"] is None and not getattr(self, "_den_reasserted", False):
            self._den_reasserted = True
            self.log("[den] the console published its own server table, which stalls the battle; republishing "
                     "ours so the console serves. If the raid does not start within a few seconds, press Stop, "
                     "close the game fully and try again.")
            clock = self.t_clock()
            for k, console in enumerate(self.consoles):
                out.append((1, raid_battle.framework(k, None, clock, raid_battle.server_record(console, k)), None))
            out.append((1, raid_battle.framework(self.slot, None, clock,
                                                 raid_battle.server_record(self.station, self.slot,
                                                                           raid_battle.CLIENT_VERSION)), None))
        return out

    raid_battle.Master.receive = receive
    return lambda: setattr(raid_battle.Master, "receive", original)


def run_host(argv):
    """Runs bin/swsh_host.py in this process, as the first working raid did, with the boss builder
    made consistent and the server table reasserted. -> its exit code."""
    from pokeldn.swsh import raid, raid_battle
    restore_boss, restore_table = consistent_boss(raid), reassert_server(raid_battle)

    def restore():
        restore_boss()
        restore_table()
    script = os.path.join(pokeldn_root(), "bin", "swsh_host.py")
    saved_argv, saved_path = sys.argv, list(sys.path)
    sys.argv = [script, *argv]
    sys.path.insert(0, os.path.dirname(script))
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as stop:
        return stop.code or 0
    finally:
        restore()
        sys.argv, sys.path[:] = saved_argv, saved_path
    return 0


if __name__ == "__main__":
    try:
        main(build_parser().parse_args())
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
        sys.exit(1)
