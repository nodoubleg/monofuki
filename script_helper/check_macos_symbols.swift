// macOS-only fallback audit. Does not install fonts or change terminal settings.
// swift script_helper/check_macos_symbols.swift export/MonofukiNerdFont-*.otf
import Foundation
import CoreText

let directory = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
let config = try JSONSerialization.jsonObject(with: Data(contentsOf: directory.appendingPathComponent("terminal_ranges.json"))) as! [String: Any]
let version = config["unicode_version"] as! String
let blocks = config["blocks"] as! [[Any]]
let unicodeDirectory = directory.appendingPathComponent("unicode/\(version)")
let records = try String(contentsOf: unicodeDirectory.appendingPathComponent("UnicodeData.txt"), encoding: .utf8)
var names: [UInt32: String] = [:]
for line in records.split(separator: "\n") {
    let fields = line.split(separator: ";", omittingEmptySubsequences: false)
    let cp = UInt32(fields[0], radix: 16)!
    if !["Cc", "Cf", "Cs"].contains(String(fields[2])) && blocks.contains(where: { cp >= ($0[2] as! NSNumber).uint32Value && cp <= ($0[3] as! NSNumber).uint32Value }) {
        names[cp] = String(fields[1])
    }
}
let variations = try String(contentsOf: unicodeDirectory.appendingPathComponent("emoji-variation-sequences.txt"), encoding: .utf8)
var emoji: Set<UInt32> = []
for line in variations.split(separator: "\n") {
    let fields = line.split(whereSeparator: { $0 == " " || $0 == ";" })
    if fields.count > 1 && fields[1] == "FE0F", let cp = UInt32(fields[0], radix: 16), cp >= 128 { emoji.insert(cp) }
}
precondition(names.count == config["assigned_printable"] as! Int)
precondition(Set(names.keys).intersection(emoji).count == config["non_ascii_emoji_bases"] as! Int)
guard CommandLine.arguments.count > 1 else {
    print("Usage: swift script_helper/check_macos_symbols.swift FONT.otf [FONT.ttf ...]")
    exit(2)
}
var failed = false
for argument in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: argument)
    var registrationError: Unmanaged<CFError>?
    guard CTFontManagerRegisterFontsForURL(url as CFURL, .process, &registrationError) else {
        fatalError("Cannot register \(argument): \(String(describing: registrationError))")
    }
    let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as! [CTFontDescriptor]
    let font = CTFontCreateWithFontDescriptor(descriptors[0], 13, nil)
    for presentation in ["native", "text", "emoji"] {
        var missing: [String] = []
        for cp in names.keys.sorted() {
            var text = String(UnicodeScalar(cp)!)
            if emoji.contains(cp) && presentation != "native" { text += presentation == "emoji" ? "\u{FE0F}" : "\u{FE0E}" }
            let attributed = NSAttributedString(string: text, attributes: [NSAttributedString.Key(kCTFontAttributeName as String): font])
            let line = CTLineCreateWithAttributedString(attributed)
            let runs = CTLineGetGlyphRuns(line) as! [CTRun]
            let missingRuns = runs.filter { run in
                let attributes = CTRunGetAttributes(run) as NSDictionary
                let used = attributes[kCTFontAttributeName] as! CTFont
                var glyphs = [CGGlyph](repeating: 0, count: CTRunGetGlyphCount(run))
                CTRunGetGlyphs(run, CFRange(location: 0, length: 0), &glyphs)
                return (CTFontCopyPostScriptName(used) as String).contains("LastResort") || glyphs.first == 0
            }
            if runs.isEmpty || !missingRuns.isEmpty { missing.append(String(format: "U+%05X %@", cp, names[cp]!)) }
        }
        print("\(CTFontCopyPostScriptName(font)) | Unicode \(version) | \(presentation): \(names.count) symbols, \(missing.count) missing | \(ProcessInfo.processInfo.operatingSystemVersionString)")
        if !missing.isEmpty { failed = true; print(missing.joined(separator: "\n")) }
    }
    CTFontManagerUnregisterFontsForURL(url as CFURL, .process, nil)
}
exit(failed ? 1 : 0)
