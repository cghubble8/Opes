import { useState } from 'react'

function Login({ onLogin }) {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError('')

        if (!email || !password) {
            setError('Please fill in all fields')
            return
        }

        setLoading(true)

        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000))

        // Demo login - accept any credentials
        setLoading(false)
        onLogin({ email, name: email.split('@')[0] })
    }

    const handleDemoLogin = async () => {
        setLoading(true)
        await new Promise(resolve => setTimeout(resolve, 800))
        setLoading(false)
        onLogin({ email: 'demo@opes.com', name: 'Demo User' })
    }

    return (
        <div className="login-container">
            <div className="login-card">
                {/* Logo */}
                <div className="login-header">
                    <div className="login-logo">
                        <span className="logo-text">Opes</span>
                    </div>
                    <p className="login-subtitle">AI-Powered Stock Analysis</p>
                </div>

                {/* Form */}
                <form className="login-form" onSubmit={handleSubmit}>
                    <div className="input-group">
                        <label htmlFor="email">Email</label>
                        <input
                            type="email"
                            id="email"
                            placeholder="you@example.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    <div className="input-group">
                        <label htmlFor="password">Password</label>
                        <input
                            type="password"
                            id="password"
                            placeholder="••••••••"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    {error && <div className="login-error">{error}</div>}

                    <button
                        type="submit"
                        className="btn-primary login-btn"
                        disabled={loading}
                    >
                        {loading ? 'Signing in...' : 'Sign In'}
                    </button>
                </form>

                {/* Divider */}
                <div className="login-divider">
                    <span>or</span>
                </div>

                {/* Demo Button */}
                <button
                    className="demo-login-btn"
                    onClick={handleDemoLogin}
                    disabled={loading}
                >
                    Try Demo Account
                </button>

                {/* Footer */}
                <p className="login-footer">
                    Demo app for portfolio tracking and stock analysis
                </p>
            </div>

            {/* Background decoration */}
            <div className="login-bg-decoration">
                <div className="bg-circle bg-circle-1"></div>
                <div className="bg-circle bg-circle-2"></div>
                <div className="bg-circle bg-circle-3"></div>
            </div>
        </div>
    )
}

export default Login
