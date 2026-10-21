import Foundation
import CoreText
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import CryptoKit

let paths = Array(CommandLine.arguments.dropFirst())
if paths.isEmpty { fatalError("Supply tuned OTF font files") }
let sample = "minimum Toffee VVA VYA WYA ÁÉÅÜ ÇĽ gq07{}"
let size: CGFloat = 48
let width = 1500, height = paths.count * 210 + 70
let cs = CGColorSpaceCreateDeviceRGB()
let context = CGContext(data:nil,width:width,height:height,bitsPerComponent:8,bytesPerRow:width*4,space:cs,bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
context.setFillColor(CGColor(red:0.125,green:0.12,blue:0.15,alpha:1));context.fill(CGRect(x:0,y:0,width:width,height:height))
var reports: [[String:Any]] = []
for (index,path) in paths.enumerated() {
    let url = URL(fileURLWithPath:path), data = try Data(contentsOf:url)
    let cg = CGFont(CGDataProvider(data:data as CFData)!)!
    let font = CTFontCreateWithGraphicsFont(cg,size,nil,nil)
    var modes: [[String:Any]] = []
    for (row,enabled) in [true,false].enumerated() {
        var attrs: [NSAttributedString.Key:Any] = [NSAttributedString.Key(kCTFontAttributeName as String):font,NSAttributedString.Key(kCTForegroundColorAttributeName as String):CGColor(red:0.93,green:0.92,blue:0.96,alpha:1)]
        if !enabled { attrs[NSAttributedString.Key(kCTKernAttributeName as String)] = 0 }
        let line = CTLineCreateWithAttributedString(NSAttributedString(string:sample,attributes:attrs))
        var advances: [Double] = [], positions: [Double] = [], actualNames: [String] = []
        for run in CTLineGetGlyphRuns(line) as! [CTRun] {
            let count = CTRunGetGlyphCount(run)
            var a = [CGSize](repeating:.zero,count:count), p = [CGPoint](repeating:.zero,count:count)
            CTRunGetAdvances(run,CFRange(location:0,length:0),&a);CTRunGetPositions(run,CFRange(location:0,length:0),&p)
            advances += a.map{Double($0.width / size * 1024)}
            positions += p.map{Double($0.x / size * 1024)}
            let attributes = CTRunGetAttributes(run) as NSDictionary
            actualNames.append(CTFontCopyPostScriptName(attributes[kCTFontAttributeName] as! CTFont) as String)
        }
        let expected = 575 * Double(advances.count)
        let total = CTLineGetTypographicBounds(line,nil,nil,nil) / Double(size) * 1024
        guard abs(total-expected)<0.01 else {fatalError("Advance sum changed: \(path), \(enabled): \(total)")}
        let shifts = positions.enumerated().map{ $0.element - Double($0.offset)*575 }
        if !enabled && shifts.contains(where:{abs($0)>0.01}) {fatalError("Strict CoreText placement changed")}
        let y = CGFloat(height-index*210-row*65-100)
        context.setStrokeColor(CGColor(red:0.3,green:0.3,blue:0.36,alpha:1));context.setLineWidth(0.5)
        for n in 0...sample.count {let x=28+CGFloat(n)*575/1024*size;context.move(to:CGPoint(x:x,y:y-16));context.addLine(to:CGPoint(x:x,y:y+45))};context.strokePath()
        context.textPosition = CGPoint(x:28,y:y);CTLineDraw(line,context)
        modes.append(["kern_default":enabled,"positions_font_units":positions,"shifts_font_units":shifts,"run_advance_widths_font_units":advances,"total_font_units":total,"actual_fonts":actualNames])
    }
    reports.append(["file":url.lastPathComponent,"sha256":SHA256.hash(data:data).map{String(format:"%02x",$0)}.joined(),"postscript_name":CTFontCopyPostScriptName(font),"ascent_font_units":CTFontGetAscent(font)/size*1024,"descent_font_units":CTFontGetDescent(font)/size*1024,"modes":modes])
    let label = NSAttributedString(string:url.lastPathComponent,attributes:[NSAttributedString.Key(kCTFontAttributeName as String):CTFontCreateWithName("Helvetica" as CFString,16,nil),NSAttributedString.Key(kCTForegroundColorAttributeName as String):CGColor(red:1,green:0.52,blue:1,alpha:1)])
    context.textPosition=CGPoint(x:28,y:height-index*210-40);CTLineDraw(CTLineCreateWithAttributedString(label),context)
}
let output = URL(fileURLWithPath:".font-build/tuned-coretext-proof.png")
let destination = CGImageDestinationCreateWithURL(output as CFURL,UTType.png.identifier as CFString,1,nil)!
CGImageDestinationAddImage(destination,context.makeImage()!,nil);guard CGImageDestinationFinalize(destination)else{fatalError("PNG failed")}
let result:[String:Any] = ["platform":ProcessInfo.processInfo.operatingSystemVersionString,"sample":sample,"fonts":reports,"evidence":"CoreText process-local graphics fonts; no terminal UI or font installation"]
let bytes = try JSONSerialization.data(withJSONObject:result,options:[.prettyPrinted,.sortedKeys]);FileHandle.standardOutput.write(bytes)
