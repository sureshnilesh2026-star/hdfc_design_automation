import { Component, type ReactNode } from "react";
import { Alert, Button } from "./ui";

type Props = { children: ReactNode };
type State = { message: string | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { message: null };

  static getDerivedStateFromError(error: Error): State {
    return { message: error.message };
  }

  render() {
    if (this.state.message) {
      return (
        <Alert tone="error" title="This screen could not be shown">
          {this.state.message}
          <div style={{ marginTop: 12 }}>
            <Button type="button" onClick={() => this.setState({ message: null })}>
              Try again
            </Button>
          </div>
        </Alert>
      );
    }
    return this.props.children;
  }
}
