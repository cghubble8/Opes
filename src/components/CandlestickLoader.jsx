/**
 * CandlestickLoader
 * A stock-themed animated loading component using SVG candlesticks.
 */
function CandlestickLoader({ message = 'Loading...' }) {
  // Static candle data: [bodyBottom%, bodyTop%, wickBottom%, wickTop%, bullish?]
  // Values are percentages of the SVG height (0 = top, 100 = bottom for SVG coords)
  const candles = [
    { x: 18, bodyLo: 55, bodyHi: 30, wickLo: 75, wickHi: 18, bull: false, delay: 0 },
    { x: 38, bodyLo: 65, bodyHi: 40, wickLo: 80, wickHi: 28, bull: true, delay: 0.12 },
    { x: 58, bodyLo: 50, bodyHi: 20, wickLo: 68, wickHi: 10, bull: true, delay: 0.24 },
    { x: 78, bodyLo: 60, bodyHi: 38, wickLo: 78, wickHi: 26, bull: false, delay: 0.36 },
    { x: 98, bodyLo: 45, bodyHi: 15, wickLo: 60, wickHi: 5, bull: true, delay: 0.48 },
    { x: 118, bodyLo: 55, bodyHi: 30, wickLo: 72, wickHi: 18, bull: true, delay: 0.60 },
    { x: 138, bodyLo: 65, bodyHi: 42, wickLo: 82, wickHi: 30, bull: false, delay: 0.72 },
  ]

  const svgH = 100
  const bodyW = 12
  const wickW = 2

  // Convert % to px within an 80px tall drawing area, offset by 10px top margin
  const toY = (pct) => 10 + (pct / 100) * 80

  return (
    <div className="cs-loader-wrap">
      <div className="cs-loader-card">
        {/* Glow blob behind animation */}
        <div className="cs-glow" />

        {/* SVG candlestick animation */}
        <svg
          className="cs-svg"
          viewBox={`0 0 160 ${svgH}`}
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* Subtle baseline grid lines */}
          {[25, 50, 75].map(y => (
            <line
              key={y}
              x1="0" y1={toY(y)}
              x2="160" y2={toY(y)}
              stroke="rgba(255,255,255,0.04)"
              strokeWidth="1"
            />
          ))}

          {candles.map((c, i) => {
            const green = '#10b981'
            const red = '#ef4444'
            const colour = c.bull ? green : red

            const bodyTop = toY(c.bodyHi)
            const bodyBottom = toY(c.bodyLo)
            const bodyHeight = bodyBottom - bodyTop

            const wickTop = toY(c.wickHi)
            const wickBottom = toY(c.wickLo)

            const animStyle = {
              animationDelay: `${c.delay}s`,
            }

            return (
              <g key={i} className="cs-candle" style={animStyle}>
                {/* Wick */}
                <rect
                  x={c.x - wickW / 2}
                  y={wickTop}
                  width={wickW}
                  height={wickBottom - wickTop}
                  fill={colour}
                  opacity="0.6"
                  rx="1"
                />
                {/* Body */}
                <rect
                  x={c.x - bodyW / 2}
                  y={bodyTop}
                  width={bodyW}
                  height={bodyHeight}
                  fill={colour}
                  rx="2"
                />
                {/* Shine overlay on body */}
                <rect
                  x={c.x - bodyW / 2}
                  y={bodyTop}
                  width={bodyW / 2}
                  height={bodyHeight}
                  fill="rgba(255,255,255,0.07)"
                  rx="2"
                />
              </g>
            )
          })}
        </svg>

        {/* Scanning line */}
        <div className="cs-scan-line" />

        {/* Label */}
        <p className="cs-message">{message}</p>

        {/* Dot trail */}
        <div className="cs-dots">
          <span className="cs-dot" style={{ animationDelay: '0s' }} />
          <span className="cs-dot" style={{ animationDelay: '0.2s' }} />
          <span className="cs-dot" style={{ animationDelay: '0.4s' }} />
        </div>
      </div>
    </div>
  )
}

export default CandlestickLoader
