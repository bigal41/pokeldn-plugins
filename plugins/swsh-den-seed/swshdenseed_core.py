"""Sword/Shield Max Raid den seed recovery, pure Python.

A den's Pokemon is drawn from xoroshiro128+ seeded with the den seed (s0) and the game's fixed
second word (s1): the encryption constant, a fake trainer id, the PID, the IVs and the rest, in that
order, each as the low bits of one output. The first output's low 32 bits are the EC, so the seed's
low half is the EC minus the constant's low half. The upper half is found from the PID: every state
bit is a GF(2)-affine function of those 32 unknown bits, and the PID is the integer sum of two such
words, so a bit-by-bit guess-and-determine with Gaussian elimination recovers it in a few thousand
steps. The IVs then pick the right candidate and the den's flawless count by simulation.

Generation order and masks follow PokeFinder's RaidGenerator (Admiral Fish) and the community
seed checkers. A day advances the den seed by the xoroshiro constant.
"""
import struct

MASK64 = (1 << 64) - 1
MASK32 = 0xFFFFFFFF
XOROSHIRO_CONST = 0x82A2B175229D6A5B
STAT_NAMES = ("HP", "Atk", "Def", "SpA", "SpD", "Spe")
ANTI_SHINY = 0x10000000           # the game flips this PID bit when a non-shiny roll would be shiny


def _rotl(x, k):
    return ((x << k) | (x >> (64 - k))) & MASK64


class Xoroshiro:
    """xoroshiro128+ as the game seeds it: s0 = seed, s1 = the fixed constant."""

    def __init__(self, seed):
        self.s0, self.s1 = seed & MASK64, XOROSHIRO_CONST

    def next(self):
        s0, s1 = self.s0, self.s1
        out = (s0 + s1) & MASK64
        s1 ^= s0
        self.s0 = (_rotl(s0, 24) ^ s1 ^ ((s1 << 16) & MASK64)) & MASK64
        self.s1 = _rotl(s1, 37)
        return out

    def next_uint(self, maximum):
        """A value below `maximum`: masked to the next power of two, redrawn while too big."""
        mask = (1 << (maximum - 1).bit_length()) - 1
        while True:
            value = self.next() & mask
            if value < maximum:
                return value


def shiny_kind(pid, tsv):
    """0 not shiny, 1 star, 2 square, for a PID against a trainer shiny value (tid ^ sid)."""
    xor = (pid >> 16) ^ (pid & 0xFFFF) ^ tsv
    return 2 if xor == 0 else 1 if xor < 16 else 0


def raid_pokemon(seed, flawless, tsv=None):
    """The Pokemon a den seed gives with `flawless` guaranteed 31s. `tsv` is the catcher's tid ^ sid;
    with it the PID is the one the game stores, otherwise the raw roll."""
    rng = Xoroshiro(seed)
    ec = rng.next_uint(MASK32)
    sidtid = rng.next_uint(MASK32)
    pid = rng.next_uint(MASK32)
    raw_pid = pid
    shiny = shiny_kind(pid, (sidtid >> 16) ^ (sidtid & 0xFFFF))
    if tsv is not None:
        if shiny:
            pid = (((pid & 0xFFFF) ^ tsv ^ (0 if shiny == 2 else 1)) << 16) | (pid & 0xFFFF)
        elif shiny_kind(pid, tsv):
            pid ^= ANTI_SHINY
    ivs = [-1] * 6
    for _ in range(flawless):
        while True:
            i = rng.next_uint(6)
            if ivs[i] == -1:
                break
        ivs[i] = 31
    for i in range(6):
        if ivs[i] == -1:
            ivs[i] = rng.next_uint(32)
    return {"seed": seed, "ec": ec, "sidtid": sidtid, "pid": pid, "raw_pid": raw_pid, "shiny": shiny,
            "ivs": tuple(ivs)}


# --- the symbolic side: forms over GF(2) in the 32 unknown bits of the seed's upper half ------------
# A form is an int: bits 0..31 are the coefficients of unknowns h0..h31, bit 32 is the constant.
CONST = 1 << 32


def _sym_state(low32):
    s0 = [CONST if (low32 >> j) & 1 else 0 for j in range(32)] + [1 << j for j in range(32)]
    s1 = [CONST if (XOROSHIRO_CONST >> j) & 1 else 0 for j in range(64)]
    return s0, s1


def _sym_step(s0, s1):
    s1 = [a ^ b for a, b in zip(s1, s0)]
    rot24 = s0[40:] + s0[:40]
    shl16 = [0] * 16 + s1[:48]
    return [a ^ b ^ c for a, b, c in zip(rot24, s1, shl16)], s1[27:] + s1[:27]


def _reduce(basis, form):
    for pivot, row in basis:            # descending pivots; a row has no bit above its pivot
        if (form >> pivot) & 1:
            form ^= row
    return form


def _insert(basis, form):
    """The basis with `form = 0` added, unchanged when implied, None when contradicted."""
    form = _reduce(basis, form)
    if form & MASK32 == 0:
        return basis if form == 0 else None
    pivot = (form & MASK32).bit_length() - 1
    out = list(basis)
    at = 0
    while at < len(out) and out[at][0] > pivot:
        at += 1
    out.insert(at, (pivot, form))
    return tuple(out)


def _solve_sum(a_forms, b_forms, known, limit=1 << 18):
    """Bases describing every h with low32(A + B) matching `known` (a bit per position, None free)."""
    leaves = []

    def rec(i, basis, carry):
        if len(leaves) >= limit:
            raise RuntimeError("too many candidate seeds: the PID gives too little to go on")
        if i == 32:
            leaves.append(basis)
            return
        a, b = a_forms[i], b_forms[i]
        for p in ((known[i],) if known[i] is not None else (0, 1)):
            q = p ^ carry                               # a_i xor b_i, given the carry in
            nb = _insert(basis, a ^ b ^ (CONST if q else 0))
            if nb is None:
                continue
            if q:                                       # a_i != b_i: the carry passes through
                rec(i + 1, nb, carry)
                continue
            ra = _reduce(nb, a)                         # a_i == b_i: the carry out is a_i
            if ra & MASK32 == 0:
                rec(i + 1, nb, ra >> 32)
            else:
                for v in (0, 1):
                    nb2 = _insert(nb, a ^ (CONST if v else 0))
                    if nb2 is not None:
                        rec(i + 1, nb2, v)

    rec(0, (), 0)
    return leaves


def _solutions(basis, limit=1 << 20):
    rows = sorted(basis)
    pivots = {p for p, _ in rows}
    free = [j for j in range(32) if j not in pivots]
    if 1 << len(free) > limit:
        raise RuntimeError("too many candidate seeds: the PID gives too little to go on")
    for n in range(1 << len(free)):
        h = 0
        for k, j in enumerate(free):
            if (n >> k) & 1:
                h |= 1 << j
        for p, row in rows:
            if (((row & MASK32 & ~(1 << p)) & h).bit_count() + (row >> 32)) & 1:
                h |= 1 << p
        yield h


def candidate_seeds(ec, pid, shiny):
    """Every den seed whose first and third draws give this EC and PID, before the IVs are checked."""
    low32 = (ec - (XOROSHIRO_CONST & MASK32)) & MASK32
    s0, s1 = _sym_state(low32)
    s0, s1 = _sym_step(*_sym_step(s0, s1))             # the third output is s0 + s1 of this state
    if shiny:                                           # the game rewrote the upper half
        known = [(pid >> i) & 1 if i < 16 else None for i in range(32)]
    else:                                               # it may have flipped the anti-shiny bit
        known = [(pid >> i) & 1 if i != 28 else None for i in range(32)]
    seeds = set()
    for basis in _solve_sum(s0[:32], s1[:32], known):
        for h in _solutions(basis):
            seeds.add((h << 32) | low32)
    return sorted(seeds)


def find(ec, pid, ivs, shiny, tsv=None, flawless=(1, 2, 3, 4, 5)):
    """-> [(seed, flawless, pokemon)] matching the EC, PID and IVs of a caught Pokemon. `shiny` is
    whether it came out shiny; `tsv` the catcher's tid ^ sid when known, which pins the PID exactly."""
    ivs = tuple(ivs)
    out = []
    for seed in candidate_seeds(ec, pid, shiny):
        for count in flawless:
            mon = raid_pokemon(seed, count, tsv)
            if mon["ec"] != ec or mon["ivs"] != ivs:
                continue
            if tsv is not None:
                if mon["pid"] != pid:
                    continue
            elif shiny:
                if not mon["shiny"] or (mon["raw_pid"] ^ pid) & 0xFFFF:
                    continue
            elif mon["raw_pid"] not in (pid, pid ^ ANTI_SHINY):
                continue
            out.append((seed, count, mon))
    return out


def shiny_frames(seed, flawless, frames, count, tsv=None):
    """The first `count` shiny frames within `frames` days of `seed`: (days, kind, pokemon)."""
    out = []
    for n in range(1, frames + 1):
        s = (seed + n * XOROSHIRO_CONST) & MASK64
        rng = Xoroshiro(s)
        rng.next_uint(MASK32)
        sidtid = rng.next_uint(MASK32)
        pid = rng.next_uint(MASK32)
        kind = shiny_kind(pid, (sidtid >> 16) ^ (sidtid & 0xFFFF))
        if kind:
            out.append((n, kind, raid_pokemon(s, flawless, tsv)))
            if len(out) >= count:
                break
    return out


# --- reading a Gen-8 record (.pk8 / .ek8), PKHeX's PokeCrypto ------------------------------------
HEADER, BLOCK, STORED, PARTY = 8, 0x50, 0x148, 0x158
BLOCK_ORDER = (
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 1, 3), (0, 3, 1, 2), (0, 2, 3, 1), (0, 3, 2, 1),
    (1, 0, 2, 3), (1, 0, 3, 2), (2, 0, 1, 3), (3, 0, 1, 2), (2, 0, 3, 1), (3, 0, 2, 1),
    (1, 2, 0, 3), (1, 3, 0, 2), (2, 1, 0, 3), (3, 1, 0, 2), (2, 3, 0, 1), (3, 2, 0, 1),
    (1, 2, 3, 0), (1, 3, 2, 0), (2, 1, 3, 0), (3, 1, 2, 0), (2, 3, 1, 0), (3, 2, 1, 0),
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 1, 3), (0, 3, 1, 2), (0, 2, 3, 1), (0, 3, 2, 1),
    (1, 0, 2, 3), (1, 0, 3, 2),
)
IV_SHIFTS = (0, 5, 10, 20, 25, 15)     # HP, Atk, Def, SpA, SpD, Spe inside the IV32 word


def _crypt(chunk, seed):
    out = bytearray(chunk)
    for i in range(0, len(out) - 1, 2):
        seed = (seed * 0x41C64E6D + 0x6073) & MASK32
        struct.pack_into("<H", out, i, struct.unpack_from("<H", out, i)[0] ^ (seed >> 16))
    return bytes(out)


def _checksum(plain):
    return sum(struct.unpack_from(f"<{(STORED - HEADER) // 2}H", plain, HEADER)) & 0xFFFF


def read_record(raw):
    """-> ec, pid, ivs, tid, sid, species, shiny of a .pk8 / .ek8, encrypted or PKHeX's plain export."""
    if len(raw) not in (STORED, PARTY):
        raise ValueError(f"{len(raw)} bytes; a Sword/Shield record is {STORED} or {PARTY}")
    want = struct.unpack_from("<H", raw, 6)[0]
    if _checksum(raw) == want:
        plain = bytes(raw)
    else:
        ec = struct.unpack_from("<I", raw, 0)[0]
        body = _crypt(raw[HEADER:STORED], ec)
        order = BLOCK_ORDER[(ec >> 13) & 31]
        plain = bytes(raw[:HEADER]) + b"".join(body[src * BLOCK:(src + 1) * BLOCK] for src in order)
        if _checksum(plain) != want:
            raise ValueError("not a Sword/Shield Pokemon file: the checksum does not match")
    u16 = lambda o: struct.unpack_from("<H", plain, o)[0]
    u32 = lambda o: struct.unpack_from("<I", plain, o)[0]
    iv32 = u32(0x8C)
    tid, sid, pid = u16(0x0C), u16(0x0E), u32(0x1C)
    return {"ec": u32(0), "pid": pid, "ivs": tuple((iv32 >> s) & 31 for s in IV_SHIFTS), "tid": tid,
            "sid": sid, "tsv": tid ^ sid, "species": u16(0x08), "shiny": shiny_kind(pid, tid ^ sid),
            "version": plain[0xDE]}


def ivs_text(ivs):
    return "/".join(str(v) for v in ivs)
