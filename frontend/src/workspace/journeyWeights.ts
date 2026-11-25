type RequestStep = { method?: string; path: string }
type Journey = { name: string; steps: RequestStep[] }

export function journeyRouteOptions(journeys: Journey[], mix: { route: string; count: number }[]) {
  const routes = journeys.map(journey => journey.steps.map(step =>
    (step.method || 'GET') + ' ' + step.path.split('?')[0].replace(/\$\{([^}]+)\}/g, '{$1}')))
  return routes.map((steps, index) => {
    const occurrences = new Map<string, number>()
    for (const step of steps) occurrences.set(step, (occurrences.get(step) ?? 0) + 1)
    return mix.flatMap(({ route, count }) => {
      const perJourney = occurrences.get(route)
      if (!count || !perJourney || routes.some((other, i) => i !== index && other.includes(route))) return []
      return [{ route, count, perJourney }]
    })
  })
}

export function normalizedJourneyWeights(markers: { count: number; perJourney: number }[]) {
  const starts = markers.map(marker => marker.count / marker.perJourney)
  const total = starts.reduce((sum, value) => sum + value, 0)
  return starts.map(value => value / total)
}
