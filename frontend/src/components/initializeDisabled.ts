// The compatibility controller owns these buttons' enabled state. A static
// React disabled prop would suppress clicks even after it enables the DOM node.
// Keep this ref stable so ordinary rerenders preserve the controller's state.
export function initializeDisabled(element: HTMLButtonElement | null): void {
  if (element) element.disabled = true
}
