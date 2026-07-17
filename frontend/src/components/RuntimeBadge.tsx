import { useQuery } from '@tanstack/react-query'

import { validateSession } from '../api/client'

export function RuntimeBadge() {
  const session = useQuery({
    queryKey: ['session'],
    queryFn: validateSession,
    staleTime: Number.POSITIVE_INFINITY,
  })
  if (!session.data) return null
  const demo = session.data.runtime_mode === 'demo'
  return (
    <span className={`runtime-badge ${demo ? 'runtime-demo' : 'runtime-live'}`}>
      {demo ? '离线演示' : '真实模型'} · v{session.data.version}
    </span>
  )
}
