// Máscara de la persona cuadro por cuadro con Apple Vision (chip neuronal del M5).
//   matte <entrada.mp4> <salida.mp4> [--objetos] [--suavizado 0.6]
// Salida: H.264 del mismo tamaño, fps y número de cuadros que la entrada; gris = opacidad de la persona.
// --objetos une la máscara de "objetos en primer plano" (micrófono en la mano, silla) a la de la persona.
import AVFoundation
import CoreImage
import Foundation
import Vision

func salir(_ m: String) -> Never { FileHandle.standardError.write((m + "\n").data(using: .utf8)!); exit(1) }

let args = CommandLine.arguments
guard args.count >= 3 else { salir("uso: matte <entrada.mp4> <salida.mp4> [--objetos] [--suavizado 0.6]") }
let entrada = URL(fileURLWithPath: args[1]), salida = URL(fileURLWithPath: args[2])
let objetos = args.contains("--objetos")
var alfa: Float = 0.6
if let i = args.firstIndex(of: "--suavizado"), i + 1 < args.count, let v = Float(args[i + 1]) { alfa = v }
// --rangos "a-b,c-d" (segundos): solo esos tramos pasan por Vision; el resto se escribe en negro (rápido)
var rangos: [(Double, Double)] = []
if let i = args.firstIndex(of: "--rangos"), i + 1 < args.count {
    for r in args[i + 1].split(separator: ",") {
        let ab = r.split(separator: "-").compactMap { Double($0) }
        if ab.count == 2 { rangos.append((ab[0], ab[1])) }
    }
}

let asset = AVURLAsset(url: entrada)
let sem = DispatchSemaphore(value: 0)
var pista: AVAssetTrack?
var fps: Float = 30
var tam = CGSize(width: 1080, height: 1920)
Task {
    pista = try? await asset.loadTracks(withMediaType: .video).first
    if let p = pista {
        fps = (try? await p.load(.nominalFrameRate)) ?? 30
        tam = (try? await p.load(.naturalSize)) ?? tam
    }
    sem.signal()
}
sem.wait()
guard let pista else { salir("sin pista de video") }
let W = Int(tam.width), H = Int(tam.height)

guard let lector = try? AVAssetReader(asset: asset) else { salir("no se pudo leer") }
let salidaLector = AVAssetReaderTrackOutput(track: pista, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
salidaLector.alwaysCopiesSampleData = false
lector.add(salidaLector)

try? FileManager.default.removeItem(at: salida)
guard let escritor = try? AVAssetWriter(outputURL: salida, fileType: .mp4) else { salir("no se pudo escribir") }
let entradaEsc = AVAssetWriterInput(mediaType: .video, outputSettings: [
    AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: W, AVVideoHeightKey: H,
    AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 12_000_000, AVVideoMaxKeyFrameIntervalKey: 30]])
entradaEsc.expectsMediaDataInRealTime = false
let adaptador = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: entradaEsc, sourcePixelBufferAttributes: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
    kCVPixelBufferWidthKey as String: W, kCVPixelBufferHeightKey as String: H])
escritor.add(entradaEsc)
lector.startReading()
escritor.startWriting()
escritor.startSession(atSourceTime: .zero)

let ctx = CIContext(options: [.workingColorSpace: NSNull(), .outputColorSpace: NSNull()])
let secuencia = VNSequenceRequestHandler()
let persona = VNGeneratePersonSegmentationRequest()
persona.qualityLevel = .accurate
persona.outputPixelFormat = kCVPixelFormatType_OneComponent8

var previo: [Float] = []
var pw = 0, ph = 0
var n = 0, nv = 0
let t0 = Date()
var negro: CVPixelBuffer?

while let muestra = salidaLector.copyNextSampleBuffer() {
    guard let img = CMSampleBufferGetImageBuffer(muestra) else { continue }
    let pts = CMSampleBufferGetPresentationTimeStamp(muestra)
    let ts = CMTimeGetSeconds(pts)
    if !rangos.isEmpty && !rangos.contains(where: { ts >= $0.0 && ts <= $0.1 }) {
        if negro == nil {
            CVPixelBufferPoolCreatePixelBuffer(nil, adaptador.pixelBufferPool!, &negro)
            ctx.render(CIImage(color: .black).cropped(to: CGRect(x: 0, y: 0, width: W, height: H)), to: negro!)
        }
        previo = []
        while !entradaEsc.isReadyForMoreMediaData { usleep(1000) }
        adaptador.append(negro!, withPresentationTime: pts)
        n += 1
        continue
    }
    nv += 1
    do { try secuencia.perform([persona], on: img) } catch { salir("Vision: \(error)") }
    guard let m = persona.results?.first?.pixelBuffer else { salir("sin máscara") }
    CVPixelBufferLockBaseAddress(m, .readOnly)
    let mw = CVPixelBufferGetWidth(m), mh = CVPixelBufferGetHeight(m), fila = CVPixelBufferGetBytesPerRow(m)
    let base = CVPixelBufferGetBaseAddress(m)!.assumingMemoryBound(to: UInt8.self)
    if previo.count != mw * mh { previo = [Float](repeating: -1, count: mw * mh); pw = mw; ph = mh }
    // suavizado temporal adaptativo: quieto → se promedia (sin parpadeo); en movimiento → valor nuevo (sin rastro)
    var plano = [UInt8](repeating: 0, count: mw * mh)
    plano.withUnsafeMutableBufferPointer { out in
        previo.withUnsafeMutableBufferPointer { pr in
            for y in 0..<mh {
                let filaPtr = base + y * fila
                let o = y * mw
                for x in 0..<mw {
                    let v = Float(filaPtr[x])
                    let i = o + x
                    let p = pr[i]
                    let e = (p < 0 || abs(v - p) > 48) ? v : p + (v - p) * alfa
                    pr[i] = e
                    out[i] = UInt8(e)
                }
            }
        }
    }
    CVPixelBufferUnlockBaseAddress(m, .readOnly)
    var masc = CIImage(bitmapData: Data(plano), bytesPerRow: mw, size: CGSize(width: mw, height: mh),
                       format: .L8, colorSpace: nil)
    if objetos {
        let req = VNGenerateForegroundInstanceMaskRequest()
        let h = VNImageRequestHandler(cvPixelBuffer: img)
        if (try? h.perform([req])) != nil, let r = req.results?.first,
           let fb = try? r.generateScaledMaskForImage(forInstances: r.allInstances, from: h) {
            let fo = CIImage(cvPixelBuffer: fb)
            let esc = CGAffineTransform(scaleX: CGFloat(mw) / fo.extent.width, y: CGFloat(mh) / fo.extent.height)
            masc = masc.applyingFilter("CIMaximumCompositing", parameters: [kCIInputBackgroundImageKey: fo.transformed(by: esc)])
        }
    }
    // escalar a tamaño completo con Lanczos y escribir en gris (B=G=R)
    let escala = masc.applyingFilter("CILanczosScaleTransform", parameters: [
        kCIInputScaleKey: CGFloat(H) / CGFloat(mh), kCIInputAspectRatioKey: (CGFloat(W) / CGFloat(mw)) / (CGFloat(H) / CGFloat(mh))])
        .cropped(to: CGRect(x: 0, y: 0, width: W, height: H))
    while !entradaEsc.isReadyForMoreMediaData { usleep(1000) }
    var pb: CVPixelBuffer?
    CVPixelBufferPoolCreatePixelBuffer(nil, adaptador.pixelBufferPool!, &pb)
    guard let pb else { salir("sin buffer") }
    ctx.render(escala, to: pb, bounds: CGRect(x: 0, y: 0, width: W, height: H), colorSpace: nil)
    adaptador.append(pb, withPresentationTime: pts)
    n += 1
}
entradaEsc.markAsFinished()
let fin = DispatchSemaphore(value: 0)
escritor.finishWriting { fin.signal() }
fin.wait()
if lector.status == .failed { salir("lectura falló: \(String(describing: lector.error))") }
let s = Date().timeIntervalSince(t0)
print(String(format: "matte: %d cuadros (%d con Vision) en %.1fs · máscara %dx%d · objetos %@", n, nv, s, pw, ph, objetos ? "sí" : "no"))
