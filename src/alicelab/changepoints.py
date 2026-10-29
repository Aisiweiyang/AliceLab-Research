"""Offline NIG change-point models; see docs/methods.md for assumptions."""
import numpy as np
MU0, K0, A0, B0 = 0.0, 1.0, 1.0, 1.0

def seg_loglik(x, a, b):
    """log NIG边际似然 of x[a:b]（Murphy 2007 eq.268）。"""
    n = b - a
    if n <= 0:
        return -np.inf
    xs = x[a:b]
    xb = xs.mean()
    ssc = float(((xs - xb) ** 2).sum())
    kn = K0 + n
    an = A0 + n / 2.0
    bn = B0 + 0.5 * ssc + 0.5 * K0 * n * (xb - MU0) ** 2 / kn
    from math import lgamma
    return (-n / 2.0 * np.log(np.pi) + lgamma(an) - lgamma(A0)
            + A0 * np.log(B0) - an * np.log(bn) + 0.5 * np.log(K0 / kn))

def softmax_log(scores):
    s = np.asarray(scores, dtype=float)
    s = s - np.nanmax(s[np.isfinite(s)]) if np.isfinite(s).any() else s
    e = np.exp(s)
    return e / e.sum()

def one_break_posterior(x, min_seg=26):
    """返回 P(断点=t | 数据, 恰有一次变化) 与峰值score。"""
    x = _validate(x, min_seg)
    T = len(x)
    base = seg_loglik(x, 0, T)
    ts = np.arange(min_seg, T - min_seg)
    scores = np.array([seg_loglik(x, 0, t) + seg_loglik(x, t, T) - base for t in ts])
    return ts, softmax_log(scores)

def detect(series, min_seg=26, conf=0.5):
    ts, post = one_break_posterior(np.asarray(series, dtype=float), min_seg=min_seg)
    i = int(np.argmax(post))
    return {"t": int(ts[i]), "prob": float(post[i]),
            "detected": bool(post[i] >= conf)}

def unit_test(n=300, break_at=150, reps=20, seed=20260910):
    """已知答案测试: 0.5σ/1.0σ断点须在±10内以高概率检出; 干净序列误报率须低。"""
    rng = np.random.default_rng(seed)
    res = {}
    for delta in (0.0, 0.5, 1.0, 2.0):
        hits, delays, probs = 0, [], []
        reps_ = 5 if delta == 0.0 else reps
        for _ in range(reps_):
            zz = rng.standard_normal(n)
            if delta:
                zz[break_at:] += delta
            r = detect(zz)
            if delta:
                if abs(r["t"] - break_at) <= 10:
                    hits += 1
                    delays.append(r["t"] - break_at)
                probs.append(r["prob"])
            else:
                probs.append(r["prob"])
        res[delta] = {"detect_rate": hits / reps_, "mean_delay": float(np.mean(delays)) if delays else None,
                      "mean_false_peak_prob": float(np.mean(probs))}
    return res

def _prefix(x):
    cs = np.concatenate([[0.0], np.cumsum(x)])
    cs2 = np.concatenate([[0.0], np.cumsum(np.asarray(x) ** 2)])
    return cs, cs2

def seg_loglik_matrix(x, min_seg=26, lam=1 / 250):
    """M[t,s] = log[ P(x[t:s]) * geom_len_prior(s-t, lam) ]，s>t；无效格=-inf。
    n=s-t须>=min_seg 且 s<=T（留不出左侧min_seg的位置在DP中处理）。"""
    from math import log
    if not 0 < lam < 1:
        raise ValueError("lam must be between zero and one")
    x = _validate(x, min_seg)
    T = len(x)
    cs, cs2 = _prefix(x)
    N = cs[None, :] - cs[:, None]            # N[t,s] = sum(x[t:s])
    N2 = cs2[None, :] - cs2[:, None]
    idx = np.arange(T + 1)
    n_mat = idx[None, :] - idx[:, None]      # n_mat[t,s] = s-t
    xb = np.where(n_mat > 0, N / np.where(n_mat > 0, n_mat, 1), 0.0)
    ssc = np.where(n_mat > 0, N2 - n_mat * xb ** 2, np.nan)
    from scipy.special import gammaln
    with np.errstate(all="ignore"):
        an = A0 + n_mat / 2.0
        bn = B0 + 0.5 * ssc + 0.5 * K0 * n_mat * (xb - MU0) ** 2 / (K0 + n_mat)
        M = (-n_mat / 2.0 * np.log(np.pi) + gammaln(an) - gammaln(A0)
             + A0 * np.log(B0) - an * np.log(bn) + 0.5 * np.log(K0 / (K0 + n_mat)))
    M = M + np.log(lam) + (n_mat - 1) * np.log(1 - lam)  # 几何段长先验
    M[n_mat < min_seg] = -np.inf
    np.fill_diagonal(M, -np.inf)
    return M

def exact_posterior(x, min_seg=26, lam=1 / 250, k_max=4, standardize=False):
    """Fearnhead(2006)精确后验（段长几何先验下的贝叶斯模型平均）。
    返回: k_dist(各断点数后验), loc1(k=1断点位置后验,对齐one_break_posterior的ts),
          Q(k, t)=P(x[t:]恰k断点) 的log矩阵（供前向取样/扩展）。

    F-018 修正①：k≥1 递推切片原为 t+1:T+1，把 s=T（"断点在末尾、后缀为空"）的幻影路径
    计入——Q[1,0] 恒等于 Q[0,0]，P(k≥1) 被抬出 0.5 下限。现排除 s=T（k≥2 在 s=T 处
    本就因 Q[k-1,T]=-inf 无贡献，切片收紧对其无影响）。
    F-018 修正②：standardize=True 时先标准化序列——NIG 先验(B0=1)按单位尺度标定，
    序列 σ≪1 时（如周频IC）bn 被 B0 主导、均值位移证据被压缩，k 级后验失真。
    条件位置后验 loc1_post 不受两问题影响（同类 Γ 项在分子分母间抵消）。"""
    from scipy.special import logsumexp
    if not isinstance(k_max, int) or k_max < 0:
        raise ValueError("k_max must be a nonnegative integer")
    x = _validate(x, min_seg)
    if standardize:
        sd = x.std()
        if sd > 0:
            x = (x - x.mean()) / sd
    T = len(x)
    M = seg_loglik_matrix(x, min_seg=min_seg, lam=lam)
    # Q[k, t]: log P(x[t:] 有恰好k个断点)
    Q = np.full((k_max + 1, T + 1), -np.inf)
    Q[0, T] = 0.0
    for t in range(T - 1, -1, -1):
        Q[0, t] = M[t, T]
        for k in range(1, k_max + 1):
            Q[k, t] = logsumexp(M[t, t + 1: T] + Q[k - 1, t + 1: T])
    k_logpost = np.array([Q[k, 0] for k in range(k_max + 1)])
    k_dist = softmax_log(k_logpost)
    # k=1 位置后验: P(break at s | k=1) ∝ M[0,s] + Q0[s]
    ss = np.arange(min_seg, T - min_seg + 1)
    loc_post = softmax_log(M[0, ss] + Q[0, ss])
    return {"k_dist": k_dist, "ts": ss, "loc1_post": loc_post, "Q": Q, "lam": lam}

def exact_detect(x, min_seg=26, lam=1 / 250, k_max=4):
    r = exact_posterior(x, min_seg=min_seg, lam=lam, k_max=k_max)
    i = int(np.argmax(r["loc1_post"]))
    return {"p_k0": float(r["k_dist"][0]),
            "p_k_ge1": float(1 - r["k_dist"][0]),
            "k_mode": int(np.argmax(r["k_dist"])),
            "t1": int(r["ts"][i]), "p_loc1_peak": float(r["loc1_post"][i]),
            "win_mass1": float(r["loc1_post"][max(0, i - 4): i + 5].sum())}

def joint_pair_logw(x, min_seg=26, lam=1 / 250):
    """k=2 断点对 (s1,s2) 的对数未归一联合后验矩阵（精确枚举，无采样误差——
    替代"前向-后向采样"方案；k=2 规模 ~T²/2 可全枚举）。
    logw[s1,s2] = M[0,s1]+M[s1,s2]+M[s2,T]（仅 ss 合法位置），无效格 -inf
    （min_seg 间距与顺序约束由 M 的 -inf 结构承载）。
    一致性恒等式（单测钉死）：logsumexp(logw) - M[0,T] == Q[2,0] - Q[0,0]。
    返回: (logw 矩阵 [|ss|×|ss|], ss 合法位置数组)。"""
    from scipy.special import logsumexp  # noqa: F401
    r = exact_posterior(x, min_seg=min_seg, lam=lam)
    M = seg_loglik_matrix(x, min_seg=min_seg, lam=lam)
    ss = r["ts"]  # 合法断点位置（min_seg 边距）
    B = M[np.ix_(ss, ss)]          # B[i,j] = M[s_i, s_j]
    C = M[ss, len(x)]              # C[j] = M[s_j, T]（尾段）
    logw = (M[0, ss][:, None] + B + C[None, :]).astype(float)
    logw[np.tril_indices(len(ss))] = -np.inf  # s2<=s1 显式无效（M 本身已 -inf，显式化便于读）
    return logw, ss

def _validate(x, min_seg):
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("series must be finite and one-dimensional")
    if not isinstance(min_seg, int) or min_seg < 2 or len(x) <= 2 * min_seg:
        raise ValueError("require min_seg >= 2 and len(series) > 2 * min_seg")
    return x

def cusum_stat(x, nu=0.5, mu0=0.0):
    """Two-sided CUSUM including observation zero; inputs use caller's scale."""
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all() or nu < 0:
        raise ValueError("finite one-dimensional series and nonnegative drift required")
    positive = negative = 0.0
    out = np.zeros(len(x))
    for i, value in enumerate(x - mu0):
        positive = max(0.0, positive + value - nu)
        negative = max(0.0, negative - value - nu)
        out[i] = max(positive, negative)
    return out
