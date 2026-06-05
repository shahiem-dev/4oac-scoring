"""
Grand Prix scoring simulation against the REAL 2025-26 WCSAA data.

Reproduces the proposal's methodology on live catches_scored:
  - Weight points per catch: ed 4/kg (min 0.5), non-ed 1/kg (min 1), sight fish flat 1
  - GP points per IC: (angler_weight_pts / max_weight_pts_in_IC) * 50
  - Fish points per IC: +1 per qualifying fish (meets min weight, excludes sight fish)
  - Season totals + ranks under each model

Outputs CSVs to raw/notes/wcsaa-gp-sim/ for the analysis deliverable.
Read-only against the DB.
"""
from __future__ import annotations
import tomllib, collections, csv
from pathlib import Path

ROOT = Path(r"C:\second-brain\4oac-scoring")
OUT  = Path(r"C:\second-brain\raw\notes\wcsaa-gp-sim")
SEASON = "2025-26"
GP_MAX = 50.0

def creds():
    with open(ROOT / ".streamlit" / "secrets.toml", "rb") as f:
        s = tomllib.load(f)
    return s["SUPABASE_URL"], s["SUPABASE_KEY"]

def fetch_all(sb, table):
    out=[]; p=0
    while True:
        r = sb.table(table).select("*").eq("season_id",SEASON).range(p*1000,(p+1)*1000-1).execute()
        if not r.data: break
        out += r.data
        if len(r.data) < 1000: break
        p += 1
    return out

def weight_pts(w, edible):
    w = float(w or 0); e = (edible or "").upper() == "Y"
    if e and w < 0.5: return 0.0
    if not e and w < 1.0: return 0.0
    return w * 4 if e else w

def is_sight(species):
    s = (species or "").lower()
    return "site fish" in s or "sight fish" in s or "gurnard" in s

def main():
    from supabase import create_client
    sb = create_client(*creds())
    OUT.mkdir(parents=True, exist_ok=True)

    anglers = sb.table("anglers").select("*").eq("season_id",SEASON).execute().data
    name = {a["wp_no"]: f"{a['first_name']} {a['surname']}".strip() for a in anglers}
    club = {a["wp_no"]: a.get("club","") for a in anglers}
    div  = {a["wp_no"]: a.get("league_code","") for a in anglers}

    scored = fetch_all(sb, "catches_scored")
    comps = sorted({r["comp_id"] for r in scored}, key=lambda x:(len(x),x))

    # weight points & fish counts per (wp, comp)
    wp_pc   = collections.defaultdict(float)   # (wp,comp)->weight pts
    fish_pc = collections.defaultdict(int)     # (wp,comp)->qualifying fish count
    for r in scored:
        wp, c = r["wp_no"], r["comp_id"]
        p = weight_pts(r["weight_kg"], r["edible"])
        wp_pc[(wp,c)] += p
        if p > 0 and not is_sight(r.get("canonical_species","")):
            fish_pc[(wp,c)] += 1

    # max weight pts per comp (overall pool)
    max_c = collections.defaultdict(float)
    for (wp,c), p in wp_pc.items():
        max_c[c] = max(max_c[c], p)

    # GP points per (wp, comp)
    gp_pc = {}
    for (wp,c), p in wp_pc.items():
        gp_pc[(wp,c)] = (p / max_c[c] * GP_MAX) if max_c[c] > 0 else 0.0

    # everyone who has any catch
    all_wps = sorted({wp for (wp,_) in wp_pc})

    def season_weight(wp):  return sum(wp_pc.get((wp,c),0) for c in comps)
    def season_gp(wp, best=None):
        vals = sorted((gp_pc.get((wp,c),0.0) for c in comps), reverse=True)
        return sum(vals[:best]) if best else sum(vals)
    def season_fish(wp):    return sum(fish_pc.get((wp,c),0) for c in comps)
    def season_gpfish(wp, best=None):
        # GP base + fish points (additive after GP), best-N applies to the per-IC (gp+fish) total
        per = [gp_pc.get((wp,c),0.0) + fish_pc.get((wp,c),0) for c in comps]
        per = sorted(per, reverse=True)
        return sum(per[:best]) if best else sum(per)

    rows = []
    for wp in all_wps:
        rows.append({
            "wp_no": wp, "name": name.get(wp,wp), "club": club.get(wp,""), "div": div.get(wp,""),
            "weight_pts": round(season_weight(wp),2),
            "gp_all8":    round(season_gp(wp),2),
            "gp_best7":   round(season_gp(wp,7),2),
            "fish_pts":   season_fish(wp),
            "gpfish_all8":round(season_gpfish(wp),2),
            "ics_fished": sum(1 for c in comps if (wp,c) in wp_pc),
            "ics_blobbed":sum(1 for c in comps if (wp,c) not in wp_pc or wp_pc[(wp,c)]==0),
        })

    def rank(rows, key):
        s = sorted(rows, key=lambda r: r[key], reverse=True)
        return {r["wp_no"]: i+1 for i,r in enumerate(s)}

    r_w   = rank(rows,"weight_pts")
    r_gp  = rank(rows,"gp_all8")
    r_gp7 = rank(rows,"gp_best7")
    r_gpf = rank(rows,"gpfish_all8")
    for r in rows:
        r["rank_weight"] = r_w[r["wp_no"]]
        r["rank_gp"]     = r_gp[r["wp_no"]]
        r["rank_gp7"]    = r_gp7[r["wp_no"]]
        r["rank_gpfish"] = r_gpf[r["wp_no"]]
        r["move_w_to_gp"]= r_w[r["wp_no"]] - r_gp[r["wp_no"]]  # +ve = moved up

    rows.sort(key=lambda r: r["weight_pts"], reverse=True)
    cols = ["rank_weight","rank_gp","rank_gp7","rank_gpfish","move_w_to_gp",
            "wp_no","name","club","div","weight_pts","gp_all8","gp_best7",
            "fish_pts","gpfish_all8","ics_fished","ics_blobbed"]
    with (OUT/"gp_full.csv").open("w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

    print(f"Anglers: {len(rows)}  ICs: {comps}")
    print(f"\nTop 25 by WEIGHT points — weight rank vs GP rank (all-8):\n")
    print(f"{'WgtR':>4} {'GPR':>4} {'Move':>5}  {'Name':<26} {'Club':<11} {'Wgt':>8} {'GP':>7} {'Fish':>4} {'Blob':>4}")
    for r in rows[:25]:
        mv = r["move_w_to_gp"]; mvs = f"+{mv}" if mv>0 else (str(mv) if mv<0 else "=")
        print(f"{r['rank_weight']:>4} {r['rank_gp']:>4} {mvs:>5}  {r['name'][:26]:<26} {r['club'][:11]:<11} "
              f"{r['weight_pts']:>8.1f} {r['gp_all8']:>7.1f} {r['fish_pts']:>4} {r['ics_blobbed']:>4}")

    # Biggest movers
    print("\nBiggest RISERS (weight->GP):")
    for r in sorted(rows, key=lambda r: -r["move_w_to_gp"])[:6]:
        print(f"  #{r['rank_weight']}->#{r['rank_gp']} (+{r['move_w_to_gp']})  {r['name']} [{r['club']}] blobs={r['ics_blobbed']}")
    print("\nBiggest FALLERS (weight->GP):")
    for r in sorted(rows, key=lambda r: r["move_w_to_gp"])[:6]:
        print(f"  #{r['rank_weight']}->#{r['rank_gp']} ({r['move_w_to_gp']})  {r['name']} [{r['club']}] blobs={r['ics_blobbed']} fished={r['ics_fished']}")

if __name__ == "__main__":
    main()
