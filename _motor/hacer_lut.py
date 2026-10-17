#!/usr/bin/env python3
"""Genera el LUT 'premium': contraste suave en S, calidez ligera, sombras un poco frías, saturación de piel cuidada.
  python3 hacer_lut.py [salida.cube]"""
import sys
from pathlib import Path
N = 33
out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent / "04-recursos/lut/premium.cube")

def curva(x, k=0.12):  # S suave alrededor de 0.5
    return x + k * (x - 0.5) * (1 - abs(2 * x - 1))

lineas = [f"TITLE \"Premium\"", f"LUT_3D_SIZE {N}"]
for b in range(N):
    for g in range(N):
        for r in range(N):
            R, G, B = r / (N - 1), g / (N - 1), b / (N - 1)
            R, G, B = curva(R), curva(G), curva(B)
            l = 0.2126 * R + 0.7152 * G + 0.0722 * B
            s = 1.04  # saturación
            R, G, B = l + (R - l) * s, l + (G - l) * s, l + (B - l) * s
            # altas cálidas, sombras ligeramente frías
            R += 0.018 * l - 0.006 * (1 - l)
            B += -0.022 * l + 0.010 * (1 - l)
            R, G, B = (min(1, max(0, v)) ** 1.02 for v in (R, G, B))  # gamma un poco más densa
            lineas.append(f"{R:.5f} {G:.5f} {B:.5f}")
out.write_text("\n".join(lineas) + "\n")
print(out)
