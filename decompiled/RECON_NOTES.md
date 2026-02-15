# Chromatron Binary Reconnaissance

## Win32 Binary (chromatron_unpacked.exe)
- **Original size**: 39,936 bytes (UPX compressed)
- **Unpacked size**: 98,304 bytes
- **Format**: PE32 executable (GUI) Intel 80386, MS Windows
- **Compiler**: Microsoft Visual C++ (MSVC runtime strings present)
- **Sections**: .text, .rdata, .data
- **Version string**: "Chromatron 1.14"

### Win32 API Surface
- **Window**: CreateWindowExA, RegisterClassExA, DefWindowProcA, ShowWindow, UpdateWindow
- **Message loop**: GetMessageA, TranslateMessage, DispatchMessageA
- **Rendering**: BeginPaint/EndPaint, SetDIBitsToDevice, SetBkColor, DrawTextA, GetStockObject
- **Input**: (handled via WndProc message switch)
- **Clipboard**: OpenClipboard, CloseClipboard, GetClipboardData, SetClipboardData, EmptyClipboard, GlobalAlloc/Lock/Unlock
- **File I/O**: CreateFileA, ReadFile, WriteFile, SetFilePointer, CloseHandle
- **System**: GetLocalTime, GetSystemTime, GetModuleFileNameA, MessageBoxA
- **UI**: InvalidateRect, LoadCursorA, LoadIconA, GetSystemMetrics, PostQuitMessage

### Key Observations
- Uses SetDIBitsToDevice (not BitBlt) = software rendering to a DIB, then blitting
- Clipboard support = Ctrl+C/V for solution sharing
- DrawTextA = text rendering via GDI (not bitmap font)
- No DirectDraw/Direct3D/OpenGL imports = pure GDI software rendering
- GetLocalTime/GetSystemTime = possible timing/seed for something

## Mac PPC Binary (chromatron1)
- **Size**: 77,676 bytes
- **Format**: Mach-O executable ppc
- **Version string**: "Chromatron 1 (v1.15)" (slightly newer!)
- **Bundle ID**: com.silverspaceship.chromatron

### String Comparison
Both binaries share identical game text strings (instruction text, "You win!", etc.).
Mac has "UseMouseWheelToChangeLevel" preference key.
Mac version is v1.15, Win is v1.14.

## Game Elements (from instruction strings)
1. **Reflector** - Mirror, rotatable by clicking
2. **Splitter** - Splits beam at angle, passes through head-on; can merge beams
3. **Prism** - Bends R/G/B differently at glancing angle on long face
4. **Bender** - Angled reflector, converts horizontal/vertical to diagonal and vice versa
5. **Doppler** - Color shift: R→G→B→R forward, reverse backward
6. **Quantum Tangler** - Input one side, output pair in opposite directions; entangled color changes
7. **Teleporter** - Beam jumps to next teleporter in same direction
8. **Filter** - Allows only one color through
9. **Black Pinwheel** - Must NOT be hit by any laser to win

## Color System
- Primary: Red, Green, Blue
- Mixed: Magenta (R+B), Yellow (R+G), Cyan (G+B)
- White: R+G+B combined
- Additive color mixing model

## Level System
- 50 levels total (numbered 1-50)
- Level status: Red=inaccessible, Green=open, Blue=complete
- Progressive unlock system
