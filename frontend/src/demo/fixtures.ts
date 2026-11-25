export const demoProjectId = 'commerce-demo'
export const demoPlanId = 'checkout-plan'
export const demoBaselineId = 'demo-baseline'
export const demoCandidateId = 'demo-candidate'

export const demoProjectPath = '/projects/' + demoProjectId
export const demoTestPath = demoProjectPath + '/tests/' + demoPlanId
export const demoReportPath = demoProjectPath + '/runs/' + demoCandidateId
export const demoRelease = { baselineP95: 184, candidateP95: 222, maxIncreasePercent: 10 }
