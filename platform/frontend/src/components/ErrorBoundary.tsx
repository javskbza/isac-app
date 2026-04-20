import { Component, ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // Plain DOM write so it's visible even if React styles fail
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, fontFamily: 'monospace', background: '#fff1f2', minHeight: '100vh' }}>
          <h2 style={{ color: '#b91c1c', marginBottom: 8 }}>Render error</h2>
          <pre style={{ background: '#fee2e2', padding: 16, borderRadius: 8, whiteSpace: 'pre-wrap', fontSize: 13, color: '#7f1d1d' }}>
            {this.state.error.message}
            {'\n\n'}
            {this.state.error.stack}
          </pre>
          <button
            style={{ marginTop: 16, padding: '8px 16px', background: '#dc2626', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
            onClick={() => this.setState({ error: null })}
          >
            Dismiss
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
