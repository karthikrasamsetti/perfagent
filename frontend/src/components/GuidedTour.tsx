import { useEffect, useRef, useState } from 'react'
import home from '../../../docs/screenshots/home.png'
import projects from '../../../docs/screenshots/projects-redesign.png'
import describe from '../../../docs/screenshots/describe-redesign.png'
import review from '../../../docs/screenshots/review-plan-redesign.png'
import verify from '../../../docs/screenshots/verify-redesign.png'
import run from '../../../docs/screenshots/live-run-redesign.png'
import report from '../../../docs/screenshots/release-report.png'
import dashboard from '../../../docs/screenshots/release-dashboard.png'

const preferenceKey = 'perfagent:guided-tour:v1'
const stops = [
  { title: 'Home', image: home, heading: 'Choose where to start', detail: 'Create a test, open your projects, or import an existing k6 script from Home.' },
  { title: 'Projects', image: projects, heading: 'Organize tests by application', detail: 'Open a project to see its tests and saved runs. Create a test inside the project you want to use.' },
  { title: 'Describe', image: describe, heading: 'Set your target and workload', detail: 'Enter the target URL and endpoints. Choose a load, spike, soak, or stress test and set the duration, users, or throughput goal.' },
  { title: 'Review plan', image: review, heading: 'Confirm what will be sent', detail: 'Review the drafted requests, traffic, and thresholds. Add a response check, attach data for request fields, or capture a response value for a later request. Preview sample requests before you approve.' },
  { title: 'Verify', image: verify, heading: 'Check the requests and script', detail: 'Inspect the generated k6 script and verify the requests and checks. Use Release or commit to label a candidate for comparison.' },
  { title: 'Run', image: run, heading: 'Watch the workload', detail: 'Start or stop a run from the live view. Watch achieved throughput, latency, errors, and dropped iterations as the test progresses.' },
  { title: 'Report', image: report, heading: 'Read the verdict and evidence', detail: 'Review what happened, check k6 thresholds and release readiness, and download the HTML report. Approve a representative run as a baseline and set budgets for future candidates.' },
  { title: 'Dashboard', image: dashboard, heading: 'Compare results across runs', detail: 'Filter by test or environment. Inspect historical latency, throughput, and errors, and open a run to compare it with the approved baseline.' },
]

export function GuidedTour() {
  const [step, setStep] = useState(-1)
  const dialog = useRef<HTMLDialogElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const title = useRef<HTMLHeadingElement>(null)
  const stop = stops[step]

  function open(firstStep: number) {
    setStep(firstStep)
    dialog.current?.showModal()
  }

  useEffect(() => {
    try {
      if (!localStorage.getItem(preferenceKey)) open(-1)
    } catch {
      // The Help button still opens the tour when browser storage is unavailable.
    }
  }, [])

  useEffect(() => {
    if (dialog.current?.open) title.current?.focus()
  }, [step])

  function dismiss() {
    try {
      localStorage.setItem(preferenceKey, 'seen')
    } catch {
      // Closing the tour still works when browser storage is unavailable.
    }
    trigger.current?.focus()
  }

  return (
    <>
      <button className="btn ghost sm" type="button" ref={trigger} onClick={() => open(-1)}
        aria-haspopup="dialog">Help<span className="tour-help-label"> · Guided tour</span></button>
      <dialog ref={dialog} className="guided-tour" aria-labelledby="tour-title" onClose={dismiss}>
        <div className="guided-tour-content">
          <h2 id="tour-title" ref={title} tabIndex={-1}>
            {stop ? <><span>Step {step + 1} of {stops.length}</span>{stop.title}</> : 'Take a tour of PerfAgent'}
          </h2>
          {stop ? (
            <>
              <h3>{stop.heading}</h3>
              <p>{stop.detail}</p>
              <img className="guided-tour-example" src={stop.image} alt="" />
            </>
          ) : <p>Follow a sample checkout test from planning to reporting. The tour uses screenshots and sends no test traffic.</p>}
          <div className="guided-tour-actions">
            <button type="button" className="btn ghost sm" onClick={() => dialog.current?.close()}>Skip tour</button>
            {step >= 0 && <button type="button" className="btn ghost sm" disabled={step === 0}
              onClick={() => setStep(step - 1)}>Previous</button>}
            <button type="button" className="btn sm" onClick={() => {
              if (step === stops.length - 1) dialog.current?.close()
              else setStep(step + 1)
            }}>{step < 0 ? 'Start tour' : step === stops.length - 1 ? 'Done' : 'Next'}</button>
          </div>
        </div>
      </dialog>
    </>
  )
}
