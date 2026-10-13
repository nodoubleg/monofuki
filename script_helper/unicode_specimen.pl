#!/usr/bin/env perl
use v5.16;
use strict;
use warnings;
use utf8;
use Getopt::Long qw(GetOptions);
use JSON::PP qw(decode_json);
use FindBin qw($RealBin);
use File::Basename qw(basename);
use IO::Handle;

binmode STDOUT, ':encoding(UTF-8)';
binmode STDERR, ':encoding(UTF-8)';

open my $catalog_fh, '<:raw', "$RealBin/terminal_ranges.json" or die "Cannot read terminal ranges: $!\n";
my $catalog = do { local $/; decode_json(<$catalog_fh>) };
close $catalog_fh;
my @blocks = @{$catalog->{blocks}};
my $unicode_version = $catalog->{unicode_version};
my $data_dir = "$RealBin/unicode/$unicode_version";
my (%unicode, @unicode_ranges, @wide_ranges, %emoji);
open my $ucd, '<:encoding(UTF-8)', "$data_dir/UnicodeData.txt" or die "Cannot read Unicode data: $!\n";
my $first;
while (<$ucd>) {
    chomp;
    my ($hex, $name, $category) = split /;/;
    my $cp = hex $hex;
    if ($name =~ /^<(.+), First>$/) { $first = [$cp, $1, $category]; }
    elsif ($name =~ /, Last>$/) { push @unicode_ranges, [$first->[0], $cp, $first->[1], $category]; }
    else { $unicode{$cp} = {name => $name, category => $category}; }
}
close $ucd;
open my $eaw, '<:raw', "$data_dir/EastAsianWidth.txt" or die "Cannot read width data: $!\n";
while (<$eaw>) {
    push @wide_ranges, [hex($1), hex(defined $2 ? $2 : $1)]
        if /^([0-9A-F]+)(?:\.\.([0-9A-F]+))?\s*;\s*[WF]\b/;
}
close $eaw;
open my $variation, '<:raw', "$data_dir/emoji-variation-sequences.txt" or die "Cannot read emoji data: $!\n";
while (<$variation>) { $emoji{hex $1} = 1 if /^([0-9A-F]+) FE0F\s*;/ && hex($1) >= 0x80; }
close $variation;

sub character_info {
    my ($cp) = @_;
    return $unicode{$cp} if $unicode{$cp};
    for my $range (@unicode_ranges) {
        return {category => $range->[3], name => sprintf('%s U+%04X', $range->[2], $cp)}
            if $cp >= $range->[0] && $cp <= $range->[1];
    }
    return undef;
}

sub is_wide {
    my ($cp) = @_;
    for my $range (@wide_ranges) { return 1 if $cp >= $range->[0] && $cp <= $range->[1]; }
    return 0;
}
my (@sections, @ranges, $font, $encoded, $nerd, $missing, $names, $page, $list, $help, $raw_slots);
my ($columns, $rows, $start_page, $style) = (4, 12, 1, 'regular');
my $presentation = 'emoji';
GetOptions(
    'section=s@' => \@sections, 'range=s@' => \@ranges,
    'font=s' => \$font, 'encoded' => \$encoded, 'nerd' => \$nerd,
    'missing-only' => \$missing, 'names' => \$names, 'page' => \$page,
    'columns=i' => \$columns, 'rows=i' => \$rows, 'start-page=i' => \$start_page,
    'style=s' => \$style, 'list' => \$list, 'help|h' => \$help,
    'raw-slots' => \$raw_slots,
    'presentation=s' => \$presentation,
) or die "Try --help\n";
die "Unexpected arguments: @ARGV\n" if @ARGV;
if ($help) {
    print <<'HELP';
Usage: perl script_helper/unicode_specimen.pl [options]

Without options, print every code-point slot in the terminal ranges audited
for Monofuki. Each cell is labeled, for example: 025AA! [▪].
Select Monofuki in your terminal first; this script does not change fonts.

  --page                 Pause after each screenshot-sized page; Enter / q
  --section shapes       Print one named block (repeatable); --list lists names
  --range 1FB00-1FB3B     Print a custom hexadecimal range (repeatable)
  --font FILE.ttf        Read the intended font's Unicode character map
                         TTF and OTF supported; no external modules required
  --missing-only         Print only assigned characters absent from --font
  --encoded              Print all printable characters mapped by --font
  --nerd                 Also print mapped private-use icons from --font
  --names                One character per line with its Unicode name
  --raw-slots            Also render unassigned slots in Unicode 18.0.0
  --presentation emoji   emoji (default), text, or native (no selector)
                         Only standardized non-ASCII sequences get selectors
  --style italic         regular, bold, italic, or bold-italic
  --columns 4 --rows 12   Cells per row and rows per page
  --start-page 3          Skip earlier pages

With --font, ! means absent from that font, + means mapped. A missing glyph
can still appear through terminal fallback; the marker checks the file itself.
Without --font, ? means coverage is unknown. A dot (.) represents an unassigned
slot in the bundled Unicode 18.0.0 data, not a missing font glyph. Control/format
characters are labeled instead of emitted; combining marks are shown on 'a'.
Emoji uses FE0F to ask macOS for its color emoji fallback; text uses FE0E.
The font coverage marker checks the base character, not the emoji fallback.

Examples:
  perl script_helper/unicode_specimen.pl --section shapes --page
  perl script_helper/unicode_specimen.pl --font export/MonofukiNerdFont-Regular.otf --missing-only --page
  perl script_helper/unicode_specimen.pl --font export/MonofukiNerdFont-Regular.otf --encoded --page
HELP
    exit;
}
if ($list) {
    printf "%-12s U+%04X-U+%04X  %s\n", $_->[0], $_->[2], $_->[3], $_->[1] for @blocks;
    exit;
}
die "--columns must be 1-8; --rows must be 1-40; --start-page must be positive\n"
    unless $columns >= 1 && $columns <= 8 && $rows >= 1 && $rows <= 40 && $start_page >= 1;
my %sgr = (regular => 0, bold => 1, italic => 3, 'bold-italic' => '1;3');
die "--presentation must be emoji, text, or native\n" unless $presentation =~ /^(?:emoji|text|native)$/;
die "Unknown style '$style'\n" unless exists $sgr{$style};
die "--encoded, --nerd, and --missing-only require --font\n"
    if ($encoded || $nerd || $missing) && !$font;
die "--encoded cannot be combined with block selection or --missing-only\n"
    if $encoded && (@sections || @ranges || $missing);
die "--page requires an interactive terminal\n" if $page && !(-t STDIN && -t STDOUT);

# Read standard Unicode cmap formats 4 and 12 directly, using only core Perl.
# https://learn.microsoft.com/en-us/typography/opentype/spec/cmap
sub font_characters {
    my ($path) = @_;
    open my $fh, '<:raw', $path or die "Cannot read $path: $!\n";
    local $/; my $data = <$fh>; close $fh;
    my $slice = sub {
        my ($offset, $length) = @_;
        die "Truncated font table in $path\n" if $offset < 0 || $offset + $length > length $data;
        return substr $data, $offset, $length;
    };
    my $u16 = sub { unpack 'n', $slice->($_[0], 2) };
    my $u32 = sub { unpack 'N', $slice->($_[0], 4) };
    my $signature = $slice->(0, 4);
    die "Use a single TTF or OTF font, not WOFF2 or a font collection\n"
        unless $signature eq "\0\1\0\0" || $signature eq 'OTTO' || $signature eq 'true';
    my $cmap;
    for my $i (0 .. $u16->(4) - 1) {
        my $record = 12 + 16 * $i;
        $cmap = $u32->($record + 8) if $slice->($record, 4) eq 'cmap';
    }
    die "No character map in $path\n" unless defined $cmap;
    my @tables;
    for my $i (0 .. $u16->($cmap + 2) - 1) {
        my $record = $cmap + 4 + 8 * $i;
        my ($platform, $encoding) = ($u16->($record), $u16->($record + 2));
        next unless $platform == 0 || ($platform == 3 && ($encoding == 1 || $encoding == 10));
        my $offset = $cmap + $u32->($record + 4);
        my $format = $u16->($offset);
        next unless $format == 4 || $format == 12;
        push @tables, [$format, $platform == 3 ? 1 : 0, $offset];
    }
    die "No supported Unicode cmap (format 4 or 12) in $path\n" unless @tables;
    # Prefer full Unicode coverage, then the Windows Unicode subtable.
    my ($format, undef, $offset) = @{(sort { $b->[0] <=> $a->[0] || $b->[1] <=> $a->[1] } @tables)[0]};
    my %chars;
    if ($format == 12) {
        my $groups = $u32->($offset + 12);
        die "Truncated cmap groups in $path\n" if $groups > (length($data) - $offset - 16) / 12;
        for my $i (0 .. $groups - 1) {
            my $group = $offset + 16 + 12 * $i;
            my ($first, $last, $glyph) = map { $u32->($group + $_) } (0, 4, 8);
            die "Invalid Unicode cmap group\n" if $first > $last || $last > 0x10ffff;
            for my $cp ($first .. $last) { $chars{$cp} = 1 if $glyph + $cp - $first; }
        }
    } else {
        my $seg_count = $u16->($offset + 6);
        die "Invalid cmap segment count in $path\n" if !$seg_count || $seg_count % 2;
        my $count = $seg_count / 2;
        my $range_offsets = $offset + 16 + 6 * $count;
        for my $i (0 .. $count - 1) {
            my $last = $u16->($offset + 14 + 2 * $i);
            my $first = $u16->($offset + 16 + 2 * $count + 2 * $i);
            my $delta = $u16->($offset + 16 + 4 * $count + 2 * $i);
            my $address = $range_offsets + 2 * $i;
            my $relative = $u16->($address);
            die "Invalid Unicode cmap segment\n" if $first > $last;
            for my $cp ($first .. $last) {
                my $glyph = $relative ? $u16->($address + $relative + 2 * ($cp - $first)) : $cp;
                $glyph = ($glyph + $delta) & 0xffff if !$relative || $glyph;
                $chars{$cp} = 1 if $glyph;
            }
        }
    }
    return \%chars;
}

my $mapped = $font ? font_characters($font) : undef;
my @selected;
if ($encoded) {
    push @selected, ['encoded', 'All mapped characters', [sort { $a <=> $b } keys %$mapped]];
} else {
    my %requested = map { $_ => 1 } @sections;
    my %valid = map { $_->[0] => 1 } @blocks;
    die "Unknown section '$_'; use --list\n" for grep { !$valid{$_} } @sections;
    for my $block (@blocks) {
        next if (@sections || @ranges) && !$requested{$block->[0]};
        push @selected, [$block->[0], $block->[1], [$block->[2] .. $block->[3]]];
    }
    for my $range (@ranges) {
        $range =~ /^(?:U\+)?([0-9a-f]+)(?:[-:.]+(?:U\+)?([0-9a-f]+))?$/i or die "Invalid range '$range'\n";
        my ($first, $last) = (hex($1), hex(defined $2 ? $2 : $1));
        die "Invalid Unicode range '$range'\n" if $first > $last || $last > 0x10ffff;
        push @selected, [$range, 'Custom range', [$first .. $last]];
    }
    if ($nerd) {
        my @icons = grep { ($_ >= 0xe000 && $_ <= 0xf8ff) || ($_ >= 0xf0000 && $_ <= 0xffffd) || ($_ >= 0x100000 && $_ <= 0x10fffd) } sort { $a <=> $b } keys %$mapped;
        push @selected, ['nerd', 'Mapped private-use icons', \@icons];
    }
}

my (@pages, %seen);
for my $section (@selected) {
    my @cells;
    for my $cp (@{$section->[2]}) {
        next if $seen{$cp}++ || ($cp >= 0xd800 && $cp <= 0xdfff) || ($cp & 0xffff) >= 0xfffe || ($cp >= 0xfdd0 && $cp <= 0xfdef);
        my $info = character_info($cp);
        my $category = $info ? $info->{category} : 'Cn';
        next if $missing && ($category eq 'Cn' || $mapped->{$cp});
        next if $encoded && $category =~ /^(?:Cc|Cf)$/;
        my ($glyph, $width, $flag, $name) = (chr($cp), 1, '?', $info ? $info->{name} : 'UNASSIGNED IN UNICODE 18.0.0');
        if ($category eq 'Cn' && !($mapped && $mapped->{$cp}) && !$raw_slots) {
            ($glyph, $flag) = ('.', '.');
        } elsif ($category =~ /^(?:Cc|Cf)$/) {
            ($glyph, $width, $flag) = ('ctl', 3, '-');
        } else {
            $flag = $mapped ? ($mapped->{$cp} ? '+' : '!') : '?';
            if ($category =~ /^(?:Mn|Mc|Me)$/) { $glyph = 'a' . $glyph; }
            else { $width = 2 if is_wide($cp); }
            if ($emoji{$cp} && $presentation ne 'native') {
                $glyph .= $presentation eq 'emoji' ? "\x{FE0F}" : "\x{FE0E}";
                $width = 2 if $presentation eq 'emoji';
            }
        }
        my $styled = -t STDOUT && $style ne 'regular' ? "\e[$sgr{$style}m$glyph\e[0m" : $glyph;
        my $cell = sprintf '%05X%s [%s]', $cp, $flag, $styled;
        $cell .= ' ' x (4 - $width);
        $cell .= ' ' . ($name || 'PRIVATE USE') if $names;
        push @cells, $cell;
    }
    my $per_row = $names ? 1 : $columns;
    while (@cells) {
        my @lines;
        for (1 .. $rows) {
            last unless @cells;
            push @lines, join ' ', splice @cells, 0, $per_row;
        }
        push @pages, [$section->[1], \@lines];
    }
}
die "No characters match the selection\n" unless @pages;
die "--start-page exceeds " . scalar(@pages) . " pages\n" if $start_page > @pages;
for my $i ($start_page - 1 .. $#pages) {
    print "\e[2J\e[H" if $page;
    print "Monofuki Unicode specimen | $pages[$i][0] | page " . ($i + 1) . '/' . scalar(@pages) . "\n";
    print 'Font: ' . ($font ? basename($font) : 'terminal font; no file coverage check') . " | style: $style\n";
    print "Unicode $unicode_version | $presentation presentation | + mapped, ! absent, ? unchecked, . unassigned, - control\n\n";
    print join("\n", @{$pages[$i][1]}), "\n";
    if ($page && $i < $#pages) {
        print "\nScreenshot this page. Enter for next; q to quit: ";
        STDOUT->flush();
        my $answer = <STDIN>;
        last if !defined($answer) || $answer =~ /^q/i;
    } else { print "\n"; }
}
