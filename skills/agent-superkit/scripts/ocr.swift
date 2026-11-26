import Foundation
import ImageIO
import Vision

struct Region: Encodable {
    let text: String
    let confidence: Float
    let left: Double
    let top: Double
    let width: Double
    let height: Double
}

struct Result: Encodable {
    let engine = "macOS Vision"
    let coordinateOrigin = "top-left-normalized"
    let languages: [String]
    let lines: [Region]
}

func fail(_ message: String, code: Int32) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(code)
}

let arguments = Array(CommandLine.arguments.dropFirst())
guard arguments.count == 1 || arguments.count == 3 && arguments[1] == "--languages" else {
    fail("Usage: local-image-ocr IMAGE [--languages zh-Hans,en-US]", code: 64)
}

let url = URL(fileURLWithPath: arguments[0]).standardizedFileURL
let requested = arguments.count == 3 ? arguments[2].split(separator: ",", omittingEmptySubsequences: false).map(String.init) : ["zh-Hans", "en-US"]

do {
    let properties = try url.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
    guard properties.isRegularFile == true, let size = properties.fileSize, (1...30_000_000).contains(size),
          let input = CGImageSourceCreateWithURL(url as CFURL, [kCGImageSourceShouldCache: false] as CFDictionary),
          CGImageSourceGetCount(input) == 1,
          let metadata = CGImageSourceCopyPropertiesAtIndex(input, 0, nil) as? [CFString: Any],
          let width = (metadata[kCGImagePropertyPixelWidth] as? NSNumber)?.doubleValue,
          let height = (metadata[kCGImagePropertyPixelHeight] as? NSNumber)?.doubleValue,
          width > 0, height > 0, width * height <= 60_000_000,
          let image = CGImageSourceCreateImageAtIndex(input, 0, nil) else {
        fail("Expected one readable image under 30 MB and 60 megapixels.", code: 66)
    }
    let orientationCode = (metadata[kCGImagePropertyOrientation] as? NSNumber)?.uint32Value ?? 1
    let orientation = CGImagePropertyOrientation(rawValue: orientationCode) ?? .up
    let recognition = VNRecognizeTextRequest()
    recognition.recognitionLevel = .accurate
    let supported = Set(try recognition.supportedRecognitionLanguages())
    guard !requested.isEmpty, Set(requested).isSubset(of: supported) else {
        fail("Requested OCR language is unavailable in this macOS Vision version.", code: 64)
    }
    recognition.recognitionLanguages = requested
    recognition.usesLanguageCorrection = false
    let handler = VNImageRequestHandler(cgImage: image, orientation: orientation, options: [:])
    try handler.perform([recognition])
    let lines = (recognition.results ?? []).compactMap { hit -> Region? in
        guard let candidate = hit.topCandidates(1).first else { return nil }
        let box = hit.boundingBox
        return Region(text: candidate.string, confidence: candidate.confidence, left: box.minX,
                      top: 1 - box.maxY, width: box.width, height: box.height)
    }
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys, .prettyPrinted]
    let encoded = try encoder.encode(Result(languages: requested, lines: lines))
    FileHandle.standardOutput.write(encoded + Data("\n".utf8))
} catch {
    fail("Could not recognize text from the supplied local image.", code: 65)
}
