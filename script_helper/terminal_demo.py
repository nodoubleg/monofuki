#!/usr/bin/env python3
"""Print a terminal font specimen. No dependencies; uses the terminal's active font."""

import argparse
import math
import shutil
import sys

CHARACTER_SAMPLE = 'agil|!0Oo$#@&(){}[]<>;:\'"`.,-_=+'
GLOBE = r'''           .-""""""""-.
        .-'     |      '-.
      .'      .-+-.       '.
     /      .'  |  '.       \
    ;------/----+----\-------;
    |     ;     |     ;      |
    ;------\----+----/-------;
     \      '.  |  .'       /
      '.      '-+-'       .'
        '-.     |      .-'
           '-........-' '''.rstrip()
CITY = """                 ⇧  ⇨  ⇩  ⇯
     ┌───┐          ┌──────┐
     │░░░│  ┌────┐  │▒▒▒▒▒▒│
  ┌──┤░░░├──┤▓▓▓▓├──┤▒▒▒▒▒▒├──┐
  │  │░░░│  │▓▓▓▓│  │▒▒▒▒▒▒│  │
  └──┴───┴──┴────┴──┴──────┴──┘
  ▁▂▃▄▅▆▇█  terminal after dark"""


def art_pieces():
    """One source for the website gallery and the printable terminal demo."""
    return (
        ("globe", "ASCII globe", "ASCII, spaces, and punctuation", GLOBE),
        ("orbit", "A Braille orbit", "Dots on a two-by-four grid",
         "\n".join(artwork(40, 16))),
        ("city", "Terminal after dark", "Box drawing, blocks, and restored arrows", CITY),
    )


def print_scene(scene, styled=False):
    def color(text, rgb):
        return f'\033[38;2;{rgb}m{text}\033[0m' if styled else text

    if scene == "characters":
        print(color("Monofuki character specimen", "255;132;255") + '\n')
        print(color(CHARACTER_SAMPLE, "161;138;255"))
        print("\n0Oo  1lI|!  B8  rn m  (){}[]<>")
        styles = '\033[1mBold\033[0m   \033[3mItalic\033[0m   \033[1;3mBold italic\033[0m' if styled else 'Bold   Italic   Bold italic'
        print('\n' + styles)
    elif scene == "icons":
        print(color("Nerd Font icons + terminal graphics", "255;132;255") + '\n')
        print(color("\uf07b  monofuki   \ue0a0 master   \uf120 python3", "104;255;214"))
        print(color("\n┌──────────────────────────────┐\n│  ⇨ ⇩ ⇯   ░▒▓█   ⠁⠂⠄⠈⠐⠠⡀⢀  │\n└──────────────────────────────┘", "161;138;255"))
    else:
        colors = {'globe': '255;132;255', 'orbit': '104;255;214', 'city': '161;138;255'}
        for key, title, _, text in art_pieces():
            if scene in (key, "all"):
                print(f"{title}\n\n{color(text, colors[key])}\n")


def artwork(columns, rows):
    # A six-lobed rosette sampled onto a Unicode Braille raster.
    bits = ((1, 8), (2, 16), (4, 32), (64, 128))
    width, height = columns * 2, rows * 4
    for cy in range(rows):
        line = []
        for cx in range(columns):
            mask = 0
            for dy in range(4):
                for dx in range(2):
                    x = (cx * 2 + dx + 0.5 - width / 2) / (width / 2)
                    y = (cy * 4 + dy + 0.5 - height / 2) / (height / 2)
                    radius = math.hypot(x, y)
                    angle = math.atan2(y, x)
                    ribbon = 0.58 + 0.19 * math.cos(6 * angle + radius * 4)
                    if abs(radius - ribbon) < 0.095:
                        mask |= bits[dy][dx]
            line.append(chr(0x2800 + mask))
        yield "".join(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=48, help="art width in terminal columns (16–100)")
    parser.add_argument("--all", action="store_true", help="also print all 256 Braille patterns")
    parser.add_argument("--plain", action="store_true", help="omit ANSI bold/italic style samples")
    parser.add_argument("--art", action="store_true", help="print every artwork shown on the project website")
    parser.add_argument("--scene", choices=("characters", "icons", "globe", "orbit", "city", "all"),
                        help="print a scene used in the VHS specimen recording")
    args = parser.parse_args()
    if args.art or args.scene:
        print_scene("all" if args.art else args.scene, styled=sys.stdout.isatty() and not args.plain)
        return
    if not 16 <= args.width <= 100:
        parser.error("--width must be between 16 and 100")
    width = min(args.width, max(16, shutil.get_terminal_size((80, 24)).columns - 2))
    print("Monofuki terminal graphics")
    print("Select the rebuilt font in your terminal, then rerun.")
    print("Dots should stay evenly spaced across text rows.\n")
    print("\n".join(artwork(width, max(8, round(width / 2.14)))))
    print("\nSeam check: this should be one continuous dot grid.")
    for _ in range(6):
        print("⣿" * min(width, 32))
    print("\nBox drawing and solid blocks: look for broken joins.")
    print("┌────────┬────────┐  ████████████")
    print("│        │        │  ████████████")
    print("├────────┼────────┤  ████████████")
    print("│        │        │  ▄▄▄▄▄▄▄▄▄▄▄▄")
    print("└────────┴────────┘  ▀▀▀▀▀▀▀▀▀▀▀▀")
    print("\nArrows: ⇦ ⇧ ⇨ ⇩ ⇯   Shades: ░▒▓█")
    print("Dot order 1–8: ⠁ ⠂ ⠄ ⠈ ⠐ ⠠ ⡀ ⢀")
    print("Blank Braille has one-cell width: |⠀| | |")
    if sys.stdout.isatty() and not args.plain:
        print("\nStyle grid: regular / bold / italic / bold italic")
        for sgr in ("0", "1", "3", "1;3"):
            print(f"\033[{sgr}⣿⣿⣿⣿⣿⣿⣿⣿  ⇨ ⇩ ⇯\033[0m")
    if args.all:
        print("\nAll 256 Braille patterns (16 per row):")
        for start in range(0x2800, 0x2900, 16):
            print(f"{start:04X}  " + "".join(chr(cp) for cp in range(start, start + 16)))


if __name__ == "__main__":
    main()
