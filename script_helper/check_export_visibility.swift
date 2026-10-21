import Foundation
import CoreText
import CoreGraphics

// Compare native bitmap ink at 64 px, including all mapped scalars. In particular,
// a successful glyph lookup or rasterizer call with zero pixels is not a pass.
func load(_ path: String) throws -> CTFont {
    let data = try Data(contentsOf: URL(fileURLWithPath: path))
    guard let provider = CGDataProvider(data: data as CFData), let cg = CGFont(provider) else { fatalError("Load failed: \(path)") }
    return CTFontCreateWithGraphicsFont(cg, 64, nil, nil)
}
func hasInk(_ font: CTFont, _ scalar: Unicode.Scalar) -> Bool {
    let chars = Array(String(scalar).utf16)
    var glyphs = [CGGlyph](repeating: 0, count: chars.count)
    guard CTFontGetGlyphsForCharacters(font, chars, &glyphs, chars.count), let glyph = glyphs.first, glyph != 0 else { return false }
    var g = glyph
    let bounds = CTFontGetBoundingRectsForGlyphs(font, .horizontal, &g, nil, 1)
    if bounds.isEmpty { return false }
    let width = max(1, Int(ceil(bounds.width)) + 6), height = max(1, Int(ceil(bounds.height)) + 6)
    guard let context = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8,
                                  bytesPerRow: width, space: CGColorSpaceCreateDeviceGray(), bitmapInfo: 0) else { fatalError("Bitmap allocation failed") }
    context.setFillColor(gray: 1, alpha: 1)
    var origin = CGPoint(x: 3 - bounds.minX, y: 3 - bounds.minY)
    CTFontDrawGlyphs(font, &g, &origin, 1, context)
    let pixels = context.data!.assumingMemoryBound(to: UInt8.self)
    for i in 0..<(width * height) { if pixels[i] > 0 { return true } }
    return false
}
let paths = Array(CommandLine.arguments.dropFirst())
guard !paths.isEmpty else { fatalError("Supply generated TTF paths with corresponding OTF files") }
var results: [[String: Any]] = []
for path in paths {
    let sourcePath = String(path.dropLast(4)).replacingOccurrences(of: "-hinted", with: "") + ".otf"
    let source = try load(sourcePath), target = try load(path)
    let chars = CTFontCopyCharacterSet(source) as CharacterSet
    var visible = 0, checked = 0
    for range in 0...16 where CFCharacterSetHasMemberInPlane(chars as CFCharacterSet, CFIndex(range)) {
        for cp in (range * 65536)..<((range + 1) * 65536) {
            guard let scalar = Unicode.Scalar(cp), chars.contains(scalar) else { continue }
            checked += 1
            if hasInk(source, scalar) {
                visible += 1
                if !hasInk(target, scalar) { fatalError("Lost visible glyph \(path) U+\(String(cp, radix: 16))") }
            }
        }
    }
    results.append(["file": URL(fileURLWithPath: path).lastPathComponent, "mapped": checked, "otf_visible": visible, "lost": 0])
}
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: ["platform": ProcessInfo.processInfo.operatingSystemVersionString, "size": 64, "results": results], options: [.prettyPrinted, .sortedKeys]))
