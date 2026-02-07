"""Generate simple PNG icons for the PWA from scratch (no Pillow needed)."""

import struct
import zlib


def create_png(width, height, bg_color, text_lines):
    """Create a minimal PNG with colored background and text-like pattern."""
    # We'll draw a simple globe/world icon with colored blocks

    def pixel(r, g, b):
        return bytes([r, g, b, 255])

    bg = pixel(*bg_color)
    accent = pixel(79, 195, 247)  # #4fc3f7
    white = pixel(255, 255, 255)
    dark = pixel(15, 25, 35)

    # Build pixel rows
    raw = bytearray()
    cx, cy = width // 2, height // 2
    radius = int(width * 0.35)
    inner = int(width * 0.32)

    for y in range(height):
        raw.append(0)  # filter byte: none
        for x in range(width):
            dx = x - cx
            dy = y - cy
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < inner:
                # Inside globe: draw grid lines
                # Latitude lines
                lat_line = abs(dy) % (radius // 4) < 2
                # Longitude lines (curved)
                angle_step = radius // 5
                lon_line = abs(dx) % angle_step < 2

                if lat_line or lon_line:
                    raw.extend(accent)
                else:
                    raw.extend(dark)
            elif dist < radius:
                # Globe edge
                raw.extend(accent)
            else:
                raw.extend(bg)

    # Encode as PNG
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + chunk + crc

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    compressed = zlib.compress(bytes(raw), 9)

    png = header
    png += make_chunk(b'IHDR', ihdr)
    png += make_chunk(b'IDAT', compressed)
    png += make_chunk(b'IEND', b'')
    return png


if __name__ == '__main__':
    bg = (15, 25, 35)  # --bg color

    for size in [192, 512]:
        data = create_png(size, size, bg, [])
        path = f'static/icon-{size}.png'
        with open(path, 'wb') as f:
            f.write(data)
        print(f'Generated {path} ({len(data)} bytes)')

    # Also generate apple-touch-icon (180x180)
    data = create_png(180, 180, bg, [])
    path = 'static/apple-touch-icon.png'
    with open(path, 'wb') as f:
        f.write(data)
    print(f'Generated {path} ({len(data)} bytes)')
