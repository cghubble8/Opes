# Deployment Checklist — Opes to Vercel

## Pre-Deployment Review
This checklist covers the security and quality fixes applied before initial Vercel deployment.

### ✅ Security Fixes (CRITICAL)

**C1: Cross-Tenant Token Acceptance (CWE-287)**
- [x] Added `azp` (authorized party) claim validation in `api/utils/security.py`
- [x] Tokens from other Clerk applications are now rejected
- **Requires:** Set `CLERK_AUTHORIZED_PARTY` environment variable in Vercel project settings

**H1: Silent Authentication Failures**
- [x] Fixed `topStocks.js` to throw error on 401 instead of silently returning mock data
- [x] Consistent with `analyze.js` behavior — authentication failures are now visible to users

### ✅ Dependency Security (MEDIUM)

**M1: Unpinned @clerk/react Version**
- [x] Pinned `@clerk/react` to `^5.0.0` in `package.json`
- [x] Prevents breaking changes from silent version bumps during deploy

**M2: Unscoped Budget localStorage**
- [x] Scoped budget localStorage key to user ID: `budget_v1_{userId}`
- [x] Prevents data leakage on shared browsers / multi-user devices
- [x] Updated `Budget.jsx` to pass Clerk `user.id` to budget service

### ✅ Code Quality Fixes

- [x] Removed unused `signOut` import from `App.jsx`
- [x] Clarified misleading CSRF comment in `main.jsx`
- [x] Removed unnecessary `formatPercentage` wrapper in `Budget.jsx`
- [x] Fixed rounding bug in `handleSaveTotalBudget` (recompute totalBudget from categories)
- [x] Fixed `onBlur` firing after Escape cancel by guarding against empty values
- [x] Moved `CustomTooltip` outside render function to prevent re-creation on every render
- [x] Extracted shared token getter pattern to `src/services/auth.js`

## Environment Variables Required for Production

Set these in Vercel project settings → Environment Variables:

| Variable | Value | Description |
|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | (from Clerk dashboard) | Frontend Clerk SDK key (browser-safe, public) |
| `CLERK_JWKS_URL` | `https://[your-domain]/.well-known/jwks.json` | Clerk JWKS endpoint for token verification |
| `CLERK_AUTHORIZED_PARTY` | (your Clerk publishable key) | Validates `azp` claim to prevent cross-tenant tokens |

## Deployment Steps

1. **Ensure all changes are committed:**
   ```bash
   git add .
   git commit -m "Security hardening, Clerk auth integration, Code quality improvements"
   ```

2. **Set environment variables in Vercel:**
   - Go to Project Settings → Environment Variables
   - Add the three variables listed above
   - Make sure they're available in Production environment

3. **Deploy to Vercel:**
   ```bash
   git push origin main
   ```
   Vercel will automatically deploy the main branch.

4. **Verify in Production:**
   - Open browser DevTools Console
   - Check for CSP violation warnings (none expected)
   - Test authentication flow:
     - Sign in via Clerk
     - Analyze a stock (should fetch data)
     - View Top 5 Buys (should load)
     - Check Budget tab with user ID in localStorage
   - Check server logs for any JWT validation errors

## Post-Deployment Validation

### Authentication Flow
- [ ] User can sign in via Clerk
- [ ] Expired/invalid tokens show "Session expired. Please sign in again."
- [ ] Top Stocks view errors on 401 (doesn't silently serve mock data)

### Budget Feature
- [ ] Budget data is per-user (check localStorage in DevTools)
- [ ] Different users see different budgets on shared browser
- [ ] Category edits persist and are user-scoped

### Security Headers
- [ ] `X-Content-Type-Options: nosniff` present
- [ ] `X-Frame-Options: DENY` present
- [ ] `Cache-Control: no-store` present
- [ ] CORS headers allow only configured origins

## Rollback Plan

If issues arise after deployment:
1. Remove or rollback the commit
2. Redeploy from a known-good commit
3. Check Vercel logs for JWT validation or environment variable errors
4. Verify environment variables are set correctly in Vercel UI (not in .env.local)

## Known Limitations (Not Blockers)

- Budget feature uses mock transaction data (no real financial records)
- Rate limiting is advisory only (requires Upstash Redis for production scale)
- ML model retrains on every request (acceptable for current load)

## Questions?

- Check `CLAUDE.md` for architecture overview
- Review `Docs/updates.txt` for recent feature additions
- See `api/utils/security.py` docstring for security rationale
