import { expect, it } from 'vitest'
import { journeyRouteOptions, normalizedJourneyWeights } from './journeyWeights'

it('estimates starts from exclusive routes and corrects for repeated requests', () => {
  const journeys = [
    { name: 'Browse', steps: [{ path: '/browse' }, { path: '/browse' }, { path: '/config' }] },
    { name: 'Checkout', steps: [{ path: '/config' }, { method: 'POST', path: '/order/${item_id}?test=true' }] },
  ]
  const options = journeyRouteOptions(journeys, [
    { route: 'GET /browse', count: 180 }, { route: 'POST /order/{item_id}', count: 10 },
    { route: 'GET /config', count: 200 },
  ])
  expect(options.map(items => items.map(item => item.route))).toEqual([['GET /browse'], ['POST /order/{item_id}']])
  expect(normalizedJourneyWeights(options.map(items => items[0]))).toEqual([.9, .1])
})

it('leaves unsampled and shared-only journeys without suggestions', () => {
  const journeys = [{ name: 'a', steps: [{ path: '/same' }] }, { name: 'b', steps: [{ path: '/same' }] }]
  expect(journeyRouteOptions(journeys, [{ route: 'GET /same', count: 20 }])).toEqual([[], []])
})
