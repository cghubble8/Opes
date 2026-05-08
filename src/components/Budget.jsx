import { useState, useEffect } from 'react'
import { useUser } from '@clerk/react'
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { getBudget, saveBudget } from '../services/budget'
import CandlestickLoader from './CandlestickLoader'
import './Budget.css'

// Pure utility functions
const formatCurrencyValue = (num) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(num)
}

const CustomTooltip = ({ active, payload, totalSpent }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload
    const percentage = ((data.spent / totalSpent) * 100).toFixed(1)
    return (
      <div className="custom-tooltip">
        <p className="tooltip-label">{data.name}</p>
        <p className="tooltip-value">{formatCurrencyValue(data.spent)}</p>
        <p className="tooltip-percent">{percentage}%</p>
      </div>
    )
  }
  return null
}

function Budget() {
  const { user } = useUser()
  const [budget, setBudget] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingCategory, setEditingCategory] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [editingTotalBudget, setEditingTotalBudget] = useState(false)
  const [editTotalValue, setEditTotalValue] = useState('')

  useEffect(() => {
    if (user?.id) {
      loadBudget()
    }
  }, [user?.id])

  const loadBudget = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getBudget(user.id)
      setBudget(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }



  // Handle budget amount edit
  const handleEditBudget = (categoryName, currentBudget) => {
    setEditingCategory(categoryName)
    setEditValue(currentBudget.toString())
  }

  const handleSaveBudget = (categoryName) => {
    if (!editValue.trim()) return
    const newBudget = parseFloat(editValue)
    if (isNaN(newBudget) || newBudget <= 0) {
      alert('Budget must be a positive number')
      return
    }

    const updatedCategories = budget.categories.map((cat) =>
      cat.name === categoryName ? { ...cat, budget: newBudget } : cat
    )

    saveBudget(updatedCategories, user.id)
    setBudget({
      ...budget,
      categories: updatedCategories,
      totalBudget: updatedCategories.reduce((sum, cat) => sum + cat.budget, 0),
      totalRemaining: updatedCategories.reduce((sum, cat) => sum + cat.budget, 0) - budget.totalSpent,
    })
    setEditingCategory(null)
  }

  const handleCancelEdit = () => {
    setEditValue('')
    setEditingCategory(null)
  }

  const handleKeyDown = (e, categoryName) => {
    if (e.key === 'Enter') {
      handleSaveBudget(categoryName)
    } else if (e.key === 'Escape') {
      handleCancelEdit()
    }
  }

  // Handle total budget editing
  const handleEditTotalBudget = () => {
    setEditingTotalBudget(true)
    setEditTotalValue(budget.totalBudget.toString())
  }

  const handleSaveTotalBudget = () => {
    if (!editTotalValue.trim()) return
    const newTotal = parseFloat(editTotalValue)
    if (isNaN(newTotal) || newTotal <= 0) {
      alert('Budget must be a positive number')
      return
    }

    const scaleFactor = newTotal / budget.totalBudget
    const scaledCategories = budget.categories.map((cat) => ({
      ...cat,
      budget: Math.round(cat.budget * scaleFactor * 100) / 100,
    }))

    saveBudget(scaledCategories, user.id)
    const recomputedTotal = scaledCategories.reduce((sum, cat) => sum + cat.budget, 0)
    setBudget({
      ...budget,
      categories: scaledCategories,
      totalBudget: recomputedTotal,
      totalRemaining: recomputedTotal - budget.totalSpent,
    })
    setEditingTotalBudget(false)
  }

  const handleCancelTotalEdit = () => {
    setEditingTotalBudget(false)
    setEditTotalValue('')
  }

  const handleTotalKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSaveTotalBudget()
    } else if (e.key === 'Escape') {
      handleCancelTotalEdit()
    }
  }

  // Calculate budget used percentage
  const budgetPercentage = budget ? (budget.totalSpent / budget.totalBudget) * 100 : 0

  // Determine progress bar color
  const getProgressColor = (percentage) => {
    if (percentage <= 50) return '#C9A84C' // gold
    if (percentage <= 75) return '#D4922A' // warning
    return '#E03030' // danger
  }

  // Sort categories by spent amount descending
  const sortedCategories = budget
    ? [...budget.categories].sort((a, b) => b.spent - a.spent)
    : []

  // Tooltip with totalSpent context
  const BudgetTooltip = (props) => <CustomTooltip {...props} totalSpent={budget?.totalSpent} />

  if (loading) {
    return (
      <div className="budget-container">
        <CandlestickLoader message="Loading your budget…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="budget-container">
        <div className="error-container">
          <div className="error-icon">!</div>
          <p className="error-message">{error}</p>
          <button className="btn-primary" onClick={loadBudget}>
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="budget-container">
      {/* Summary Bar */}
      <div className="budget-summary-bar card">
        <div className="summary-header">
          <h3>Budget Overview — {budget.month}</h3>
        </div>

        <div className="summary-stats">
          <div className="stat-pill">
            <span className="stat-label">Total Budget</span>
            {editingTotalBudget ? (
              <div className="stat-edit-input">
                <input
                  type="number"
                  value={editTotalValue}
                  onChange={(e) => setEditTotalValue(e.target.value)}
                  onKeyDown={handleTotalKeyDown}
                  onBlur={handleSaveTotalBudget}
                  autoFocus
                />
              </div>
            ) : (
              <span className="stat-value editable" onClick={handleEditTotalBudget}>
                {formatCurrencyValue(budget.totalBudget)}
              </span>
            )}
          </div>
          <div className="stat-pill">
            <span className="stat-label">Spent</span>
            <span className="stat-value">{formatCurrencyValue(budget.totalSpent)}</span>
          </div>
          <div className="stat-pill">
            <span className="stat-label">Remaining</span>
            <span className={`stat-value ${budget.totalRemaining >= 0 ? 'positive' : 'negative'}`}>
              {budget.totalRemaining >= 0 ? '+' : ''}{formatCurrencyValue(budget.totalRemaining)}
            </span>
          </div>
        </div>

        {/* Budget Progress Bar */}
        <div className="budget-progress-container">
          <div className="progress-label">
            <span>Budget Used</span>
            <span className="progress-percent">{budgetPercentage.toFixed(1)}%</span>
          </div>
          <div className="budget-progress">
            <div
              className="budget-progress-fill"
              style={{
                width: `${Math.min(budgetPercentage, 100)}%`,
                backgroundColor: getProgressColor(budgetPercentage),
              }}
            />
          </div>
        </div>
      </div>

      {/* Two-Column Layout: Chart + Categories */}
      <div className="budget-grid">
        {/* Pie Chart */}
        <div className="budget-chart-section card">
          <h3 className="section-title">Spending by Category</h3>
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={budget.categories}
                  dataKey="spent"
                  nameKey="name"
                  cx="50%"
                  cy="45%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  label={false}
                >
                  {budget.categories.map((category, index) => (
                    <Cell key={`cell-${index}`} fill={category.color} />
                  ))}
                </Pie>
                <Tooltip content={<BudgetTooltip />} />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-center-label">
            <div className="chart-label-value">{formatCurrencyValue(budget.totalSpent)}</div>
            <div className="chart-label-text">Total Spent</div>
          </div>
        </div>

        {/* Categories List */}
        <div className="budget-categories-section">
          <h3 className="section-title">Categories</h3>
          <div className="categories-list">
            {sortedCategories.map((category) => {
              const categoryPercentage = (category.spent / category.budget) * 100
              const isOverBudget = category.spent > category.budget
              const isEditing = editingCategory === category.name

              return (
                <div key={category.name} className="category-row card">
                  <div className="category-header">
                    <div className="category-name-section">
                      <span className="category-color-dot" style={{ backgroundColor: category.color }} />
                      <span className="category-name">{category.name}</span>
                    </div>
                    {isOverBudget && <span className="category-badge-warning">Over Budget</span>}
                  </div>

                  <div className="category-amounts">
                    <span className="category-spent">{formatCurrencyValue(category.spent)}</span>
                    <span className="category-separator">/</span>
                    {isEditing ? (
                      <div className="category-edit-input">
                        <input
                          type="number"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => handleKeyDown(e, category.name)}
                          onBlur={() => handleSaveBudget(category.name)}
                          autoFocus
                        />
                        <span className="edit-hint">Press Enter to save</span>
                      </div>
                    ) : (
                      <span
                        className="category-budget"
                        onClick={() => handleEditBudget(category.name, category.budget)}
                      >
                        {formatCurrencyValue(category.budget)}
                      </span>
                    )}
                  </div>

                  <div className="category-progress">
                    <div
                      className="category-progress-fill"
                      style={{
                        width: `${Math.min(categoryPercentage, 100)}%`,
                        backgroundColor: isOverBudget ? '#E03030' : category.color,
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="budget-transactions card">
        <h3 className="section-title">Recent Transactions</h3>
        <div className="transactions-list">
          {budget.transactions.slice(0, 8).map((transaction) => {
            const category = budget.categories.find((c) => c.name === transaction.category)
            const categoryColor = category ? category.color : '#999'

            return (
              <div key={transaction.id} className="transaction-row">
                <div className="transaction-left">
                  <span className="transaction-date">{transaction.date}</span>
                  <span className="transaction-description">{transaction.description}</span>
                </div>
                <div className="transaction-right">
                  <span
                    className="transaction-category-badge"
                    style={{
                      backgroundColor: `${categoryColor}22`,
                      borderColor: categoryColor,
                      color: categoryColor,
                    }}
                  >
                    {transaction.category}
                  </span>
                  <span className="transaction-amount">−{formatCurrencyValue(transaction.amount)}</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="demo-notice">
        <span>Demo budget with editable categories</span>
      </div>
    </div>
  )
}

export default Budget
