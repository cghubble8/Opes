import { Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, ComposedChart } from 'recharts'

function buildChartData(chartData) {
  if (!chartData?.dates) return []
  return chartData.dates.map((date, i) => ({
    date:  date.slice(5), // MM-DD
    price: chartData.closes[i],
    sma:   chartData.sma_20[i],
    upper: chartData.bollinger_upper[i],
    lower: chartData.bollinger_lower[i],
  })).reverse()
}

export default function PriceChart({ symbol, chartData }) {
  const data = buildChartData(chartData)

  return (
    <div className="card chart-card">
      <h3>{symbol} — 1 Year Price History</h3>
      <div className="chart-legend">
        <span className="legend-item"><span className="legend-swatch legend-price"></span>Price</span>
        <span className="legend-item"><span className="legend-swatch legend-sma"></span>SMA 20</span>
        <span className="legend-item"><span className="legend-swatch legend-upper-bb"></span>Upper BB</span>
        <span className="legend-item"><span className="legend-swatch legend-lower-bb"></span>Lower BB</span>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <defs>
              <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#C9A84C" stopOpacity={0.28} />
                <stop offset="95%" stopColor="#C9A84C" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(201,168,76,0.08)" />
            <XAxis dataKey="date" stroke="#5C5248" fontSize={11} tick={{ fill: '#5C5248' }} />
            <YAxis stroke="#5C5248" fontSize={11} tick={{ fill: '#5C5248' }} domain={['auto', 'auto']} width={52} />
            <Tooltip
              contentStyle={{
                background: '#1a1a1a',
                border: '1px solid rgba(201,168,76,0.22)',
                borderRadius: '10px',
                color: '#F0EAD6',
                fontSize: '0.8125rem',
              }}
              labelStyle={{ color: '#A89880', marginBottom: '4px' }}
            />
            <Area type="monotone" dataKey="upper" stroke="none" fill="rgba(255,96,88,0.06)" />
            <Area type="monotone" dataKey="lower" stroke="none" fill="#080808" />
            <Line type="monotone" dataKey="upper" stroke="#FF6058" strokeDasharray="5 5" dot={false} strokeWidth={1} opacity={0.7} />
            <Line type="monotone" dataKey="lower" stroke="#34D27A" strokeDasharray="5 5" dot={false} strokeWidth={1} opacity={0.7} />
            <Line type="monotone" dataKey="sma"   stroke="#E2C27A" dot={false} strokeWidth={1.5} opacity={0.85} />
            <Area type="monotone" dataKey="price" stroke="#C9A84C" fill="url(#priceGradient)" strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
