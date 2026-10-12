"""Generates architecture.png and architecture.svg (run: python make_diagram.py). Edit the coordinates/text below to change the diagram."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

W, H = 20, 11.6
fig, ax = plt.subplots(figsize=(W, H)); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
fig.patch.set_facecolor("white")

C = dict(local=("#EEF2F7", "#7A8CA3"), storage=("#FFE8CC", "#D9822B"), adf=("#D5F2EE", "#1F9D8F"),
         compute=("#D6E6FF", "#2F6FD0"), table=("#DDF3DD", "#3E9B4F"), link=("#EBDDFB", "#8A4FD0"),
         planned=("#F3F3F3", "#8C8C8C"), grey=("#EFEFEF", "#9A9A9A"), sql=("#FFF3C4", "#C99A00"))
INK = "#1F2933"

def band(x, y, w, h, label, fc="#F7F9FC", ec="#C5CFDC"):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=1.4, zorder=0))
    ax.text(x + 0.2, y + h - 0.28, label, fontsize=11.5, fontweight="bold", color="#3B4A5C", va="center", zorder=2)

def box(x, y, w, h, title, lines, kind, dashed=False, ts=11, ls=9):
    fc, ec = C[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=ec, lw=2,
                                ls=(0, (5, 3)) if dashed else "-", zorder=2))
    ax.text(x + w / 2, y + h - 0.27, title, ha="center", va="center", fontsize=ts, fontweight="bold", color=INK, zorder=3)
    for i, t in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.62 - i * 0.27, t, ha="center", va="center", fontsize=ls, color=INK, zorder=3)

def route(pts, color="#33475B", dashed=False, label=None, lpos=None, lalign="center"):
    xs, ys = zip(*pts)
    ax.plot(xs[:-1], ys[:-1], color=color, lw=2, ls=(0, (5, 3)) if dashed else "-", zorder=1, solid_capstyle="butt")
    ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops=dict(arrowstyle="-|>", color=color, lw=2,
                ls=(0, (5, 3)) if dashed else "-", shrinkA=0, shrinkB=0), zorder=4)
    if label:
        ax.text(*lpos, label, fontsize=9, color=color, ha=lalign, va="center", style="italic", zorder=5,
                bbox=dict(fc="white", ec="none", pad=1.2, alpha=0.9))

# ---------- title ----------
ax.text(W / 2, 11.18, "End-to-End Retail Data Engineering Pipeline", ha="center", fontsize=21, fontweight="bold", color=INK)
ax.text(W / 2, 10.78, "Azure Data Factory  |  ADLS Gen2  |  Microsoft Fabric Lakehouse (PySpark, Delta)  |  SQL analytics endpoint  -  Olist data prepared as simulated monthly batches",
        ha="center", fontsize=11, color="#52606D")

# ---------- band A: local ----------
band(0.4, 8.7, 19.2, 1.75, "1  LOCAL MACHINE  -  VS Code + Python")
box(0.8, 8.9, 4.6, 1.15, "Kaggle Olist dataset", ["9 original CSV files", "(static, historical public data)"], "local")
box(6.6, 8.9, 5.8, 1.15, "prepare_olist_batches.py", ["splits into monthly batch_date folders; injects duplicates,", "status updates and bad rows (simulated)"], "local")
box(13.6, 8.9, 5.6, 1.15, "Source batches + manifest.json", ["103 CSV files", "expected row / batch counts"], "local")
route([(5.4, 9.475), (6.6, 9.475)]); route([(12.4, 9.475), (13.6, 9.475)])

# ---------- band B: Azure storage + ADF ----------
band(0.4, 4.7, 19.2, 3.55, "2  AZURE  -  ADLS Gen2 (container 'retail')  +  Azure Data Factory")
box(0.8, 6.0, 4.6, 1.4, "source/", ["monthly batch folders", "+ manifest.json"], "storage")
box(6.8, 6.0, 5.4, 1.4, "Azure Data Factory", ["pipeline: pl_retail_source_to_bronze", "Copy Data activity", "linked service: system-assigned managed identity"], "adf")
box(13.6, 6.0, 5.6, 1.4, "bronze/  (landing copy)", ["103 CSV files copied by ADF", "not read by Notebook 01 (current design)"], "storage")
box(13.6, 4.9, 5.6, 0.85, "silver/  gold/  ops/  serving/", ["directories exist; not populated by the notebooks"], "grey")
route([(5.4, 6.7), (6.8, 6.7)]); route([(12.2, 6.7), (13.6, 6.7)])
route([(16.4, 8.9), (16.4, 8.48), (3.1, 8.48), (3.1, 7.4)], label="uploaded from the local machine to source/", lpos=(9.8, 8.48))
ax.text(9.5, 5.3, "Ingestion (ADF) and transformation (Fabric notebooks) are separate steps.\nADF does not trigger the notebooks; they are run manually in order 01 -> 02 -> 03.",
        ha="center", va="center", fontsize=9.5, style="italic", color="#52606D")

# ---------- band C: Fabric ----------
band(0.4, 0.95, 19.2, 3.45, "3  MICROSOFT FABRIC  -  workspace 'project1'  |  Lakehouse 'lh_retail_lakehouse' (OneLake)")
x0, step, w, y, h = 0.7, 2.06, 1.84, 1.75, 1.75
X = [x0 + i * step for i in range(9)]
T = dict(ts=10.2, ls=8.4)
box(X[0], y, w, h, "Shortcut 'retail'", ["Lakehouse link", "to ADLS source/", "virtual reference;", "no data is copied"], "link", **T)
box(X[1], y, w, h, "Notebook 01", ["Bronze ingestion", "raw strings +", "lineage columns", "manifest checks"], "compute", **T)
box(X[2], y, w, h, "bronze_*  (9)", ["managed Delta", "tables", "full refresh"], "table", **T)
box(X[3], y, w, h, "Notebook 02", ["Silver transform", "types, rules,", "quarantine, dedup,", "reconciliation"], "compute", **T)
box(X[4], y, w, h, "silver_*  (9)", ["quarantine_*  (9)", "managed Delta", "tables"], "table", **T)
box(X[5], y, w, h, "Notebook 03", ["Silver to Gold", "dimensions, facts,", "analytics tables,", "19 checks"], "compute", **T)
box(X[6], y, w, h, "gold_*  (11)", ["4 dimensions", "2 facts", "5 analytics tables"], "table", **T)
box(X[7], y, w, h, "SQL analytics", ["endpoint (T-SQL)", "analytics Q1-Q11", "read-only,", "no data copied"], "sql", **T)
box(X[8], y, w, h, "Power BI", ["report on gold_*", "next step -", "not yet built"], "planned", dashed=True, **T)
for i in range(8):
    nxt_planned = (i == 7)
    route([(X[i] + w, y + h / 2), (X[i + 1], y + h / 2)], dashed=nxt_planned, color="#8C8C8C" if nxt_planned else "#33475B")
route([(1.62, 6.0), (1.62, 3.5)], color="#8A4FD0", label="read through\nthe shortcut", lpos=(1.72, 4.72), lalign="left")

# ---------- legend ----------
items = [("Local files", "local", False), ("ADLS directories", "storage", False), ("Azure Data Factory", "adf", False),
         ("Fabric notebooks", "compute", False), ("Managed Delta tables", "table", False), ("Shortcut", "link", False),
         ("SQL analytics endpoint", "sql", False), ("Planned (not built)", "planned", True)]
lx = 0.55
for name, kind, dashed in items:
    fc, ec = C[kind]
    ax.add_patch(FancyBboxPatch((lx, 0.3), 0.32, 0.26, boxstyle="round,pad=0.01,rounding_size=0.05", fc=fc, ec=ec, lw=1.8,
                                ls=(0, (4, 2)) if dashed else "-"))
    ax.text(lx + 0.42, 0.43, name, fontsize=9.3, va="center", color=INK)
    lx += 0.55 + len(name) * 0.085 + 0.3
fig.savefig("architecture.png", dpi=150, bbox_inches="tight", facecolor="white")
fig.savefig("architecture.svg", bbox_inches="tight", facecolor="white")
print("saved architecture.png / architecture.svg")
