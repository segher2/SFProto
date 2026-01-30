from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# Paths
# =========================

CSV_PATH = Path("bench_out_bag/results.csv")
FIG_DIR = Path("bench_out_bag/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# Load data
# =========================

df = pd.read_csv(CSV_PATH)

# Consistent ordering for plots
CODEC_ORDER = ["bag_v3", "v4", "v7"]
df["codec"] = pd.Categorical(df["codec"], CODEC_ORDER, ordered=True)

# =========================
# 1. Size comparison
# =========================

size_df = (
    df.groupby("codec")["size_bytes"]
    .min()  # size is constant per codec
    .reset_index()
)

plt.figure()
plt.bar(size_df["codec"], size_df["size_bytes"] / 1024 / 1024)
plt.ylabel("Size (MB)")
plt.xlabel("Codec")
plt.title("Serialized size comparison (GeoJSON FeatureCollection)")
plt.tight_layout()
plt.savefig(FIG_DIR / "size_comparison.png", dpi=300)
plt.close()

# =========================
# 2. CPU encode/decode (BAR PLOT)
# =========================

cpu_df = df.query("stage == 'cpu'")

pivot = cpu_df.pivot(
    index="codec",
    columns="phase",
    values="mean_ms"
).loc[CODEC_ORDER]

ax = pivot.plot(
    kind="bar",
    width=0.75,
)

ax.set_ylabel("Mean time (ms)")
ax.set_xlabel("Codec")
ax.set_title("CPU performance: encode vs decode")
ax.legend(title="Phase")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(FIG_DIR / "cpu_encode_decode.png", dpi=300)
plt.close()


# =========================
# 3. Raw IO throughput (BAR PLOT)
# =========================

io_df = df.query("stage == 'raw_io'").copy()

io_df["throughput_MBps"] = (
    io_df["size_bytes"] / (1024 * 1024)
) / (io_df["mean_ms"] / 1000)

pivot = io_df.pivot_table(
    index="codec",
    columns="phase",
    values="throughput_MBps",
    aggfunc="mean",
).loc[CODEC_ORDER]

ax = pivot.plot(
    kind="bar",
    width=0.75,
)

ax.set_ylabel("Throughput (MB/s)")
ax.set_xlabel("Codec")
ax.set_title("Raw disk IO throughput")
ax.legend(title="Phase")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(FIG_DIR / "raw_io_throughput.png", dpi=300)
plt.close()


# =========================
# 4. End-to-end times (BAR PLOT)
# =========================

e2e_df = df.query("stage == 'end_to_end'")

pivot = e2e_df.pivot_table(
    index="codec",
    columns="phase",
    values="mean_ms",
    aggfunc="mean",
).loc[CODEC_ORDER]

ax = pivot.plot(
    kind="bar",
    width=0.75,
)

ax.set_ylabel("Mean time (ms)")
ax.set_xlabel("Codec")
ax.set_title("End-to-end performance (serialize + IO)")
ax.legend(title="Phase")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(FIG_DIR / "end_to_end_times.png", dpi=300)
plt.close()



print(f"Figures written to: {FIG_DIR.resolve()}")
