"""Developer tool (needs torch + panns_inference): convert the PANNs laugh model to ONNX.

The app itself only needs onnxruntime + numpy. This writes:
  models/panns_sed.onnx   - Cnn14_DecisionLevelMax from its log-mel input to per-frame
                            AudioSet probabilities (before the x32 frame repeat)
  models/panns_melW.npy   - the model's own mel filterbank (513 x 64)
and checks the numpy + ONNX pipeline against the original PyTorch model.

    .venv\\Scripts\\python tools\\export_panns_onnx.py
"""
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "models")
CKPT = os.path.join(os.path.expanduser("~"), "panns_data", "Cnn14_DecisionLevelMax.pth")


class Core(torch.nn.Module):
    """Everything after the log-mel front end, in eval mode."""
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, logmel):                      # (B, 1, T, 64)
        m = self.m
        x = logmel.transpose(1, 3)
        x = m.bn0(x)
        x = x.transpose(1, 3)
        for blk, pool in ((m.conv_block1, 2), (m.conv_block2, 2), (m.conv_block3, 2),
                          (m.conv_block4, 2), (m.conv_block5, 2), (m.conv_block6, 1)):
            x = blk(x, pool_size=(pool, pool), pool_type="avg")
        x = torch.mean(x, dim=3)
        x = F.max_pool1d(x, 3, 1, 1) + F.avg_pool1d(x, 3, 1, 1)
        x = x.transpose(1, 2)
        x = F.relu_(m.fc1(x))
        return torch.sigmoid(m.fc_audioset(x))      # (B, T/32, 527)


def main():
    from panns_inference.models import Cnn14_DecisionLevelMax
    m = Cnn14_DecisionLevelMax(sample_rate=32000, window_size=1024, hop_size=320, mel_bins=64,
                               fmin=50, fmax=14000, classes_num=527)
    m.load_state_dict(torch.load(CKPT, map_location="cpu")["model"])
    m.eval()
    os.makedirs(OUT, exist_ok=True)
    melW = m.logmel_extractor.melW.detach().numpy().astype(np.float32)
    np.save(os.path.join(OUT, "panns_melW.npy"), melW)
    core = Core(m).eval()
    dummy = torch.randn(1, 1, 3001, 64)
    torch.onnx.export(core, dummy, os.path.join(OUT, "panns_sed.onnx"), input_names=["logmel"],
                      output_names=["probs"], dynamic_axes={"logmel": {0: "b", 2: "t"}, "probs": {0: "b", 1: "t"}},
                      opset_version=17, dynamo=False)
    print("exported", os.path.getsize(os.path.join(OUT, "panns_sed.onnx")) // 1_000_000, "MB")

    # check against the original on real-ish audio: noise bursts + tones
    import sounds
    rng = np.random.default_rng(0)
    audio = (rng.standard_normal(32000 * 20) * np.repeat(rng.random(20) > .5, 32000) * 0.1).astype(np.float32)
    with torch.no_grad():
        ref = m(torch.from_numpy(audio)[None])["framewise_output"][0].numpy()
    got = sounds.infer(audio)
    n = min(len(ref), len(got))
    print("frames", len(ref), len(got), "max abs diff %.2e" % np.abs(ref[:n] - got[:n]).max())


if __name__ == "__main__":
    main()
