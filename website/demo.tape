# Generate with VHS 0.12.1 from the repository root after build_site.py.
# The CI recording job installs this run's patched fonts before rendering.
Output "_site/media/monofuki.mp4"
Set Shell "bash"
Set FontFamily "Monofuki Nerd Font"
Set FontSize 23
Set Width 1200
Set Height 750
Set Padding 32
Set Framerate 30
Set TypingSpeed 35ms
Set CursorBlink false
Set WindowBar Colorful
Set BorderRadius 8
Set Theme { "name": "Crush", "background": "#201F26", "foreground": "#ECEBF0", "black": "#2D2C36", "red": "#FF577D", "green": "#68FFD6", "yellow": "#F5EF34", "blue": "#6B50FF", "magenta": "#FF84FF", "cyan": "#4FBEFE", "white": "#ECEBF0", "brightBlack": "#858392", "brightRed": "#FF6DAA", "brightGreen": "#00FFB2", "brightYellow": "#E8FE96", "brightBlue": "#8B75FF", "brightMagenta": "#FF84FF", "brightCyan": "#68FFD6", "brightWhite": "#F7F6FB", "cursor": "#FF84FF", "selection": "#6B50FF" }
Hide
Type "export PS1=''; clear"
Enter
Sleep 500ms
Type "clear; python3 script_helper/terminal_demo.py --scene characters"
Enter
Sleep 500ms
Show
Sleep 4s
Hide
Type "clear; python3 script_helper/terminal_demo.py --scene icons"
Enter
Sleep 500ms
Show
Sleep 3s
Hide
Type "clear; python3 script_helper/terminal_demo.py --scene globe"
Enter
Sleep 500ms
Show
Sleep 3s
Hide
Type "clear; python3 script_helper/terminal_demo.py --scene city"
Enter
Sleep 500ms
Show
Sleep 3s
Hide
Type "clear; python3 script_helper/terminal_demo.py --scene orbit"
Enter
Sleep 500ms
Show
Sleep 4s
