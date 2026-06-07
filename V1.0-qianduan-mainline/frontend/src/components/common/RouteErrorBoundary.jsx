import { Component } from 'react'

/**
 * Catches render errors in routed pages so a single tab crash does not leave a blank white screen.
 */
export class RouteErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    this.setState({ info })
    console.error('[RouteErrorBoundary]', error, info?.componentStack)
  }

  render() {
    const { error, info } = this.state
    if (error) {
      return (
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <h1 className="text-lg font-semibold text-red-900">This page hit a runtime error</h1>
            <p className="text-sm text-red-800 mt-2">
              The rest of the app shell should still work. Try another route, or reload after fixing the issue below.
            </p>
            <pre className="mt-3 text-xs bg-white/80 border border-red-100 rounded-lg p-3 overflow-auto text-red-950 whitespace-pre-wrap">
              {error?.message || String(error)}
            </pre>
            {info?.componentStack && (
              <details className="mt-2 text-xs text-red-900/80">
                <summary className="cursor-pointer font-medium">Component stack</summary>
                <pre className="mt-1 whitespace-pre-wrap opacity-90">{info.componentStack}</pre>
              </details>
            )}
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
