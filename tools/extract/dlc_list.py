"""List the add-on content (DLC) packages of the game in a folder, for the runtime's nn::aoc answers.

    python dlc_list.py <folder with DLC .nsp files> [--out <aoc.txt>] [--files]

Every .nsp is read itself, not its file name: the title id comes from the header of each NCA inside (only the header
key of ~/.switch/prod.keys is needed for that). A package belongs to this game when its title id is in the game's
add-on content range: application id 0x01006A800016E000 + 0x1000 = base 0x01006A800016F000, add-on content index =
title id - base (1..0x7FF). --files also decrypts the content NCA (PublicData; title key from the ticket in the package) and lists the
files of its RomFS.

The output (default: print only) has one add-on content index per line, decimal, sorted, followed by a # comment with
its title id and package; lines starting with # are comments. scripts/setup.py --dlc writes it to build/sysdata/aoc.txt and
scripts/run.py hands it to the game as SSBU_AOC (runtime/nnmisc.c).
"""
import argparse
import os
import struct
import sys

import romfs_extract as RX

APPLICATION_ID = 0x01006A800016E000
AOC_BASE = APPLICATION_ID + 0x1000
TYPES = {0: 'Program', 1: 'Meta', 2: 'Control', 3: 'Manual', 4: 'Data', 5: 'PublicData'}


def nca_header(nsp, name):
    h = RX.xts_decrypt(RX.KEYS['header_key'], nsp.read(name, 0, 0xC00), 0)
    if h[0x200:0x204] != b'NCA3':
        return None
    return h[0x205], struct.unpack('<Q', h[0x210:0x218])[0]


def romfs_files(nsp):
    """Files of the RomFS of the package's content NCA (the largest NCA): [(path, size)]."""
    nca = RX.Nca(nsp)
    sec = nca.section(0)
    fs = sec['fs']
    if fs[0x8:0xC] != b'IVFC':
        return []
    level6 = struct.unpack('<Q', fs[0x8 + 0x10 + 5 * 0x18:0x8 + 0x18 + 5 * 0x18])[0]

    class Reader:
        def read(self, offset, size):
            return nca.read(sec, offset, size)
    return [(p, size) for p, _, size in RX.walk(Reader(), level6)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--out', help='write the index list to this file')
    ap.add_argument('--files', action='store_true', help='also list the files inside each package')
    a = ap.parse_args()
    found, other = {}, []
    names = sorted(n for n in os.listdir(a.folder) if n.lower().endswith('.nsp'))
    for n in names:
        nsp = RX.Nsp(os.path.join(a.folder, n))
        ids = set()
        for f in nsp.files:
            if f.endswith('.nca'):
                h = nca_header(nsp, f)
                if h:
                    ids.add((h[1], TYPES.get(h[0], str(h[0]))))
        tids = {t for t, _ in ids}
        if len(tids) != 1:
            other.append((n, 'several or no title ids: %s' % ', '.join('%016X %s' % x for x in sorted(ids))))
            continue
        tid = tids.pop()
        index = tid - AOC_BASE
        if not 0 < index < 0x800:
            other.append((n, 'title id %016X is not an add-on content of this game' % tid))
            continue
        line = '%-4d  %016X  %s' % (index, tid, '+'.join(sorted(t for _, t in ids)))
        if a.files:
            line += '  ' + ', '.join('%s (%d bytes)' % f for f in romfs_files(nsp))
        found[index] = (n, line)
        print(line)
    for n, why in other:
        print('SKIPPED %s: %s' % (n, why))
    print('%d add-on content packages of this game (%d other files skipped)' % (len(found), len(other)))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w') as f:
            f.write('# add-on content indices of SSBU (title id - %016X), from %s by tools/extract/dlc_list.py\n' % (AOC_BASE, os.path.abspath(a.folder)))
            for index in sorted(found):
                f.write('%d    # %016X %s\n' % (index, AOC_BASE + index, found[index][0]))
        print('written: %s' % a.out)
    return 0 if found or not names else 1


if __name__ == '__main__':
    sys.exit(main())
