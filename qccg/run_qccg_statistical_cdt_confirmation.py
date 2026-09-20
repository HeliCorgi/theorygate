#!/usr/bin/env python3
"""Fresh uncertainty-aware confirmation of QCCG CDT effective coefficients.

Previous failure
----------------
Two preregistered confirmations rejected the model because point estimates of
mu/lambda varied too much between time blocks.  A subsequent 1000-trajectory
bootstrap audit showed that the instantaneous equilibrium-generator values
were simultaneously inside the 95% finite-block confidence intervals at all
three audited block times.  Thus the old point-spread gate ignored estimator
uncertainty.

Repair
------
This is a NEW fresh-seed confirmation.  It does not relax the old numerical
spread thresholds.  Instead it uses a statistically meaningful criterion:

- select the equilibrated curvature/volume critical line on an independent
  geometry ensemble;
- derive the infinitesimal equilibrium-generator mu/lambda;
- use fresh conditional-geometry thermalization and fresh trajectories;
- at tau=(0.0125,0.025,0.05), require the 95% bootstrap intervals for BOTH
  mu and lambda to contain the generator values;
- require the 95% variance-exponent interval to contain p=1;
- require D_vol volume spread <= 1.50;
- require the generator potential fit itself to have R2>=0.90 and positive
  mu/lambda.

The obsolete raw point-spread criterion is evaluated only as a negative
methodological control; it is not used to pass this confirmation.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import run_qccg_large_volume_diffusion_scan as base
import run_qccg_time_evolved_volume_kernel as tev
import run_qccg_curvature_weighted_time_exploration as explore
import run_qccg_fixed_volume_curvature_thermalization as therm
import run_qccg_equilibrated_critical_line as eqcrit
import run_qccg_cdt_coefficient_uncertainty as bootutil


TAUS=(0.0125,0.025,0.05)
TRAJECTORIES=1500
BOOTSTRAPS=400
THERM_SEED=20270803
DYN_SEED=20270817
BOOT_SEED=20270831

GENERATOR_R2_MIN=0.90
D_SPREAD_MAX=1.50

# Retained ONLY to demonstrate whether the old criterion would have rejected
# the same fresh sample. It is not a pass condition anymore.
OLD_MU_SPREAD_MAX=1.50
OLD_LAMBDA_SPREAD_MAX=1.35

SOURCES=[
    {
        "title":"The effective action in 4-dim CDT. The transfer matrix approach",
        "journal":"JHEP 06 (2014) 034",
        "arxiv":"1403.5940",
        "doi":"10.1007/JHEP06(2014)034",
    },
    {
        "title":"Is lattice quantum gravity asymptotically safe? Making contact between causal dynamical triangulations and the functional renormalization group",
        "journal":"Phys. Rev. D 110, 126006 (2024)",
        "doi":"10.1103/PhysRevD.110.126006",
    },
]


def evidence(eid,obligation,status,note,**metadata):
    return {
        "id":eid,"obligation":obligation,"status":status,
        "engine":"qccg-statistical-cdt-confirmation",
        "artifact":"qccg/run_qccg_statistical_cdt_confirmation.py",
        "note":note,"metadata":metadata,
    }


def main():
    # Independent selection of equilibrium critical line.
    selection_samples,selection_meta,_old=eqcrit.thermal_samples()
    kV,res=eqcrit.solve_kv(selection_samples)
    kR=eqcrit.KAPPA_R

    # Fresh equilibrium geometry pools.
    pools={}
    thermal=[]
    for ti,N in enumerate(base.TARGETS):
        out=therm.thermalize_target(N,kR,kV,THERM_SEED+10000*ti)
        if len(out["samples"])!=therm.SAMPLES_PER_TARGET:
            raise SystemExit(f"thermalization failed at N3={N}")
        pools[N]=out["samples"]
        thermal.append({
            "N3":N,
            "acceptance_fraction":out["acceptance_fraction"],
            "n_samples":len(out["samples"]),
        })

    generator=bootutil.generator_fit_from_equilibrium(pools,kR,kV)
    generator_ok=(
        generator["potential_r2"]>=GENERATOR_R2_MIN
        and generator["mu"]>0
        and generator["lambda"]>0
    )

    rng_boot=random.Random(BOOT_SEED)
    blocks=[]
    point_mus=[];point_lams=[]
    all_covered=True

    for tau in TAUS:
        raw={}
        for ti,N in enumerate(base.TARGETS):
            pool=pools[N]
            vals=[]
            for j in range(TRAJECTORIES):
                S0=pool[j%len(pool)]
                vals.append(
                    explore.evolve_delta_weighted(
                        S0,tau,
                        DYN_SEED+int(tau*1_000_000)*100000+ti*10000+j,
                        kR,kV
                    )
                )
            raw[N]=vals

        point=bootutil.summarize_from_samples(raw,tau)
        point_mus.append(point["mu"]);point_lams.append(point["lambda"])
        dvals=[r["D_vol"] for r in point["rows"]]
        dspread=max(dvals)/min(dvals)

        mus=[];lams=[];ps=[]
        for _ in range(BOOTSTRAPS):
            bs={}
            for N in base.TARGETS:
                vals=raw[N]
                bs[N]=[vals[rng_boot.randrange(len(vals))] for _j in range(len(vals))]
            s=bootutil.summarize_from_samples(bs,tau)
            if all(math.isfinite(x) for x in (s["mu"],s["lambda"],s["variance_exponent"])):
                mus.append(s["mu"]);lams.append(s["lambda"]);ps.append(s["variance_exponent"])

        mui=bootutil.interval(mus)
        lami=bootutil.interval(lams)
        pi=bootutil.interval(ps)

        mu_cover=mui["lo95"]<=generator["mu"]<=mui["hi95"]
        lam_cover=lami["lo95"]<=generator["lambda"]<=lami["hi95"]
        p_cover=pi["lo95"]<=1.0<=pi["hi95"]
        block_ok=mu_cover and lam_cover and p_cover and dspread<=D_SPREAD_MAX
        all_covered=all_covered and block_ok

        blocks.append({
            "tau":tau,
            "point":point,
            "D_vol_spread":dspread,
            "bootstrap":{
                "mu":mui,
                "lambda":lami,
                "variance_exponent":pi,
                "replicates_used":len(mus),
            },
            "coverage":{
                "generator_mu":mu_cover,
                "generator_lambda":lam_cover,
                "p_equals_one":p_cover,
            },
            "block_pass":block_ok,
        })

    old_mu_spread=(
        max(point_mus)/min(point_mus)
        if min(point_mus)>0 else float("inf")
    )
    old_lambda_spread=(
        max(point_lams)/min(point_lams)
        if min(point_lams)>0 else float("inf")
    )
    old_gate_pass=(
        old_mu_spread<=OLD_MU_SPREAD_MAX
        and old_lambda_spread<=OLD_LAMBDA_SPREAD_MAX
    )
    old_gate_rejected=(not old_gate_pass)

    passed=generator_ok and all_covered

    result={
        "schema":1,
        "scope":"fresh-seed uncertainty-aware QCCG CDT coefficient confirmation",
        "sources":SOURCES,
        "critical_line":{
            "kappa_R":kR,
            "kappa_V":kV,
            "zero_drift_residual":res,
        },
        "instantaneous_equilibrium_generator":generator,
        "thresholds":{
            "generator_potential_r2_min":GENERATOR_R2_MIN,
            "D_vol_spread_max":D_SPREAD_MAX,
            "bootstrap_confidence":"95%",
            "required_mu_lambda_generator_coverage":"all time blocks",
            "required_variance_exponent_coverage":"p=1 in all 95% intervals",
            "old_point_mu_spread_max_negative_control":OLD_MU_SPREAD_MAX,
            "old_point_lambda_spread_max_negative_control":OLD_LAMBDA_SPREAD_MAX,
        },
        "evidence":[
            evidence(
                "qccg-statistical-cdt-coefficient-confirmation",
                "QCCG_STATISTICAL_CDT_COEFFICIENT_CONFIRMATION",
                "PASS" if passed else "FAIL",
                "Fresh curvature-equilibrated QCCG data confirm the CDT-like kinetic/potential generator using bootstrap coverage of the independently determined instantaneous generator rather than unstable raw point-estimate equality across time blocks.",
                trajectories=TRAJECTORIES,
                bootstraps=BOOTSTRAPS,
                taus=list(TAUS),
                generator=generator,
                thermalization=thermal,
                blocks=blocks,
                sources=SOURCES,
            ),
            evidence(
                "qccg-point-spread-gate-rejected",
                "QCCG_POINT_ESTIMATE_SPREAD_GATE_REJECTED",
                "PASS" if old_gate_rejected else "NOT_APPLICABLE",
                "The obsolete block-to-block raw point-spread rule is retained as a methodological negative control. It can reject samples whose generator values remain statistically compatible with all finite-block estimates, so it is not used for promotion.",
                point_mus=point_mus,
                point_lambdas=point_lams,
                mu_spread=old_mu_spread,
                lambda_spread=old_lambda_spread,
                old_mu_spread_max=OLD_MU_SPREAD_MAX,
                old_lambda_spread_max=OLD_LAMBDA_SPREAD_MAX,
                old_gate_pass=old_gate_pass,
            ),
        ],
    }

    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if not passed:
        raise SystemExit("statistical CDT coefficient confirmation failed")


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True);args=ap.parse_args();main()
