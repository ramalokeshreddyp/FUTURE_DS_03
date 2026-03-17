from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


DEFAULT_DATASET_CANDIDATES = [
    Path("data/bank-full.csv"),
    Path(r"c:\Users\lokes\Downloads\bank+marketing\bank\bank-full.csv"),
]

MONTH_ORDER = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
CAMPAIGN_BUCKETS = ([0, 1, 2, 3, 5, 10, 100], ["1", "2", "3", "4-5", "6-10", "11+"])
DURATION_BUCKETS = ([0, 60, 120, 180, 300, 600, 20000], ["0-59s", "60-119s", "120-179s", "180-299s", "300-599s", "600s+"])


def locate_dataset(explicit_path: str | None) -> Path:
    if explicit_path:
        dataset_path = Path(explicit_path)
        if dataset_path.exists():
            return dataset_path
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    for candidate in DEFAULT_DATASET_CANDIDATES:
        if candidate.exists():
            return candidate

    searched = "\n".join(str(candidate) for candidate in DEFAULT_DATASET_CANDIDATES)
    raise FileNotFoundError(f"Could not find bank marketing dataset. Checked:\n{searched}")


def load_and_prepare_data(dataset_path: Path) -> pd.DataFrame:
    data = pd.read_csv(dataset_path, sep=";")
    data["converted"] = data["y"].eq("yes")
    data["known_channel"] = data["contact"].ne("unknown")
    data["engaged_call"] = data["duration"].ge(120)
    data["month"] = pd.Categorical(data["month"], categories=MONTH_ORDER, ordered=True)
    data["campaign_bucket"] = pd.cut(data["campaign"], bins=CAMPAIGN_BUCKETS[0], labels=CAMPAIGN_BUCKETS[1])
    data["duration_bucket"] = pd.cut(
        data["duration"],
        bins=DURATION_BUCKETS[0],
        labels=DURATION_BUCKETS[1],
        right=False,
    )
    return data


def summarize_funnel(data: pd.DataFrame) -> pd.DataFrame:
    stage_counts = [
        ("Targeted customers", len(data)),
        ("Known channel reached", int(data["known_channel"].sum())),
        ("Engaged calls (>=120s)", int(data["engaged_call"].sum())),
        ("Subscribed customers", int(data["converted"].sum())),
    ]

    rows: list[dict[str, float | int | str]] = []
    previous_count = None
    base_count = stage_counts[0][1]
    for stage, count in stage_counts:
        rows.append(
            {
                "stage": stage,
                "count": count,
                "conversion_from_previous_pct": round((count / previous_count) * 100, 2) if previous_count else 100.0,
                "drop_off_from_previous_pct": round((1 - (count / previous_count)) * 100, 2) if previous_count else 0.0,
                "conversion_from_targeted_pct": round((count / base_count) * 100, 2),
            }
        )
        previous_count = count

    return pd.DataFrame(rows)


def summarize_segments(data: pd.DataFrame, dimension: str) -> pd.DataFrame:
    summary = (
        data.groupby(dimension, observed=False)
        .agg(
            records=("converted", "size"),
            conversions=("converted", "sum"),
            conversion_rate=("converted", "mean"),
            avg_duration=("duration", "mean"),
            median_duration=("duration", "median"),
        )
        .reset_index()
    )
    summary["conversion_rate"] = (summary["conversion_rate"] * 100).round(2)
    summary["avg_duration"] = summary["avg_duration"].round(1)
    summary["median_duration"] = summary["median_duration"].round(1)
    return summary.sort_values("conversion_rate", ascending=False)


def build_key_metrics(data: pd.DataFrame, funnel_summary: pd.DataFrame) -> dict[str, float | int | str]:
    conversion_rate = round(data["converted"].mean() * 100, 2)
    known_rate = round(data["known_channel"].mean() * 100, 2)
    engaged_from_known = round(data.loc[data["known_channel"], "engaged_call"].mean() * 100, 2)
    customer_from_engaged = round(data.loc[data["engaged_call"], "converted"].mean() * 100, 2)

    contact_summary = summarize_segments(data, "contact")
    month_summary = summarize_segments(data, "month")
    prior_summary = summarize_segments(data, "poutcome")
    campaign_summary = summarize_segments(data, "campaign_bucket")

    best_channel = contact_summary.iloc[0]
    worst_channel = contact_summary.iloc[-1]
    best_month = month_summary.iloc[0]
    worst_month = month_summary.iloc[-1]
    prior_success = prior_summary.loc[prior_summary["poutcome"] == "success", "conversion_rate"].iloc[0]
    campaign_one = campaign_summary.loc[campaign_summary["campaign_bucket"] == "1", "conversion_rate"].iloc[0]
    campaign_eleven = campaign_summary.loc[campaign_summary["campaign_bucket"] == "11+", "conversion_rate"].iloc[0]

    return {
        "dataset_rows": int(len(data)),
        "dataset_columns": int(data.shape[1]),
        "overall_conversion_rate_pct": conversion_rate,
        "known_channel_rate_pct": known_rate,
        "engaged_from_known_pct": engaged_from_known,
        "customer_from_engaged_pct": customer_from_engaged,
        "largest_drop_off_stage": funnel_summary.sort_values("drop_off_from_previous_pct", ascending=False).iloc[0]["stage"],
        "best_channel": str(best_channel["contact"]),
        "best_channel_conversion_pct": float(best_channel["conversion_rate"]),
        "worst_channel": str(worst_channel["contact"]),
        "worst_channel_conversion_pct": float(worst_channel["conversion_rate"]),
        "best_month": str(best_month["month"]),
        "best_month_conversion_pct": float(best_month["conversion_rate"]),
        "worst_month": str(worst_month["month"]),
        "worst_month_conversion_pct": float(worst_month["conversion_rate"]),
        "prior_success_conversion_pct": float(prior_success),
        "single_touch_conversion_pct": float(campaign_one),
        "heavy_touch_conversion_pct": float(campaign_eleven),
    }


def create_dashboard(
    funnel_summary: pd.DataFrame,
    contact_summary: pd.DataFrame,
    month_summary: pd.DataFrame,
    prior_summary: pd.DataFrame,
    campaign_summary: pd.DataFrame,
    duration_summary: pd.DataFrame,
    output_file: Path,
) -> None:
    figure = make_subplots(
        rows=3,
        cols=2,
        specs=[
            [{"type": "funnel"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "xy"}],
        ],
        subplot_titles=(
            "Campaign Funnel Proxy",
            "Conversion Rate by Channel",
            "Conversion Rate by Month",
            "Conversion Rate by Prior Outcome",
            "Conversion Rate by Contact Frequency",
            "Conversion Rate by Call Duration",
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    figure.add_trace(
        go.Funnel(
            y=funnel_summary["stage"],
            x=funnel_summary["count"],
            text=[f"{value:,.0f}" for value in funnel_summary["count"]],
            textposition="inside",
            marker={"color": ["#264653", "#2a9d8f", "#e9c46a", "#e76f51"]},
            opacity=0.9,
        ),
        row=1,
        col=1,
    )

    figure.add_trace(
        go.Bar(
            x=contact_summary["contact"],
            y=contact_summary["conversion_rate"],
            marker_color=["#1d3557", "#457b9d", "#a8dadc"],
            text=contact_summary["conversion_rate"].map(lambda value: f"{value:.2f}%"),
            textposition="outside",
        ),
        row=1,
        col=2,
    )

    ordered_months = month_summary.sort_values("month")
    figure.add_trace(
        go.Scatter(
            x=ordered_months["month"],
            y=ordered_months["conversion_rate"],
            mode="lines+markers+text",
            line={"color": "#d62828", "width": 3},
            marker={"size": 8, "color": "#f77f00"},
            text=ordered_months["conversion_rate"].map(lambda value: f"{value:.1f}%"),
            textposition="top center",
        ),
        row=2,
        col=1,
    )

    prior_plot = prior_summary.sort_values("conversion_rate", ascending=False)
    figure.add_trace(
        go.Bar(
            x=prior_plot["poutcome"],
            y=prior_plot["conversion_rate"],
            marker_color="#2a9d8f",
            text=prior_plot["conversion_rate"].map(lambda value: f"{value:.2f}%"),
            textposition="outside",
        ),
        row=2,
        col=2,
    )

    campaign_plot = campaign_summary.sort_values("campaign_bucket")
    figure.add_trace(
        go.Bar(
            x=campaign_plot["campaign_bucket"],
            y=campaign_plot["conversion_rate"],
            marker_color="#6d597a",
            text=campaign_plot["conversion_rate"].map(lambda value: f"{value:.2f}%"),
            textposition="outside",
        ),
        row=3,
        col=1,
    )

    duration_plot = duration_summary.sort_values("duration_bucket")
    figure.add_trace(
        go.Bar(
            x=duration_plot["duration_bucket"],
            y=duration_plot["conversion_rate"],
            marker_color="#bc4749",
            text=duration_plot["conversion_rate"].map(lambda value: f"{value:.2f}%"),
            textposition="outside",
        ),
        row=3,
        col=2,
    )

    for row in [1, 2, 3]:
        for col in [1, 2]:
            if not (row == 1 and col == 1):
                figure.update_yaxes(title_text="Conversion rate (%)", row=row, col=col)

    figure.update_layout(
        title={
            "text": "Bank Marketing Funnel Performance Dashboard<br><sup>Proxy funnel built from campaign records: targeted -> known channel -> engaged call -> subscription</sup>",
            "x": 0.5,
        },
        template="plotly_white",
        height=1200,
        width=1500,
        showlegend=False,
        font={"family": "Segoe UI, Arial, sans-serif", "size": 13},
        margin={"t": 110, "l": 60, "r": 30, "b": 60},
        paper_bgcolor="#f8f5f0",
        plot_bgcolor="#ffffff",
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(output_file, include_plotlyjs="cdn")


def build_dashboard_payload(
    key_metrics: dict[str, float | int | str],
    funnel_summary: pd.DataFrame,
    contact_summary: pd.DataFrame,
    month_summary: pd.DataFrame,
    prior_summary: pd.DataFrame,
    campaign_summary: pd.DataFrame,
    duration_summary: pd.DataFrame,
    job_summary: pd.DataFrame,
) -> dict[str, object]:
    top_jobs = job_summary.sort_values("conversion_rate", ascending=False).head(6)
    insights = [
        {
            "title": "Late-stage drop-off dominates",
            "detail": "Only 16.24% of engaged calls convert, so the biggest revenue leak happens after the conversation already starts.",
        },
        {
            "title": "Known channels produce better lead quality",
            "detail": "Cellular converts at 14.92% while unknown contact records convert at just 4.07%, which points to contact-data quality as a real funnel lever.",
        },
        {
            "title": "Repeated contact shows diminishing returns",
            "detail": "Conversion falls from 14.60% on the first touch to 3.93% after 11+ attempts, so heavy follow-up is not efficient at scale.",
        },
        {
            "title": "Prior relationship success is a powerful targeting signal",
            "detail": "Customers with prior campaign success convert at 64.73%, making them prime candidates for tailored retention and reactivation playbooks.",
        },
    ]
    recommendations = [
        "Prioritize reachable prospects with known mobile channels and improve channel completeness on low-information records.",
        "Route prior-success customers into a dedicated high-intent segment instead of treating them like generic outreach leads.",
        "Audit the close motion for engaged calls because that is where the largest conversion loss still occurs.",
        "Set cadence review rules after 4 to 5 touches rather than allowing low-yield contact loops to continue indefinitely.",
    ]

    return {
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "metrics": key_metrics,
        "funnel": funnel_summary.to_dict(orient="records"),
        "channels": contact_summary.to_dict(orient="records"),
        "months": month_summary.sort_values("month").to_dict(orient="records"),
        "prior_outcomes": prior_summary.sort_values("conversion_rate", ascending=False).to_dict(orient="records"),
        "campaign_frequency": campaign_summary.sort_values("campaign_bucket").to_dict(orient="records"),
        "duration": duration_summary.sort_values("duration_bucket").to_dict(orient="records"),
        "top_jobs": top_jobs.to_dict(orient="records"),
        "insights": insights,
        "recommendations": recommendations,
    }


def copy_pages_assets(output_dir: Path, payload: dict[str, object]) -> None:
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    data_dir = docs_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    (data_dir / "dashboard_data.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_outputs(data: pd.DataFrame, output_dir: Path) -> dict[str, pd.DataFrame | dict[str, float | int | str]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    funnel_summary = summarize_funnel(data)
    contact_summary = summarize_segments(data, "contact")
    month_summary = summarize_segments(data, "month")
    prior_summary = summarize_segments(data, "poutcome")
    campaign_summary = summarize_segments(data, "campaign_bucket")
    duration_summary = summarize_segments(data, "duration_bucket")
    job_summary = summarize_segments(data, "job")
    key_metrics = build_key_metrics(data, funnel_summary)

    funnel_summary.to_csv(output_dir / "funnel_stage_summary.csv", index=False)
    contact_summary.to_csv(output_dir / "channel_performance.csv", index=False)
    month_summary.sort_values("month").to_csv(output_dir / "month_performance.csv", index=False)
    prior_summary.to_csv(output_dir / "prior_outcome_performance.csv", index=False)
    campaign_summary.sort_values("campaign_bucket").to_csv(output_dir / "campaign_frequency_performance.csv", index=False)
    duration_summary.sort_values("duration_bucket").to_csv(output_dir / "duration_performance.csv", index=False)
    job_summary.to_csv(output_dir / "job_performance.csv", index=False)
    (output_dir / "key_metrics.json").write_text(json.dumps(key_metrics, indent=2), encoding="utf-8")

    create_dashboard(
        funnel_summary=funnel_summary,
        contact_summary=contact_summary,
        month_summary=month_summary,
        prior_summary=prior_summary,
        campaign_summary=campaign_summary,
        duration_summary=duration_summary,
        output_file=Path("docs") / "plotly-dashboard.html",
    )
    dashboard_payload = build_dashboard_payload(
        key_metrics=key_metrics,
        funnel_summary=funnel_summary,
        contact_summary=contact_summary,
        month_summary=month_summary,
        prior_summary=prior_summary,
        campaign_summary=campaign_summary,
        duration_summary=duration_summary,
        job_summary=job_summary,
    )
    copy_pages_assets(output_dir, dashboard_payload)

    return {
        "funnel_summary": funnel_summary,
        "contact_summary": contact_summary,
        "month_summary": month_summary,
        "prior_summary": prior_summary,
        "campaign_summary": campaign_summary,
        "duration_summary": duration_summary,
        "job_summary": job_summary,
        "key_metrics": key_metrics,
        "dashboard_payload": dashboard_payload,
    }


def print_console_summary(results: dict[str, pd.DataFrame | dict[str, float | int | str]]) -> None:
    key_metrics = results["key_metrics"]
    assert isinstance(key_metrics, dict)
    print("Bank Marketing Funnel Analysis")
    print("-" * 32)
    print(f"Rows analyzed: {key_metrics['dataset_rows']:,}")
    print(f"Overall conversion: {key_metrics['overall_conversion_rate_pct']}%")
    print(f"Known-channel reach: {key_metrics['known_channel_rate_pct']}%")
    print(f"Engaged-to-customer conversion: {key_metrics['customer_from_engaged_pct']}%")
    print(f"Best channel: {key_metrics['best_channel']} ({key_metrics['best_channel_conversion_pct']}%)")
    print(f"Best month: {key_metrics['best_month']} ({key_metrics['best_month_conversion_pct']}%)")
    print(f"Prior success segment conversion: {key_metrics['prior_success_conversion_pct']}%")
    print(f"Single-touch conversion: {key_metrics['single_touch_conversion_pct']}%")
    print(f"Heavy-touch conversion: {key_metrics['heavy_touch_conversion_pct']}%")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze bank marketing conversion funnel performance.")
    parser.add_argument("--dataset", help="Path to the bank marketing CSV file.")
    parser.add_argument("--output-dir", default="outputs", help="Directory where outputs will be written.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = locate_dataset(args.dataset)
    data = load_and_prepare_data(dataset_path)
    results = export_outputs(data, Path(args.output_dir))
    print_console_summary(results)


if __name__ == "__main__":
    main()