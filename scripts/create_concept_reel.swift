import AppKit
import AVFoundation
import CoreVideo

// A compact, self-contained motion-graphics reel for presenting the tactile-board idea.
let outputPath = CommandLine.arguments.dropFirst().first
    ?? "data/outputs/soccer-to-football-magnetic-board-concept-001.mp4"
let width = 1280
let height = 720
let frameRate = 30
let duration = 8.0

func color(_ red: CGFloat, _ green: CGFloat, _ blue: CGFloat, _ alpha: CGFloat = 1) -> NSColor {
    NSColor(red: red / 255, green: green / 255, blue: blue / 255, alpha: alpha)
}

func fill(_ context: CGContext, _ rect: CGRect, _ shade: NSColor, radius: CGFloat = 0) {
    context.setFillColor(shade.cgColor)
    if radius > 0 { context.addPath(CGPath(roundedRect: rect, cornerWidth: radius, cornerHeight: radius, transform: nil)) }
    else { context.addRect(rect) }
    context.fillPath()
}

func stroke(_ context: CGContext, _ rect: CGRect, _ shade: NSColor, width: CGFloat = 2, radius: CGFloat = 0) {
    context.setStrokeColor(shade.cgColor)
    context.setLineWidth(width)
    if radius > 0 { context.addPath(CGPath(roundedRect: rect, cornerWidth: radius, cornerHeight: radius, transform: nil)) }
    else { context.addRect(rect) }
    context.strokePath()
}

func label(_ text: String, at point: CGPoint, size: CGFloat, shade: NSColor, weight: NSFont.Weight = .bold, alignment: NSTextAlignment = .left) {
    let style = NSMutableParagraphStyle()
    style.alignment = alignment
    let attrs: [NSAttributedString.Key: Any] = [
        .font: NSFont.systemFont(ofSize: size, weight: weight),
        .foregroundColor: shade,
        .paragraphStyle: style,
    ]
    let rect = CGRect(x: point.x, y: point.y, width: 850, height: size * 1.6)
    (text as NSString).draw(in: rect, withAttributes: attrs)
}

func ease(_ value: CGFloat) -> CGFloat {
    let t = min(1, max(0, value))
    return t * t * (3 - 2 * t)
}

func drawSoccerBall(_ context: CGContext, center: CGPoint, radius: CGFloat) {
    context.setFillColor(NSColor.white.cgColor)
    context.fillEllipse(in: CGRect(x: center.x - radius, y: center.y - radius, width: radius * 2, height: radius * 2))
    context.setStrokeColor(color(18, 27, 48).cgColor)
    context.setLineWidth(2)
    context.strokeEllipse(in: CGRect(x: center.x - radius, y: center.y - radius, width: radius * 2, height: radius * 2))
    context.setFillColor(color(18, 27, 48).cgColor)
    context.fillEllipse(in: CGRect(x: center.x - radius * 0.32, y: center.y - radius * 0.28, width: radius * 0.64, height: radius * 0.56))
    for angle in stride(from: 0.0, through: 288.0, by: 72.0) {
        let a = CGFloat(angle * .pi / 180)
        let p = CGPoint(x: center.x + cos(a) * radius * 0.62, y: center.y + sin(a) * radius * 0.62)
        context.fillEllipse(in: CGRect(x: p.x - radius * 0.12, y: p.y - radius * 0.12, width: radius * 0.24, height: radius * 0.24))
    }
}

func drawFootball(_ context: CGContext, center: CGPoint, scale: CGFloat, rotation: CGFloat = 0) {
    context.saveGState()
    context.translateBy(x: center.x, y: center.y)
    context.rotate(by: rotation)
    let w = 132 * scale, h = 76 * scale
    let body = CGPath(roundedRect: CGRect(x: -w / 2, y: -h / 2, width: w, height: h), cornerWidth: h / 2, cornerHeight: h / 2, transform: nil)
    context.setFillColor(color(143, 67, 38).cgColor); context.addPath(body); context.fillPath()
    context.setStrokeColor(color(255, 194, 137).cgColor); context.setLineWidth(3 * scale); context.addPath(body); context.strokePath()
    context.setStrokeColor(NSColor.white.cgColor); context.setLineWidth(3 * scale)
    context.move(to: CGPoint(x: -w * 0.15, y: 0)); context.addLine(to: CGPoint(x: w * 0.18, y: 0)); context.strokePath()
    for x in stride(from: -w * 0.06, through: w * 0.12, by: w * 0.06) {
        context.move(to: CGPoint(x: x, y: -h * 0.12)); context.addLine(to: CGPoint(x: x, y: h * 0.12)); context.strokePath()
    }
    context.restoreGState()
}

func drawMagnet(_ context: CGContext, center: CGPoint, scale: CGFloat) {
    context.saveGState(); context.translateBy(x: center.x, y: center.y); context.scaleBy(x: scale, y: scale)
    context.setLineWidth(14); context.setLineCap(.round)
    context.setStrokeColor(color(255, 91, 91).cgColor)
    context.move(to: CGPoint(x: -18, y: 18)); context.addLine(to: CGPoint(x: -18, y: -10)); context.addCurve(to: CGPoint(x: 18, y: -10), control1: CGPoint(x: -18, y: -34), control2: CGPoint(x: 18, y: -34)); context.addLine(to: CGPoint(x: 18, y: 18)); context.strokePath()
    context.setStrokeColor(color(112, 220, 255).cgColor); context.setLineWidth(12)
    context.move(to: CGPoint(x: -18, y: 18)); context.addLine(to: CGPoint(x: -18, y: 5)); context.move(to: CGPoint(x: 18, y: 18)); context.addLine(to: CGPoint(x: 18, y: 5)); context.strokePath()
    context.restoreGState()
}

func drawBoard(_ context: CGContext, origin: CGPoint, snap: CGFloat) {
    let board = CGRect(x: origin.x, y: origin.y, width: 520, height: 400)
    fill(context, board, color(35, 47, 74), radius: 30); stroke(context, board, color(100, 219, 255), width: 4, radius: 30)
    label("TACTILE FIELD", at: CGPoint(x: origin.x + 30, y: origin.y + 352), size: 23, shade: color(207, 238, 255))
    label("4 × 5 vibration grid", at: CGPoint(x: origin.x + 30, y: origin.y + 324), size: 15, shade: color(163, 185, 210), weight: .medium)
    let cellW: CGFloat = 83, cellH: CGFloat = 55, gap: CGFloat = 10
    let startX = origin.x + 30, startY = origin.y + 64
    let activeRow = 1, activeCol = 3
    for row in 0..<4 {
        for col in 0..<5 {
            let isActive = row == activeRow && col == activeCol
            let rect = CGRect(x: startX + CGFloat(col) * (cellW + gap), y: startY + CGFloat(3 - row) * (cellH + gap), width: cellW, height: cellH)
            fill(context, rect, isActive ? color(255, 190, 62) : color(63, 79, 112), radius: 11)
            stroke(context, rect, isActive ? color(255, 235, 166) : color(112, 133, 168), width: isActive ? 3 : 1, radius: 11)
            if isActive { label("BALL", at: CGPoint(x: rect.minX + 12, y: rect.midY - 8), size: 13, shade: color(21, 32, 55), weight: .heavy) }
        }
    }
    let magnetLift = (1 - snap) * 35
    drawMagnet(context, center: CGPoint(x: origin.x - 2, y: origin.y + 344 + magnetLift), scale: 0.72)
    drawMagnet(context, center: CGPoint(x: origin.x + 522, y: origin.y + 344 + magnetLift), scale: 0.72)
    if snap > 0.5 {
        let pulse = sin(snap * 32) * 0.5 + 0.5
        context.setStrokeColor(color(255, 210, 76, 0.75 * pulse).cgColor); context.setLineWidth(5)
        context.move(to: CGPoint(x: origin.x - 54, y: origin.y + 338)); context.addLine(to: CGPoint(x: origin.x - 25, y: origin.y + 338)); context.strokePath()
        context.move(to: CGPoint(x: origin.x + 545, y: origin.y + 338)); context.addLine(to: CGPoint(x: origin.x + 574, y: origin.y + 338)); context.strokePath()
    }
}

func render(_ context: CGContext, time: CGFloat) {
    fill(context, CGRect(x: 0, y: 0, width: width, height: height), color(13, 20, 38))
    fill(context, CGRect(x: 0, y: 0, width: width, height: 10), color(100, 219, 255))
    label("FROM FIELD MOTION TO TOUCH", at: CGPoint(x: 64, y: 650), size: 40, shade: NSColor.white)
    label("Concept reel · prerecorded sport → one tactile location", at: CGPoint(x: 66, y: 612), size: 18, shade: color(169, 191, 217), weight: .medium)

    if time < 2.4 {
        label("SOCCER", at: CGPoint(x: 104, y: 516), size: 22, shade: color(207, 238, 255))
        let pitch = CGRect(x: 100, y: 178, width: 570, height: 290)
        fill(context, pitch, color(34, 130, 77), radius: 18); stroke(context, pitch, color(207, 238, 255, 0.7), width: 3, radius: 18)
        context.setStrokeColor(color(207, 238, 255, 0.7).cgColor); context.setLineWidth(3)
        context.move(to: CGPoint(x: pitch.midX, y: pitch.minY)); context.addLine(to: CGPoint(x: pitch.midX, y: pitch.maxY)); context.strokePath()
        context.strokeEllipse(in: CGRect(x: pitch.midX - 44, y: pitch.midY - 44, width: 88, height: 88))
        let p = ease(time / 2.35)
        let ballX = 485 - p * 650
        drawSoccerBall(context, center: CGPoint(x: ballX, y: 320), radius: 35)
        for i in 0..<3 { fill(context, CGRect(x: ballX + CGFloat(i + 1) * 52, y: 315, width: 26, height: 8), color(255, 255, 255, 0.18 - CGFloat(i) * 0.045), radius: 4) }
        label("ball leaves the soccer pitch", at: CGPoint(x: 105, y: 125), size: 22, shade: color(207, 238, 255), weight: .medium)
    } else {
        let footballProgress = ease((time - 2.25) / 2.5)
        label("AMERICAN FOOTBALL", at: CGPoint(x: 98, y: 516), size: 22, shade: color(255, 207, 159))
        fill(context, CGRect(x: 94, y: 232, width: 600, height: 170), color(54, 87, 62), radius: 85)
        for i in 0..<7 { fill(context, CGRect(x: 116 + CGFloat(i) * 82, y: 305, width: 45, height: 4), color(255, 255, 255, 0.38), radius: 2) }
        let ballX = -80 + footballProgress * 730
        drawFootball(context, center: CGPoint(x: ballX, y: 319), scale: 0.92, rotation: sin(time * 4) * 0.1)
        label("one ball position is mapped", at: CGPoint(x: 97, y: 178), size: 22, shade: color(207, 238, 255), weight: .medium)
    }

    let boardProgress = ease((time - 4.05) / 1.1)
    let boardX = 1320 - boardProgress * 680
    let snap = ease((time - 5.15) / 0.45)
    drawBoard(context, origin: CGPoint(x: boardX, y: 170), snap: snap)
    if time >= 4.2 { label(snap > 0.9 ? "MAGNETIC SNAP" : "BOARD ARRIVES", at: CGPoint(x: 766, y: 110), size: 24, shade: snap > 0.9 ? color(255, 210, 76) : color(169, 191, 217), alignment: .center) }
    if time > 5.6 { label("one active cell = where the ball is", at: CGPoint(x: 670, y: 70), size: 19, shade: color(207, 238, 255), weight: .medium, alignment: .center) }
}

let url = URL(fileURLWithPath: outputPath)
try? FileManager.default.removeItem(at: url)
try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
let settings: [String: Any] = [AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: width, AVVideoHeightKey: height]
let writer = try AVAssetWriter(outputURL: url, fileType: .mp4)
let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
let attributes: [String: Any] = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA, kCVPixelBufferWidthKey as String: width, kCVPixelBufferHeightKey as String: height]
let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: attributes)
writer.add(input); writer.startWriting(); writer.startSession(atSourceTime: .zero)
for frame in 0..<Int(duration * Double(frameRate)) {
    while !input.isReadyForMoreMediaData { RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.002)) }
    var buffer: CVPixelBuffer?
    CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &buffer)
    guard let pixelBuffer = buffer else { fatalError("Could not make a video frame") }
    CVPixelBufferLockBaseAddress(pixelBuffer, [])
    let bytes = CVPixelBufferGetBaseAddress(pixelBuffer)!
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    let cg = CGContext(data: bytes, width: width, height: height, bitsPerComponent: 8, bytesPerRow: CVPixelBufferGetBytesPerRow(pixelBuffer), space: colorSpace, bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue)!
    let graphics = NSGraphicsContext(cgContext: cg, flipped: false); NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = graphics
    render(cg, time: CGFloat(frame) / CGFloat(frameRate))
    NSGraphicsContext.restoreGraphicsState(); CVPixelBufferUnlockBaseAddress(pixelBuffer, [])
    adaptor.append(pixelBuffer, withPresentationTime: CMTime(value: CMTimeValue(frame), timescale: CMTimeScale(frameRate)))
}
input.markAsFinished()
writer.finishWriting { print("Saved \(url.path)") }
RunLoop.current.run(until: Date(timeIntervalSinceNow: 3))
