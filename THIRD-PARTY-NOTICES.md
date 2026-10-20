# Third-party notices

Shorts Toolkit is Julian Green's own work (see [LICENSE](LICENSE)). It ships with
the third-party parts listed here, and each one stays under its own licence. Your
installed copy has the licence texts: `licenses\` next to this file (one folder per
Python library, with `INDEX.txt`), and inside `_internal\`: `fonts\`, `bin\LICENSE`
(FFmpeg) and `onnxruntime\ThirdPartyNotices.txt`. The file paths in the tables
below are inside `_internal\`.

Last checked against the 0.32.0 build. `tools\collect_licenses.py` rebuilds the
library list from what each build actually packs.

## Programs and media libraries

| Part | Version | Licence | Where its source is |
|---|---|---|---|
| FFmpeg (`bin\ffmpeg.exe`, the gyan.dev "essentials" build; used for rendering) | 9.0.2 | GPL version 3 (the build enables GPL parts such as x264 and libass). Full text in `bin\LICENSE`. | https://ffmpeg.org/download.html and https://www.gyan.dev/ffmpeg/builds/ |
| FFmpeg libraries inside PyAV (`av.libs\`; used to read audio and file details) | 8.1.2 | LGPL version 3 or later | https://github.com/PyAV-Org/pyav-ffmpeg |
| Codec libraries inside PyAV's FFmpeg: x264, x265 | as shipped by PyAV 18.1.0 | GPL version 2 or later | https://code.videolan.org/videolan/x264, https://bitbucket.org/multicoreware/x265_git |
| Codec libraries inside PyAV's FFmpeg: dav1d, libvpx, libwebp, Opus, SVT-AV1, oneVPL, zlib | as shipped by PyAV 18.1.0 | BSD-style, MIT or zlib licences | listed in https://github.com/PyAV-Org/pyav-ffmpeg |
| Codec libraries inside PyAV's FFmpeg: LAME (MP3), opencore-amr, libiconv | as shipped by PyAV 18.1.0 | LGPL (LAME, libiconv), Apache 2.0 (opencore-amr) | listed in https://github.com/PyAV-Org/pyav-ffmpeg |
| GCC runtime and winpthreads (`libgcc_s_seh`, `libstdc++`, `libwinpthread`) | as shipped by PyAV | GPL with the GCC Runtime Library Exception; winpthreads MIT | https://gcc.gnu.org, https://www.mingw-w64.org |
| Python | 3.12.10 | Python Software Foundation License | https://www.python.org |
| OpenSSL (`libssl-3`, `libcrypto-3`) | 3.x, as shipped with Python | Apache 2.0 | https://www.openssl.org |
| SQLite | as shipped with Python | public domain | https://sqlite.org |
| libffi | as shipped with Python | MIT | https://sourceware.org/libffi |
| Microsoft Visual C++ runtime (`vcruntime140`, `msvcp140`) | 14.x | Microsoft's redistributable licence | - |
| Microsoft WebView2 SDK (`webview\lib\Microsoft.Web.WebView2.*.dll`) | as shipped by pywebview 6.2.1 | Microsoft's licence for the WebView2 SDK | https://www.nuget.org/packages/Microsoft.Web.WebView2 |
| Intel OpenMP runtime (`ctranslate2\libiomp5md.dll`) | as shipped by CTranslate2 4.8.2 | Intel Simplified Software License | - |
| NVIDIA cuDNN loader (`ctranslate2\cudnn64_9.dll`, unused on AMD and Intel graphics) | as shipped by CTranslate2 4.8.2 | NVIDIA cuDNN Software License Agreement | - |

The FFmpeg program runs as its own separate program; the app sends it commands
and does not include its code. The FFmpeg libraries inside PyAV are loaded by the
app; you may replace them with your own build of the same version.

## Python libraries

43 libraries, all under permissive licences (MIT, BSD, Apache 2.0, MPL 2.0,
PSF): anyio, av (PyAV), bottle, certifi, cffi, charset-normalizer, click,
clr_loader, colorama, ctranslate2, faster-whisper, filelock, flatbuffers, fsspec,
h11, hf-xet, httpcore, httpx, huggingface_hub, Jinja2, MarkupSafe, ml_dtypes,
numpy, onnxruntime, packaging, Pillow, platformdirs, proxy_tools, psutil,
pycparser, pythonnet, pywebview, pywin32-ctypes, PyYAML, qrcode, requests,
setuptools, threadpoolctl, tokenizers, tqdm, typing_extensions, urllib3. Versions
and the licence of each are in `licenses\INDEX.txt`, with the full texts beside it.

certifi and tqdm are partly under the Mozilla Public License 2.0. Their source is
at https://github.com/certifi/python-certifi and https://github.com/tqdm/tqdm; the
app uses them unchanged.

The app is packed with PyInstaller, whose licence (GPL 2 with a special exception)
allows its start-up code to be included in programs under any licence.

## AI models and data

| Part | Licence | Credit |
|---|---|---|
| Laugh and sound model (`models\panns_sed.onnx`, `models\panns_melW.npy`), converted from Cnn14_DecisionLevelMax | weights: CC BY 4.0; code: MIT | Qiuqiang Kong, Yin Cao, Turab Iqbal, Yuxuan Wang, Wenwu Wang, Mark D. Plumbley, "PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition", 2020. Weights: https://zenodo.org/record/3987831. Changed: converted from PyTorch to ONNX (`tools\export_panns_onnx.py`). |
| Sound class names (`models\audioset_labels.csv`) | CC BY-SA 4.0 | Google, AudioSet ontology, https://github.com/audioset/ontology |
| Whisper speech models (not in the installer; downloaded on first use) | MIT | OpenAI Whisper weights, in the CTranslate2 format from https://huggingface.co/Systran, or the whisper.cpp format from https://huggingface.co/ggerganov/whisper.cpp |

## Fonts

All under the SIL Open Font License 1.1 except where noted. Each font's licence is
in `fonts\`.

| Font | Copyright |
|---|---|
| Anton | The Anton Project Authors |
| Archivo Black | The Archivo Black Project Authors |
| Bangers | The Bangers Project Authors |
| Bebas Neue | Dharma Type |
| Lilita One | Juan Montoreano |
| Luckiest Guy | Astigmatic (Apache License 2.0) |
| Montserrat | The Montserrat Project Authors |
| Permanent Marker | Font Diner (Apache License 2.0) |
| Poppins | The Poppins Project Authors |
| Rubik Mono One | The Rubik Project Authors |
| Titan One | Rodrigo Fuenzalida |

## Not included

Adobe Premiere Pro, Ollama and its models, the whisper.cpp graphics-card build, and
the Edge WebView2 runtime are separate programs that you install yourself. They are
not part of Shorts Toolkit and are not covered by its licence.
