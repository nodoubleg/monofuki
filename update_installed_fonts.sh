#!/usr/bin/env bash
# Update already-installed Monofuki styles to OTF in the macOS user Fonts directory.
# Backups live outside Fonts so macOS does not register duplicate font copies.
set -euo pipefail

update_fonts() {
    local source_dir=$1 font_dir=$2 backup_root=$3 dry_run=$4
    local base source target installed backup_dir staged has_installed style_changed
    local -a updates=() removals=() backups=()
    local matched=0 update_count=0 remove_count=0 backup_count=0

    if [[ ! -d "$source_dir" || ! -d "$font_dir" ]]; then
        echo "Missing export or installed-font directory: $source_dir / $font_dir" >&2
        return 1
    fi

    # Only known Monofuki families/styles, and only ones already installed.
    # Plan all replacements, duplicate removals, and backups before any writes.
    for base in Monofuki-{Regular,Italic,Bold,Bold-Italic} \
                MonofukiNerdFont-{Regular,Italic,Bold,BoldItalic}; do
        source="$source_dir/$base.otf"
        target="$font_dir/$base.otf"
        has_installed=false
        for installed in "$target" "$font_dir/$base.ttf" "$font_dir/$base-hinted.ttf"; do
            if [[ -L "$installed" ]]; then
                echo "Refusing to replace a managed/symlinked font: $installed" >&2
                return 1
            fi
            if [[ -e "$installed" && ! -f "$installed" ]]; then
                echo "Not a regular font file: $installed" >&2
                return 1
            fi
            [[ ! -f "$installed" ]] || has_installed=true
        done
        [[ "$has_installed" == true ]] || continue
        matched=$((matched + 1))
        if [[ ! -f "$source" || ! -s "$source" ]]; then
            echo "Missing or empty OTF export: $source. Rebuild before updating." >&2
            return 1
        fi
        style_changed=false
        if ! cmp -s "$source" "$target"; then
            updates+=("$source")
            update_count=$((update_count + 1))
            style_changed=true
            echo "Install OTF: $source -> $target"
        fi
        for installed in "$font_dir/$base.ttf" "$font_dir/$base-hinted.ttf"; do
            if [[ -f "$installed" ]]; then
                removals+=("$installed")
                remove_count=$((remove_count + 1))
                style_changed=true
                echo "Retire TTF:  $installed (after OTF verification)"
            fi
        done
        if [[ "$style_changed" == true ]]; then
            for installed in "$target" "$font_dir/$base.ttf" "$font_dir/$base-hinted.ttf"; do
                if [[ -f "$installed" ]]; then
                    backups+=("$installed")
                    backup_count=$((backup_count + 1))
                fi
            done
        else
            echo "Current OTF: $base.otf"
        fi
    done

    if (( matched == 0 )); then
        echo "No supported Monofuki fonts are already installed in $font_dir." >&2
        echo "Install the desired family with Font Book first." >&2
        return 1
    fi
    if (( update_count == 0 && remove_count == 0 )); then
        echo "All $matched installed styles already use the current OTFs."
        return 0
    fi
    if [[ "$dry_run" == true ]]; then
        echo "Dry run: $update_count OTF update(s), $remove_count TTF removal(s), $backup_count backup(s). No files changed."
        return 0
    fi

    mkdir -p "$backup_root"
    backup_dir=$(mktemp -d "$backup_root/$(date +%Y%m%d-%H%M%S).XXXXXX")
    # Finish and verify every backup before replacing any installed font.
    for installed in "${backups[@]}"; do
        cp -p "$installed" "$backup_dir/"
        cmp -s "$installed" "$backup_dir/$(basename "$installed")"
    done
    echo "Backups: $backup_dir"

    if (( update_count > 0 )); then
        for source in "${updates[@]}"; do
            target="$font_dir/$(basename "$source")"
            staged=$(mktemp "$font_dir/.monofuki-update.XXXXXX")
            if ! cp "$source" "$staged" || ! chmod 644 "$staged" || ! cmp -s "$source" "$staged"; then
                rm -f "$staged"
                echo "Could not stage $source; backups are in $backup_dir" >&2
                return 1
            fi
            # Same-directory rename avoids leaving a partly written font file.
            if ! mv -f "$staged" "$target"; then
                rm -f "$staged"
                echo "Could not replace $target; backups are in $backup_dir" >&2
                return 1
            fi
            if ! cmp -s "$source" "$target"; then
                echo "Verification failed for $target; backups are in $backup_dir" >&2
                return 1
            fi
        done
    fi
    # Remove superseded TTFs only after every OTF replacement has succeeded.
    if (( remove_count > 0 )); then
        for installed in "${removals[@]}"; do
            base=$(basename "$installed" .ttf)
            base=${base%-hinted}
            if ! cmp -s "$source_dir/$base.otf" "$font_dir/$base.otf"; then
                echo "OTF verification failed; keeping $installed" >&2
                return 1
            fi
            rm "$installed"
        done
    fi
    echo "Updated and verified $update_count OTF(s); retired $remove_count TTF(s)."
    echo "Quit and reopen your terminal and other apps using these fonts to reload them."
}

main() {
    local dry_run=false
    case "${1:-}" in
        --dry-run) dry_run=true; shift ;;
        --help|-h)
            echo "Usage: $0 [--dry-run]"
            echo "Update already-installed Monofuki styles in ~/Library/Fonts to export/ OTF files."
            echo "Back up changed files to ~/Library/Application Support/Monofuki/font-backups/."
            echo "Back up replaced fonts and remove superseded TTFs after verifying the OTFs."
            echo "Build first. This does not install new styles, rebuild fonts, or restart apps."
            return 0 ;;
    esac
    if (( $# != 0 )); then
        echo "Usage: $0 [--dry-run]" >&2
        return 1
    fi
    if [[ "$(uname -s)" != Darwin ]]; then
        echo "This helper is for macOS." >&2
        return 1
    fi
    local repo_dir
    repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    update_fonts "$repo_dir/export" "$HOME/Library/Fonts" \
        "$HOME/Library/Application Support/Monofuki/font-backups" "$dry_run"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
