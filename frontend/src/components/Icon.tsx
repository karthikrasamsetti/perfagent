const paths = {
  home: 'M3 10l9-7 9 7v10H4V10 M9 20v-7h6v7',
  projects: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  add: 'M12 5v14M5 12h14',
  workspace: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  dashboard: 'M3 3v16a2 2 0 0 0 2 2h16 M7 14l4-4 4 2 5-6',
  pulse: 'M2 12h5l3-8 4 16 3-8h5',
  activity: 'M5 5h14M5 12h14M5 19h14',
  upload: 'M12 16V4M7 9l5-5 5 5M4 16v4h16v-4',
  git: 'M6 7v10m12-9a7 7 0 0 1-7 7H6 M6 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4 M6 17a2 2 0 1 0 0 4 2 2 0 0 0 0-4 M18 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4',
  shield: 'M12 22s7-3 7-9V6l-7-3-7 3v7c0 6 7 9 7 9z M9 12l2 2 4-4',
  collapse: 'M14 6l-6 6 6 6',
  close: 'M6 6l12 12M18 6 6 18',
  refresh: 'M20 7v5h-5m5-1a8 8 0 1 0-2 7',
  download: 'M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4',
} as const

export function Icon({ name }: { name: keyof typeof paths }) {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
    strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={paths[name]} />
  </svg>
}
