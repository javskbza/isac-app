import { Component, ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center p-8">
          <div className="max-w-lg rounded-lg border border-destructive bg-card p-6">
            <h2 className="mb-2 text-lg font-semibold text-destructive">Something went wrong</h2>
            <pre className="overflow-auto rounded bg-muted p-3 text-xs text-muted-foreground">
              {this.state.error.message}
            </pre>
            <button
              className="mt-4 rounded bg-primary px-4 py-2 text-sm text-primary-foreground"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
