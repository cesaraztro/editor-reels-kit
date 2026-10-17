// Cara de la persona cada 0.1 s con Apple Vision (encuentra caras pequeñas en planos abiertos).
//   caras <entrada.mp4> <salida.json>
// Salida: {"fps":10,"cuadros":[[t, cx, cy, ancho, alto], ...]} normalizado 0–1, origen arriba-izquierda (null si no hay cara).
import AVFoundation
import Foundation
import Vision

func salir(_ m: String) -> Never { FileHandle.standardError.write((m + "\n").data(using: .utf8)!); exit(1) }
let args = CommandLine.arguments
guard args.count >= 3 else { salir("uso: caras <entrada.mp4> <salida.json>") }
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let sem = DispatchSemaphore(value: 0)
var pista: AVAssetTrack?
Task { pista = try? await asset.loadTracks(withMediaType: .video).first; sem.signal() }
sem.wait()
guard let pista, let lector = try? AVAssetReader(asset: asset) else { salir("sin video") }
let out = AVAssetReaderTrackOutput(track: pista, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
out.alwaysCopiesSampleData = false
lector.add(out)
lector.startReading()
var filas: [[Any]] = []
var siguiente = 0.0
let t0 = Date()
while let m = out.copyNextSampleBuffer() {
    let t = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(m))
    if t + 0.001 < siguiente { continue }
    siguiente = (t * 10).rounded(.down) / 10 + 0.1
    guard let img = CMSampleBufferGetImageBuffer(m) else { continue }
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cvPixelBuffer: img).perform([req])
    let tt = (t * 10).rounded() / 10
    if let f = (req.results ?? []).max(by: { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height }) {
        let b = f.boundingBox  // origen abajo-izquierda en Vision
        filas.append([tt, Double(b.midX), Double(1 - b.midY), Double(b.width), Double(b.height)])
    } else {
        filas.append([tt, NSNull(), NSNull(), NSNull(), NSNull()])
    }
}
let json = try! JSONSerialization.data(withJSONObject: ["fps": 10, "cuadros": filas])
try! json.write(to: URL(fileURLWithPath: args[2]))
let con = filas.filter { !($0[1] is NSNull) }.count
print(String(format: "caras: %d muestras (%d con cara) en %.1fs", filas.count, con, Date().timeIntervalSince(t0)))
