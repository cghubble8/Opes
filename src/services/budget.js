const DEFAULT_CATEGORIES = [
  { name: 'Housing', budget: 1500, spent: 1500, color: '#C9A84C' },
  { name: 'Food & Dining', budget: 800, spent: 620, color: '#34D27A' },
  { name: 'Transportation', budget: 400, spent: 280, color: '#5B9BD5' },
  { name: 'Entertainment', budget: 300, spent: 195, color: '#A855F7' },
  { name: 'Healthcare', budget: 200, spent: 145, color: '#FF6058' },
  { name: 'Shopping', budget: 500, spent: 480, color: '#D4922A' },
  { name: 'Utilities', budget: 300, spent: 200, color: '#2DD4BF' },
];

const MOCK_TRANSACTIONS = [
  { id: 1, date: '2026-04-10', description: 'Grocery Store', category: 'Food & Dining', amount: 85.50 },
  { id: 2, date: '2026-04-09', description: 'Gas Station', category: 'Transportation', amount: 65.00 },
  { id: 3, date: '2026-04-09', description: 'Movie Ticket', category: 'Entertainment', amount: 18.00 },
  { id: 4, date: '2026-04-08', description: 'Restaurant Dinner', category: 'Food & Dining', amount: 125.75 },
  { id: 5, date: '2026-04-08', description: 'Pharmacy', category: 'Healthcare', amount: 45.00 },
  { id: 6, date: '2026-04-07', description: 'Clothing Store', category: 'Shopping', amount: 189.99 },
  { id: 7, date: '2026-04-07', description: 'Electric Bill', category: 'Utilities', amount: 95.00 },
  { id: 8, date: '2026-04-06', description: 'Uber Trip', category: 'Transportation', amount: 32.50 },
  { id: 9, date: '2026-04-06', description: 'Coffee Shop', category: 'Food & Dining', amount: 6.25 },
  { id: 10, date: '2026-04-05', description: 'Streaming Service', category: 'Entertainment', amount: 15.99 },
  { id: 11, date: '2026-04-05', description: 'Online Shopping', category: 'Shopping', amount: 289.99 },
  { id: 12, date: '2026-04-04', description: 'Restaurant Lunch', category: 'Food & Dining', amount: 21.50 },
];

// Load budgets from localStorage and merge with defaults
function loadCategoriesFromStorage(userId) {
  const storageKey = `budget_v1_${userId}`;
  const stored = localStorage.getItem(storageKey);
  if (!stored) {
    return DEFAULT_CATEGORIES;
  }

  try {
    const savedBudgets = JSON.parse(stored);
    // Merge saved budgets back over defaults while preserving default structure
    return DEFAULT_CATEGORIES.map((cat) => {
      const saved = savedBudgets.find((s) => s.name === cat.name);
      return saved ? { ...cat, budget: saved.budget } : cat;
    });
  } catch (e) {
    console.error('Failed to parse budget from localStorage:', e);
    return DEFAULT_CATEGORIES;
  }
}

// Save budgets to localStorage (only the budget amounts, not spent/color)
export function saveBudget(categories, userId) {
  const storageKey = `budget_v1_${userId}`;
  const toStore = categories.map((cat) => ({ name: cat.name, budget: cat.budget }));
  localStorage.setItem(storageKey, JSON.stringify(toStore));
}

// Fetch budget data with a fake delay (like getPortfolio)
export async function getBudget(userId) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const categories = loadCategoriesFromStorage(userId);
      const totalBudget = categories.reduce((sum, cat) => sum + cat.budget, 0);
      const totalSpent = categories.reduce((sum, cat) => sum + cat.spent, 0);

      resolve({
        month: 'April 2026',
        categories,
        totalBudget,
        totalSpent,
        totalRemaining: totalBudget - totalSpent,
        transactions: MOCK_TRANSACTIONS,
      });
    }, 400);
  });
}
