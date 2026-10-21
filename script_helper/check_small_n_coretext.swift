import Foundation
import CoreText
import CoreGraphics
import CryptoKit

// Load each file directly into this process; no installation or font fallback.
let paths = Array(CommandLine.arguments.dropFirst())
guard !paths.isEmpty else { fatalError("Supply generated OTF/TTF paths") }
var results: [[String: Any]] = []
for path in paths {
    let data = try Data(contentsOf: URL(fileURLWithPath: path))
    guard let provider = CGDataProvider(data: data as CFData), let graphicsFont = CGFont(provider) else {
        fatalError("Cannot load \(path)")
    }
    for size in [12.0, 20.0, 64.0, 128.0] {
        let font = CTFontCreateWithGraphicsFont(graphicsFont, size, nil, nil)
        for codepoint: UniChar in [0x207F, 0x2099] {
            var character = codepoint, glyph: CGGlyph = 0
            guard CTFontGetGlyphsForCharacters(font, &character, &glyph, 1), glyph != 0,
                  let outline = CTFontCreatePathForGlyph(font, glyph, nil), !outline.isEmpty else {
                fatalError("Missing/empty \(path) U+\(String(codepoint, radix: 16))")
            }
            var advance = CGSize.zero
            CTFontGetAdvancesForGlyphs(font, .horizontal, &glyph, &advance, 1)
            guard abs(advance.width - 575.0 * size / 1024.0) < 0.0001 else { fatalError("Advance changed") }
            let context = CGContext(data: nil, width: 256, height: 256, bitsPerComponent: 8,
                                    bytesPerRow: 256, space: CGColorSpaceCreateDeviceGray(), bitmapInfo: 0)!
            context.setFillColor(gray: 1, alpha: 1)
            var point = CGPoint(x: 32, y: 64)
            CTFontDrawGlyphs(font, &glyph, &point, 1, context)
            let pixels = context.data!.assumingMemoryBound(to: UInt8.self)
            let ink = (0..<(256 * 256)).reduce(0) { $0 + (pixels[$1] > 0 ? 1 : 0) }
            guard ink > 0 else { fatalError("Blank raster \(path) U+\(String(codepoint, radix: 16))") }
            results.append(["file": URL(fileURLWithPath: path).lastPathComponent,
                            "sha256": SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined(),
                            "codepoint": String(format: "U+%04X", codepoint), "size": size,
                            "ink_pixels": ink, "advance": advance.width,
                            "actual_font": CTFontCopyPostScriptName(font)])
        }
    }
}
let output: [String: Any] = ["platform": ProcessInfo.processInfo.operatingSystemVersionString,
                           "checks": results.count, "results": results]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: output, options: [.prettyPrinted, .sortedKeys]))
