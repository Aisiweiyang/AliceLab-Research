# -*- coding: utf-8 -*-
"""offline_detector 已知答案单元测试（含 Fearnhead 精确后验增补）。
借鉴 hildensia/bayesian_changepoint_detection 的 quick_test 模式：注入已知断点必须
检出、干净序列不得报警、新旧实现必须互相一致。
运行: lab-venv/Scripts/python.exe test_offline_detector.py
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from alicelab.changepoints import (  # noqa: E402
    detect, exact_detect, exact_posterior, one_break_posterior, seg_loglik,
    seg_loglik_matrix, unit_test)

ok = True
def check(name, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail else ""))
    ok = ok and bool(cond)

# 1) 既有单断点检测器回归（第五轮口径：位置命中）
ut = unit_test()
check("legacy unit_test: 2.0σ=100%", ut[2.0]["detect_rate"] == 1.0)
check("legacy unit_test: 1.0σ>=80%", ut[1.0]["detect_rate"] >= 0.8)

# 2) 前缀和矩阵与直接 seg_loglik 一致（抽样校验）
rng = np.random.default_rng(7)
x = rng.standard_normal(120)
M = seg_loglik_matrix(x, min_seg=10, lam=1 / 50)
from math import log
errs = []
for t in range(0, 100, 17):
    for s in range(t + 10, 120, 23):
        n = s - t
        expected = seg_loglik(x, t, s) + log(1 / 50) + (n - 1) * log(1 - 1 / 50)
        errs.append(abs(M[t, s] - expected))
check("prefix-matrix == direct seg_loglik", max(errs) < 1e-8, f"max_err={max(errs):.2e}")

# 3) Fearnhead 精确后验: 干净序列误报控制。
#    说明: lam=1/250先验下500周数据P(k=1)≈P(k=0)属先验预期(期望~1断点)，
#    检判决🎚k_ge1>0.8须在干净序列上零误报、注入序列高检出（分离度判据, D-012制度）。
rng = np.random.default_rng(20260910)
clean_pk = [exact_detect(rng.standard_normal(500))["p_k_ge1"] for _ in range(20)]
check("exact: clean p_k_ge1 max < 0.8 (zero FP at tau=0.8)", max(clean_pk) < 0.8,
      f"median={float(np.median(clean_pk)):.3f} max={max(clean_pk):.3f}")

# 4) 1.0σ 注入(500点@250) → k>=1 高概率且位置命中±10
hits = 0
for rep in range(30):
    zz = rng.standard_normal(500)
    zz[250:] += 1.0
    r = exact_detect(zz)
    if r["p_k_ge1"] > 0.8 and abs(r["t1"] - 250) <= 10:
        hits += 1
check("exact: 1.0σ detect>=80% (p_k_ge1>0.8) & loc±10", hits / 30 >= 0.8, f"{hits}/30")

# 5) k=1 位置后验与 one_break_posterior 一致（同一定理两条实现路径）
zz = rng.standard_normal(300)
zz[150:] += 1.0
ts_old, post_old = one_break_posterior(zz)
r = exact_posterior(zz, min_seg=26, lam=1 / 250)
same_argmax = ts_old[int(np.argmax(post_old))] == int(r["ts"][int(np.argmax(r["loc1_post"]))])
# 概率同族不同口径(softmax网格全体 vs 条件k=1)，比较位置与相关性
corr = float(np.corrcoef(post_old, r["loc1_post"][:len(post_old)])[0, 1])
check("exact k=1 argmax == one_break argmax", same_argmax)
check("exact k=1 posterior correlates with legacy", corr > 0.99, f"corr={corr:.4f}")

# 6) 0.5σ 弱断点：不要求高检出，但 p_k_ge1 应显著高于干净序列基线
weak = []
for _ in range(10):
    z = rng.standard_normal(500)
    z[250:] += 0.5
    weak.append(exact_detect(z)["p_k_ge1"])
check("exact: 0.5σ p_k_ge1 median > 0.8 (near-full detection)", float(np.median(weak)) > 0.8,
      f"median={float(np.median(weak)):.3f} vs clean median={float(np.median(clean_pk)):.3f}")

# 7) F-018 回归：幻影路径剔除 + 先验尺度标定
#    修正前: Q[1,0]==Q[0,0]（s=T空后缀幻影）→ 干净序列 p_k_ge1 恒≈0.5（任何阈值<0.5误报50%）
rng = np.random.default_rng(20260910)
clean_after = [exact_detect(rng.standard_normal(500))["p_k_ge1"] for _ in range(20)]
check("F-018 fixed: clean p_k_ge1 median < 0.2 (幻影下限已除)",
      float(np.median(clean_after)) < 0.2, f"median={float(np.median(clean_after)):.3f}")
#    小尺度序列(σ=0.05, 位移0.04=0.8σ, 同周频IC量级): 不标准化→证据被B0=1先验压缩;
#    standardize=True→应正常检出
shifted_small = np.concatenate([rng.normal(0.02, 0.05, 150), rng.normal(-0.02, 0.05, 100)])
r_raw = exact_detect(shifted_small)  # raw口径（不标准化），不可靠属F-018②记载行为
from alicelab.changepoints import exact_posterior as _ep  # noqa: E402
rp = _ep(shifted_small, standardize=True)
pk_std = float(1 - rp["k_dist"][0])
check("F-018 fixed: 小尺度0.8σ序列 standardize后 p_k_ge1 > 0.8", pk_std > 0.8,
      f"raw={r_raw['p_k_ge1']:.3f} std={pk_std:.3f} (raw不可靠属F-018②记载行为)")

# 8) k=2 断点对枚举的一致性恒等式（joint_pair_logw vs Q 递推，两条独立路径）
from scipy.special import logsumexp  # noqa: E402
from alicelab.changepoints import joint_pair_logw, seg_loglik_matrix  # noqa: E402
zz2 = rng.standard_normal(160)
zz2[80:] += 1.2
rp2 = _ep(zz2, min_seg=13, lam=1 / 60, standardize=True)
Mm = seg_loglik_matrix((zz2 - zz2.mean()) / zz2.std(), min_seg=13, lam=1 / 60)
lw, ss2 = joint_pair_logw((zz2 - zz2.mean()) / zz2.std(), min_seg=13, lam=1 / 60)
lhs = float(logsumexp(lw) - Mm[0, len(zz2)])
rhs = float(rp2["Q"][2, 0] - rp2["Q"][0, 0])
check("k=2 pair enumeration == Q recursion (log-ratio identity)",
      abs(lhs - rhs) < 1e-8, f"lhs={lhs:.6f} rhs={rhs:.6f}")
# 边际一致性：P(s1|k=2) 峰值应落在真实断点 80 附近（±10）
w2 = np.exp(lw - logsumexp(lw))
marg_s1 = w2.sum(axis=0)
check("k=2 marginal s1 peak near true break",
      abs(int(ss2[int(np.argmax(marg_s1))]) - 80) <= 10,
      f"peak at {int(ss2[int(np.argmax(marg_s1))])}")

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
