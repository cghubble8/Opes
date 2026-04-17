import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ClerkProvider } from '@clerk/react'
import './index.css'
import App from './App.jsx'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

if (!PUBLISHABLE_KEY) {
  throw new Error('VITE_CLERK_PUBLISHABLE_KEY is not set')
}

// Authorized parties — whitelist of origins that can use this Clerk frontend.
// This is a frontend SDK hint only; backend CORS enforcement in security.py is the actual security boundary.
const authorizedParties = [
  'http://localhost:5173',     // Vite dev server
  'https://finopes.vercel.app',   // production domain
]

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ClerkProvider
      publishableKey={PUBLISHABLE_KEY}
      afterSignOutUrl="/"
      authorizedParties={authorizedParties}
    >
      <App />
    </ClerkProvider>
  </StrictMode>,
)
