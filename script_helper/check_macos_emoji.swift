// Process-local CoreText shaping evidence; does not install fonts or alter apps.
// swift script_helper/check_macos_emoji.swift CASES.json FONT.otf [FONT.otf ...]
import Foundation
import CoreText
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

guard CommandLine.arguments.count > 2 else { fatalError("Supply cases JSON and font paths") }
let casesURL = URL(fileURLWithPath: CommandLine.arguments[1])
let cases = try JSONSerialization.jsonObject(with: Data(contentsOf: casesURL)) as! [[String: Any]]
var results: [[String: Any]] = []
var fontArguments = Array(CommandLine.arguments.dropFirst(2))
var previewDirectory: URL?
if let index = fontArguments.firstIndex(of: "--preview-dir") {
    precondition(index + 1 < fontArguments.count)
    previewDirectory = URL(fileURLWithPath: fontArguments[index + 1])
    try FileManager.default.createDirectory(at: previewDirectory!, withIntermediateDirectories: true)
    fontArguments.removeSubrange(index...(index+1))
}
func inspect(_ font: CTFont, _ source: String) {
    let width = 1100, height = cases.count * 48 + 60
    let context = CGContext(data:nil,width:width,height:height,bitsPerComponent:8,bytesPerRow:width*4,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
    context.setFillColor(CGColor(gray:1,alpha:1)); context.fill(CGRect(x:0,y:0,width:width,height:height))
    let labelFont = CTFontCreateWithName("Menlo" as CFString, 11, nil)
    for (index, probe) in cases.enumerated() {
        let text = probe["text"] as! String
        let attributed = NSAttributedString(string: text, attributes: [NSAttributedString.Key(kCTFontAttributeName as String):font])
        let line = CTLineCreateWithAttributedString(attributed)
        let runs = CTLineGetGlyphRuns(line) as! [CTRun]
        var used: [[String: Any]] = []
        for run in runs {
            let attrs = CTRunGetAttributes(run) as NSDictionary
            let actual = attrs[kCTFontAttributeName] as! CTFont
            let count = CTRunGetGlyphCount(run)
            var glyphs = [CGGlyph](repeating: 0, count: count)
            CTRunGetGlyphs(run,CFRange(location:0,length:0),&glyphs)
            let range = CTRunGetStringRange(run)
            used.append(["font":CTFontCopyPostScriptName(actual) as String,"glyphs":glyphs.map {Int($0)},
                         "utf16_range":[range.location,range.length],"color_glyph_trait":CTFontGetSymbolicTraits(actual).contains(.traitColorGlyphs)])
        }
        let y = CGFloat(height - 48 * index - 40)
        func drawLabel(_ text: String, _ x: CGFloat) {
            let value = NSAttributedString(string:text,attributes:[NSAttributedString.Key(kCTFontAttributeName as String):labelFont, NSAttributedString.Key(kCTForegroundColorAttributeName as String):CGColor(gray:0,alpha:1)])
            context.textPosition = CGPoint(x:x,y:y); CTLineDraw(CTLineCreateWithAttributedString(value),context)
        }
        drawLabel((probe["label"] as! String), 20)
        context.textPosition = CGPoint(x:260,y:y); CTLineDraw(line,context)
        drawLabel(used.map { $0["font"] as! String }.joined(separator:", "), 430)
        results.append(["requested_font":CTFontCopyPostScriptName(font) as String,"source":source,"probe":probe,"runs":used])
    }
    if let directory = previewDirectory, let image = context.makeImage() {
        let path = directory.appendingPathComponent((CTFontCopyPostScriptName(font) as String) + ".png")
        let destination = CGImageDestinationCreateWithURL(path as CFURL, UTType.png.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(destination,image,nil)
        precondition(CGImageDestinationFinalize(destination))
    }
}
inspect(CTFontCreateWithName("Menlo" as CFString,20,nil),"system baseline")
for argument in fontArguments {
    let url = URL(fileURLWithPath:argument)
    var error: Unmanaged<CFError>?
    guard CTFontManagerRegisterFontsForURL(url as CFURL,.process,&error) else { fatalError("Font registration failed: \(String(describing:error))") }
    let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as! [CTFontDescriptor]
    inspect(CTFontCreateWithFontDescriptor(descriptors[0],20,nil),argument)
    CTFontManagerUnregisterFontsForURL(url as CFURL,.process,nil)
}
let report: [String:Any] = ["platform":ProcessInfo.processInfo.operatingSystemVersionString,"engine":"CoreText CTLine, explicit font, process-only registration","results":results]
let data = try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys])
FileHandle.standardOutput.write(data)
