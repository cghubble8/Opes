function pillarClass(score) {
  return score > 70 ? 'high' : score > 50 ? 'medium' : 'low'
}

export default function PredictionCard({ prediction, news }) {
  const direction = prediction?.direction

  return (
    <div className={`card prediction-card ${direction === 'bullish' ? 'bullish-glow' : direction === 'bearish' ? 'bearish-glow' : ''}`}>
      <h3>4-Pillar Rating</h3>

      <div className={`prediction-title ${direction}`}>
        {prediction?.rating || prediction?.prediction}
      </div>

      {prediction?.quality_score != null && (
        <div className="confidence-meter">
          <div className="confidence-label">
            <span>Quality Score</span>
            <span>{prediction.quality_score.toFixed(1)} / 100</span>
          </div>
          <div className="confidence-bar">
            <div
              className={`confidence-fill ${pillarClass(prediction.quality_score)}`}
              style={{ width: `${prediction.quality_score}%` }}
            />
          </div>
        </div>
      )}

      <div className="pillar-breakdown">
        <div className="pillar-row">
          <span className="pillar-label">AI Confidence</span>
          <div className="pillar-bar-track">
            <div className={`pillar-bar-fill ${pillarClass(prediction?.confidence || 0)}`}
                 style={{ width: `${prediction?.confidence || 0}%` }} />
          </div>
          <span className="pillar-value">{prediction?.confidence}%</span>
        </div>

        {prediction?.fund_score != null && (
          <div className="pillar-row">
            <span className="pillar-label">Fundamentals</span>
            <div className="pillar-bar-track">
              <div className={`pillar-bar-fill ${pillarClass(prediction.fund_score)}`}
                   style={{ width: `${prediction.fund_score}%` }} />
            </div>
            <span className="pillar-value">{prediction.fund_score.toFixed(1)}</span>
          </div>
        )}

        <div className="pillar-row">
          <span className="pillar-label">Momentum</span>
          <div className="pillar-bar-track">
            <div className={`pillar-bar-fill ${pillarClass(prediction?.momentum_score || 0)}`}
                 style={{ width: `${prediction?.momentum_score || 0}%` }} />
          </div>
          <span className="pillar-value">{prediction?.momentum_score?.toFixed(1)}</span>
        </div>

        {prediction?.news_score != null && (
          <div className="pillar-row">
            <span className="pillar-label">News Sentiment</span>
            <div className="pillar-bar-track">
              <div className={`pillar-bar-fill ${pillarClass(prediction.news_score)}`}
                   style={{ width: `${prediction.news_score}%` }} />
            </div>
            <span className="pillar-value">{news?.label || prediction.news_score.toFixed(1)}</span>
          </div>
        )}
      </div>

      {news?.headlines?.length > 0 && (
        <div className="news-headlines">
          <h4 className="key-factors-title">Recent News</h4>
          <ul className="news-list">
            {news.headlines.map((h, i) => (
              <li key={i} className="news-item">{h}</li>
            ))}
          </ul>
        </div>
      )}

      {(prediction?.key_factors?.bullish?.length > 0 || prediction?.key_factors?.bearish?.length > 0) && (
        <div className="key-factors">
          <h4 className="key-factors-title">Key Drivers</h4>
          <ul className="key-factors-list">
            {prediction.key_factors.bullish.map((f, i) => (
              <li key={`b${i}`} className="factor bullish-factor">{f}</li>
            ))}
            {prediction.key_factors.bearish.map((f, i) => (
              <li key={`r${i}`} className="factor bearish-factor">{f}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="model-accuracy">Model Training Accuracy: {prediction?.model_accuracy}%</p>
    </div>
  )
}
