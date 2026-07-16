import { useEffect, useState } from 'react'

export function TypewriterText({ text }: { text: string }) {
  return <TypedText key={text} text={text} />
}

function TypedText({ text }: { text: string }) {
  const [length, setLength] = useState(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches ? text.length : 0,
  )

  useEffect(() => {
    const timer = window.setInterval(() => {
      setLength((value) => {
        if (value >= text.length) {
          window.clearInterval(timer)
          return value
        }
        return value + 1
      })
    }, 24)
    return () => window.clearInterval(timer)
  }, [text])

  return <>{text.slice(0, length)}</>
}
