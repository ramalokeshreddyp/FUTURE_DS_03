const plotlyTheme = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Source Sans 3, sans-serif', color: '#1f2a2f', size: 13 },
  margin: { t: 24, r: 20, b: 48, l: 48 },
};

const metricCards = [
  { label: 'Overall conversion', key: 'overall_conversion_rate_pct', suffix: '%' },
  { label: 'Known-channel reach', key: 'known_channel_rate_pct', suffix: '%' },
  { label: 'Engaged to customer', key: 'customer_from_engaged_pct', suffix: '%' },
  { label: 'Best channel rate', key: 'best_channel_conversion_pct', suffix: '%' },
];

function formatValue(value, suffix = '') {
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;
}

function createMetricCard(label, value) {
  const card = document.createElement('article');
  card.className = 'metric-card';
  card.innerHTML = `<p>${label}</p><strong>${value}</strong>`;
  return card;
}

function createInsightCard(insight) {
  const card = document.createElement('article');
  card.className = 'insight-card';
  card.innerHTML = `<h3>${insight.title}</h3><p>${insight.detail}</p>`;
  return card;
}

function createRecommendationCard(text, index) {
  const card = document.createElement('article');
  card.className = 'recommendation-item';
  card.innerHTML = `<h3>Action ${index + 1}</h3><p>${text}</p>`;
  return card;
}

function renderMetricStrip(metrics) {
  const container = document.getElementById('metric-grid');
  metricCards.forEach((item) => {
    container.appendChild(createMetricCard(item.label, formatValue(metrics[item.key], item.suffix)));
  });
}

function renderNarrative(data) {
  const { metrics } = data;
  document.getElementById('dropoff-stage').textContent = metrics.largest_drop_off_stage;
  document.getElementById('dropoff-summary').textContent = 'This is the largest drop-off stage in the funnel and the highest-leverage place to improve close rates.';
  document.getElementById('overall-conversion').textContent = formatValue(metrics.overall_conversion_rate_pct, '%');
  document.getElementById('known-reach').textContent = formatValue(metrics.known_channel_rate_pct, '%');

  const insightGrid = document.getElementById('insight-grid');
  data.insights.forEach((insight) => insightGrid.appendChild(createInsightCard(insight)));

  const recommendationList = document.getElementById('recommendation-list');
  data.recommendations.forEach((recommendation, index) => {
    recommendationList.appendChild(createRecommendationCard(recommendation, index));
  });
}

function renderFunnelChart(funnel) {
  Plotly.newPlot('funnel-chart', [{
    type: 'funnel',
    y: funnel.map((row) => row.stage),
    x: funnel.map((row) => row.count),
    text: funnel.map((row) => `${row.count.toLocaleString()}<br>${row.conversion_from_targeted_pct}% of targeted`),
    textposition: 'inside',
    marker: { color: ['#183153', '#0f766e', '#d2a63f', '#d95d39'] },
    opacity: 0.95,
    hovertemplate: '%{y}<br>Count: %{x:,}<br>%{text}<extra></extra>',
  }], {
    ...plotlyTheme,
    margin: { t: 24, r: 24, b: 36, l: 24 },
  }, { responsive: true, displayModeBar: false });
}

function renderBarChart(target, data, xKey, yKey, color, orientation = 'v', tickSuffix = '%') {
  Plotly.newPlot(target, [{
    type: 'bar',
    orientation,
    x: orientation === 'v' ? data.map((row) => row[xKey]) : data.map((row) => row[yKey]),
    y: orientation === 'v' ? data.map((row) => row[yKey]) : data.map((row) => row[xKey]),
    marker: {
      color,
      line: { color: 'rgba(24,49,83,0.15)', width: 1 },
    },
    customdata: data.map((row) => row.records ?? null),
    text: data.map((row) => `${row[yKey]}${tickSuffix}`),
    textposition: orientation === 'v' ? 'outside' : 'auto',
    hovertemplate: orientation === 'v'
      ? '%{x}<br>Conversion: %{y}%<br>Records: %{customdata:,}<extra></extra>'
      : '%{y}<br>Conversion: %{x}%<br>Records: %{customdata:,}<extra></extra>',
  }], {
    ...plotlyTheme,
    yaxis: orientation === 'v' ? { title: 'Conversion rate (%)', gridcolor: 'rgba(24,49,83,0.08)' } : { automargin: true },
    xaxis: orientation === 'v' ? { automargin: true } : { title: 'Conversion rate (%)', gridcolor: 'rgba(24,49,83,0.08)' },
  }, { responsive: true, displayModeBar: false });
}

function renderMonthChart(months) {
  Plotly.newPlot('month-chart', [{
    type: 'bar',
    x: months.map((row) => row.month),
    y: months.map((row) => row.records),
    marker: { color: 'rgba(24,49,83,0.22)' },
    yaxis: 'y2',
    name: 'Volume',
    hovertemplate: '%{x}<br>Records: %{y:,}<extra></extra>',
  }, {
    type: 'scatter',
    mode: 'lines+markers',
    x: months.map((row) => row.month),
    y: months.map((row) => row.conversion_rate),
    line: { color: '#d95d39', width: 4, shape: 'spline' },
    marker: { color: '#183153', size: 9 },
    name: 'Conversion',
    hovertemplate: '%{x}<br>Conversion: %{y}%<extra></extra>',
  }], {
    ...plotlyTheme,
    yaxis: { title: 'Conversion rate (%)', gridcolor: 'rgba(24,49,83,0.08)' },
    yaxis2: { title: 'Records', overlaying: 'y', side: 'right', showgrid: false },
    xaxis: { automargin: true },
    legend: { orientation: 'h', x: 0.02, y: 1.16 },
  }, { responsive: true, displayModeBar: false });
}

function renderCampaignChart(campaignFrequency) {
  Plotly.newPlot('campaign-chart', [{
    type: 'scatter',
    mode: 'lines+markers',
    x: campaignFrequency.map((row) => row.campaign_bucket),
    y: campaignFrequency.map((row) => row.conversion_rate),
    line: { color: '#6b8f71', width: 3 },
    marker: { color: '#0f766e', size: 10, symbol: 'diamond' },
    hovertemplate: '%{x} touches<br>Conversion: %{y}%<extra></extra>',
  }], {
    ...plotlyTheme,
    yaxis: { title: 'Conversion rate (%)', gridcolor: 'rgba(24,49,83,0.08)' },
    xaxis: { title: 'Touch bucket' },
  }, { responsive: true, displayModeBar: false });
}

async function loadDashboardData() {
  const response = await fetch('./data/dashboard_data.json', { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Failed to load dashboard data.');
  }
  return response.json();
}

async function main() {
  try {
    const data = await loadDashboardData();
    renderMetricStrip(data.metrics);
    renderNarrative(data);
    renderFunnelChart(data.funnel);
    renderBarChart('channel-chart', data.channels, 'contact', 'conversion_rate', ['#183153', '#0f766e', '#89c2b7']);
    renderMonthChart(data.months);
    renderBarChart('prior-chart', data.prior_outcomes, 'poutcome', 'conversion_rate', '#d2a63f');
    renderCampaignChart(data.campaign_frequency);
    renderBarChart('duration-chart', data.duration, 'duration_bucket', 'conversion_rate', '#d95d39');
    renderBarChart('jobs-chart', data.top_jobs, 'job', 'conversion_rate', '#183153', 'h');
  } catch (error) {
    console.error(error);
    document.getElementById('metric-grid').innerHTML = '<article class="metric-card"><p>Dashboard data failed to load. Re-run the analysis script to regenerate docs/data/dashboard_data.json.</p></article>';
  }
}

main();