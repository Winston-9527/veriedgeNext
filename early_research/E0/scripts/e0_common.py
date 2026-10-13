"""E0 共用工具：context 读写、top-k 抽取、capture 落盘格式、权重量化（RTN / GPTQ）。

capture 文件格式（npz，每个执行栈一个）：
    seq_idx   int32 [M]      所属序列（prompt）下标
    pos       int32 [M]      该 context 在序列中的位置（预测第 pos+1 个 token）
    topk_ids  int32 [M, K]   top-K token id，按 logit 降序
    topk_val  float32 [M, K] 对应 logit
    meta_json str            栈描述、版本、设备、contexts 摘要
所有栈共享同一份 contexts.jsonl（token id 级别，不重新分词），保证逐 context 对齐。
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
from pathlib import Path

import numpy as np

TOPK = 5


# ---------------------------------------------------------------- contexts

def load_contexts(path: Path) -> tuple[list[dict], str]:
    """读取 e0_build_contexts.py 产出的 contexts.jsonl，返回 (rows, sha256)。"""
    raw = Path(path).read_bytes()
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    return rows, hashlib.sha256(raw).hexdigest()


def context_positions(row: dict) -> range:
    """被评估的位置：从 prompt 最后一个 token 起，到续写倒数第二个 token。

    位置 p 的 logits 预测 token p+1，因此覆盖全部参考续写 token。
    """
    return range(row["prompt_len"] - 1, len(row["input_ids"]) - 1)


# ---------------------------------------------------------------- capture io

def topk_from_logits(logits: np.ndarray, k: int = TOPK) -> tuple[np.ndarray, np.ndarray]:
    """logits [T, V] float32 -> (ids [T,k], vals [T,k])，按 logit 降序。"""
    part = np.argpartition(-logits, k, axis=-1)[:, :k]
    vals = np.take_along_axis(logits, part, axis=-1)
    order = np.argsort(-vals, axis=-1, kind="stable")
    return (np.take_along_axis(part, order, axis=-1).astype(np.int32),
            np.take_along_axis(vals, order, axis=-1).astype(np.float32))


class CaptureWriter:
    def __init__(self) -> None:
        self.seq, self.pos, self.ids, self.val = [], [], [], []

    def add(self, seq_idx: int, positions: range, logits: np.ndarray) -> None:
        """logits: 整条序列的 [T, V]；只保留 positions 对应的行。"""
        sel = np.asarray(list(positions))
        ids, vals = topk_from_logits(np.asarray(logits, dtype=np.float32)[sel])
        self.seq.append(np.full(len(sel), seq_idx, np.int32))
        self.pos.append(sel.astype(np.int32))
        self.ids.append(ids)
        self.val.append(vals)

    def save(self, out: Path, meta: dict) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            out,
            seq_idx=np.concatenate(self.seq), pos=np.concatenate(self.pos),
            topk_ids=np.concatenate(self.ids), topk_val=np.concatenate(self.val),
            meta_json=np.array(json.dumps(meta, ensure_ascii=False)),
        )
        print(f"saved {out}  contexts={sum(len(s) for s in self.seq)}")


def load_capture(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    d = {k: z[k] for k in ("seq_idx", "pos", "topk_ids", "topk_val")}
    d["meta"] = json.loads(str(z["meta_json"]))
    return d


def host_meta() -> dict:
    return {"hostname": platform.node(), "python": platform.python_version(),
            "platform": platform.platform()}


# ---------------------------------------------------------------- weight quantization (torch)
# 只做 fake-quant：量化后立即反量化回浮点，计算仍在 --dtype 下进行。
# 这样隔离出"权重精度"这一个变量；真实低比特 kernel 的效果由 mlx / bnb 栈覆盖。

def _qparams(w, bits: int, sym: bool):
    """w: [..., g] 一组权重 -> (scale, zero)，形状 [..., 1]。"""
    import torch
    maxq = 2 ** bits - 1
    if sym:
        amax = w.abs().amax(dim=-1, keepdim=True).clamp(min=1e-8)
        scale = 2 * amax / maxq
        zero = torch.full_like(scale, (maxq + 1) / 2)
    else:
        xmin = w.amin(dim=-1, keepdim=True).clamp(max=0)
        xmax = w.amax(dim=-1, keepdim=True).clamp(min=0)
        scale = ((xmax - xmin) / maxq).clamp(min=1e-8)
        zero = torch.round(-xmin / scale)
    return scale, zero


def _fake_quant(w, scale, zero, bits: int):
    import torch
    q = torch.clamp(torch.round(w / scale) + zero, 0, 2 ** bits - 1)
    return (q - zero) * scale


def rtn_quantize_(weight, bits: int, group_size: int, sym: bool) -> None:
    """原地对 Linear.weight [out, in] 做按组 RTN fake-quant。"""
    out_f, in_f = weight.shape
    assert in_f % group_size == 0, (in_f, group_size)
    w = weight.data.float().reshape(out_f, in_f // group_size, group_size)
    scale, zero = _qparams(w, bits, sym)
    weight.data.copy_(_fake_quant(w, scale, zero, bits).reshape(out_f, in_f).to(weight.dtype))


def gptq_quantize_(weight, H, bits: int, group_size: int, sym: bool,
                   blocksize: int = 128, percdamp: float = 0.01, device=None) -> None:
    """紧凑版 GPTQ（Frantar et al. 2023，无 act-order），原地 fake-quant。

    H: 该层输入的二阶统计 2·XᵀX/n，[in, in]。要求 group_size == blocksize，
    这样组的 scale 恰好在每个 block 开头由已补偿的权重确定。
    """
    import torch
    assert group_size == blocksize, "compact GPTQ requires group_size == blocksize"
    dev = device or weight.device
    W = weight.data.to(dev).float()
    ncols = W.shape[1]
    H = H.to(dev).float()
    dead = torch.diag(H) == 0
    H[dead, dead] = 1
    W[:, dead] = 0
    H += percdamp * torch.mean(torch.diag(H)) * torch.eye(ncols, device=H.device)
    Hinv = torch.linalg.cholesky(torch.cholesky_inverse(torch.linalg.cholesky(H)), upper=True)

    Q = torch.zeros_like(W)
    for i1 in range(0, ncols, blocksize):
        i2 = min(i1 + blocksize, ncols)
        W1 = W[:, i1:i2].clone()
        Q1 = torch.zeros_like(W1)
        Err1 = torch.zeros_like(W1)
        Hinv1 = Hinv[i1:i2, i1:i2]
        scale, zero = _qparams(W1, bits, sym)  # 每个 block = 一个量化组
        for i in range(i2 - i1):
            w = W1[:, i:i + 1]
            q = _fake_quant(w, scale, zero, bits)
            Q1[:, i:i + 1] = q
            err = (w - q) / Hinv1[i, i]
            W1[:, i:] -= err @ Hinv1[i:i + 1, i:]
            Err1[:, i:i + 1] = err
        Q[:, i1:i2] = Q1
        W[:, i2:] -= Err1 @ Hinv[i1:i2, i2:]
    weight.data.copy_(Q.to(weight.dtype))


def parse_layers(spec: str | None) -> tuple[int, int] | None:
    """"12-23" -> (12, 23)（闭区间）；空值表示全部层。"""
    if not spec:
        return None
    a, b = spec.split("-")
    return int(a), int(b)


def layer_index(name: str) -> int | None:
    """从 "model.layers.7.mlp.down_proj" 这类模块路径里取出层号。"""
    parts = name.split(".")
    for i, p in enumerate(parts[:-1]):
        if p == "layers" and parts[i + 1].isdigit():
            return int(parts[i + 1])
    return None


def decoder_linears(model, layers: tuple[int, int] | None = None):
    """返回 [(name, nn.Linear)]：decoder 层内的线性层（embedding / lm_head 不量化）。

    layers=(a, b) 时只返回第 a..b 层，用来模拟"流水线里只有一个分片降精度"。
    """
    import torch.nn as nn
    out = []
    for n, m in model.named_modules():
        idx = layer_index(n)
        if isinstance(m, nn.Linear) and idx is not None and (layers is None or layers[0] <= idx <= layers[1]):
            out.append((n, m))
    return out


# ---------------------------------------------------------------- stats

def kl_bern(a: float, b: float) -> float:
    eps = 1e-12
    a, b = min(max(a, eps), 1 - eps), min(max(b, eps), 1 - eps)
    return a * math.log(a / b) + (1 - a) * math.log((1 - a) / (1 - b))


def chernoff_n(p_h: float, p_q: float, alpha: float) -> float:
    """区分诚实失配率 p_h 与作弊失配率 p_q 所需 canary 数的 Chernoff 量级估计。"""
    if p_q <= p_h:
        return math.inf
    return math.log(1 / alpha) / kl_bern(p_q, p_h)


def exact_binomial_design(p_h: float, p_q: float, alpha: float, beta: float,
                          n_max: int = 20000) -> dict | None:
    """最小 N 与阈值 k：Pr[Bin(N,p_h)≥k] ≤ α 且 Pr[Bin(N,p_q)<k] ≤ β。找不到返回 None。"""
    if p_q <= p_h:
        return None
    if p_h <= 0:  # 诚实栈从不失配：一次失配即判作弊
        if p_q >= 1:
            return {"N": 1, "k": 1, "fpr": 0.0, "fnr": 0.0}
        n = max(1, math.ceil(math.log(beta) / math.log(1 - p_q)))
        return {"N": n, "k": 1, "fpr": 0.0, "fnr": float((1 - p_q) ** n)}
    lo, hi = 1, n_max
    def ok(n: int):
        sf_h = _binom_sf(n, p_h)                 # sf_h[k] = Pr[Bin ≥ k]
        k = int(np.argmax(sf_h <= alpha))         # 最小 k 使误报 ≤ α
        return k if 1 - _binom_sf(n, p_q)[k] <= beta else None
    if ok(hi) is None:
        return None
    while lo < hi:  # 近似单调，二分找最小 N
        mid = (lo + hi) // 2
        if ok(mid) is None:
            lo = mid + 1
        else:
            hi = mid
    k = ok(lo)
    return {"N": lo, "k": k,
            "fpr": float(_binom_sf(lo, p_h)[k]), "fnr": float(1 - _binom_sf(lo, p_q)[k])}


def _binom_sf(n: int, p: float) -> np.ndarray:
    """返回长度 n+2 的数组，第 k 项为 Pr[Bin(n,p) ≥ k]（不依赖 scipy）。"""
    p = min(max(p, 1e-12), 1 - 1e-12)
    k = np.arange(n + 1)
    lg = np.concatenate([[0.0], np.cumsum(np.log(np.arange(1, n + 1)))])  # log k!
    logpmf = lg[n] - lg - lg[::-1] + k * math.log(p) + (n - k) * math.log1p(-p)
    pmf = np.exp(logpmf - logpmf.max())
    pmf /= pmf.sum()
    return np.concatenate([np.cumsum(pmf[::-1])[::-1], [0.0]])
