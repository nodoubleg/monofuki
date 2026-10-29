#!/usr/bin/env python3
"""Print a terminal font specimen. No dependencies; uses the terminal's active font."""

import argparse
import math
import shutil
import sys
import time

ANIMATION_FPS = 12
CELL_WIDTH = 575
CELL_HEIGHT = 1150
ANIMATION_SCENES = (("status", 7), ("city", 7), ("orbit", 8))
ANIMATION_DESCRIPTION = """The recording redraws three fixed terminal grids:
1. A Powerline status row, a filling block meter, and aligned character/operator samples.
2. Box-drawn buildings with changing windows, block-height meters, and moving arrows.
3. A circular Braille orbit with moving satellites, sampled at the font's actual dot pitch.
The final frame is held still. Playback is optional; nothing autoplays.
Terminal shaping and optical spacing support depend on the application.
"""

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


def artwork(columns, rows, phase=0, circular=False):
    # A six-lobed rosette sampled onto a Unicode Braille raster.
    bits = ((1, 8), (2, 16), (4, 32), (64, 128))
    width, height = columns * 2, rows * 4
    pitch_x, pitch_y = CELL_WIDTH / 2, CELL_HEIGHT / 4
    radius_scale = min(width * pitch_x, height * pitch_y) / 2
    for cy in range(rows):
        line = []
        for cx in range(columns):
            mask = 0
            for dy in range(4):
                for dx in range(2):
                    x = (cx * 2 + dx + 0.5 - width / 2) * pitch_x / radius_scale
                    y = (cy * 4 + dy + 0.5 - height / 2) * pitch_y / radius_scale
                    radius = math.hypot(x, y)
                    angle = math.atan2(y, x)
                    ribbon = 0.58 + 0.19 * math.cos(6 * angle + radius * 4 - phase)
                    lit = abs(radius - ribbon) < 0.095
                    if circular:
                        # A stationary circle proves aspect; three inner satellites
                        # make motion visible without distorting that reference.
                        lit = abs(radius - 0.86) < 0.025
                        for satellite in range(3):
                            a = phase + satellite * math.tau / 3
                            lit |= math.hypot(x - .59 * math.cos(a), y - .59 * math.sin(a)) < .09
                    if lit:
                        mask |= bits[dy][dx]
            line.append(chr(0x2800 + mask))
        yield "".join(line)


def animation_frame(scene, phase, styled=False):
    """A deterministic redraw: at most 76 columns by 22 rows, no terminal reads.

    Phase is normalized 0..1; all movement uses the existing encoded repertoire.
    Keep the artwork/gallery API above static so text alternatives remain useful.
    """
    def color(text, value):
        return f"\033[{value}m{text}\033[0m" if styled else text

    header = [color("monofuki / in motion", "38;2;255;132;255"), ""]
    if scene == "status":
        filled = round(phase * 40)
        meter = "█" * filled + "░" * (40 - filled)
        caret = min(39, int(phase * 40))
        return header + [
            color("01 / STATUS REDRAWS", "38;2;104;255;214"),
            "Same columns. Changing content.", "",
            color("\uf07b monofuki \ue0b0 \ue0a0 master \ue0b0 \uf120 terminal", "38;2;104;255;214"),
            "", "┌" + "─" * 52 + "┐",
            "│" + f"  {meter}  {round(phase * 100):3d}%".ljust(52) + "│",
            "└" + "─" * 52 + "┘", "",
            "  0Oo  1lI|!  B8  rn m  ag  (){}[]<>",
            "  ==  !=  <=  >=  ->  =>  ++  ::  &&  ||",
            color("  " + " " * caret + "⇧", "38;2;255;132;255"), "",
            "", "Letters, operators and icons stay on a mono grid.",
            "Optical spacing support depends on your terminal.",
        ]
    if scene == "city":
        tick = int(phase * 48)
        heights = [1 + round(7 * (0.5 + 0.5 * math.sin(phase * math.tau * 2 + i * .63)))
                   for i in range(24)]
        windows = ("░", "▒", "▓", "█")
        towers = []
        for row in range(7):
            towers.append("  │" + "│".join(
                windows[(row + i + tick // 3) % 4] * 7 for i in range(5)) + "│")
        bars = ["  " + "".join("██" if h > row else "  " for h in heights)
                for row in reversed(range(8))]
        # A narrow skyline leaves room for a readable meter beneath it.
        return header + [color("02 / TERMINAL AFTER DARK", "38;2;161;138;255"),
            "Box joins, shading and blocks in step.", "",
            "  ┌───────┬───────┬───────┬───────┬───────┐",
            color(towers[0], "38;2;161;138;255"),
            color(towers[1], "38;2;161;138;255"),
            "  └───────┴───────┴───────┴───────┴───────┘",
            color("  " + " " * (tick % 42) + "⇨", "38;2;255;132;255"),
            *[color(line, "38;2;104;255;214") for line in bars],
            "  " + "─" * 48, "", "  ▁▂▃▄▅▆▇█   one cell wide, row after row."]
    if scene == "orbit":
        return header + [color("03 / A BRAILLE ORBIT", "38;2;104;255;214"),
            "Two dots across. Four down. A continuous grid.", "",
            *[color("  " + line, "38;2;104;255;214") for line in artwork(56, 14, phase * math.tau, circular=True)],
            "", "  ⠁ ⠂ ⠄ ⠈ ⠐ ⠠ ⡀ ⢀    256 patterns, including blank ⠀"]
    raise ValueError(f"Unknown animation scene: {scene}")


def animation_frames(fps=ANIMATION_FPS):
    for scene, seconds in ANIMATION_SCENES:
        count = seconds * fps
        for index in range(count):
            yield animation_frame(scene, index / (count - 1), styled=True)


def animate(record=False):
    # One write per frame; erase line tails and pad short scenes to avoid ghosts.
    # Deadline scheduling avoids accumulating redraw time over the whole movie.
    start = time.monotonic()
    sys.stdout.write(("" if record else "\033[?1049h") + "\033[?25l\033[2J")
    try:
        for index, lines in enumerate(animation_frames()):
            frame = lines + [""] * (22 - len(lines))
            sys.stdout.write("\033[H" + "\r\n".join(line + "\033[K" for line in frame))
            sys.stdout.flush()
            time.sleep(max(0, start + (index + 1) / ANIMATION_FPS - time.monotonic()))
    finally:
        sys.stdout.write("\033[0m\033[?25h" + ("" if record else "\033[?1049l"))
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=48, help="art width in terminal columns (16–100)")
    parser.add_argument("--all", action="store_true", help="also print all 256 Braille patterns")
    parser.add_argument("--plain", action="store_true", help="omit ANSI bold/italic style samples")
    parser.add_argument("--art", action="store_true", help="print every artwork shown on the project website")
    parser.add_argument("--animate", action="store_true", help="play the 22-second terminal animation (ANSI redraws)")
    parser.add_argument("--record", action="store_true", help="leave the final animation frame visible for VHS; otherwise restore the previous screen")
    parser.add_argument("--scene", choices=("characters", "icons", "globe", "orbit", "city", "all"),
                        help="print a scene used in the VHS specimen recording")
    args = parser.parse_args()
    if args.animate:
        if not sys.stdout.isatty():
            parser.error("--animate requires a terminal")
        size = shutil.get_terminal_size()
        needed_columns = max(len(line) for scene, _ in ANIMATION_SCENES
                             for line in animation_frame(scene, 0)) + 1
        if size.columns < needed_columns or size.lines < 23:
            parser.error(f"--animate needs at least {needed_columns} columns by 23 rows")
        try:
            animate(record=args.record)
        except KeyboardInterrupt:
            pass
        return
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
